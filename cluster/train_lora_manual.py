#!/usr/bin/env python
"""train_lora_manual.py — LoRA SFT with an explicit loop (no HF Trainer).

Why not Trainer: on this setup (bf16 LoRA + device_map="auto") the Trainer path emits
NaN gradients from around step 10, while an explicit loop with identical model, data and
hyper-parameters trains cleanly:

    step  0  loss 10.35  pre-clip 79.27  post-clip 1.00
    step 13  loss  1.64  pre-clip 65.93  post-clip 1.00

Training aborts immediately on a non-finite loss or gradient norm, so a broken run can no
longer produce a silently empty adapter.

Usage:
    PYTHONPATH=/workspace /workspace/venv/bin/python train_lora_manual.py --epochs 3
"""
from __future__ import annotations
import argparse, json, math, sys, time
from pathlib import Path

sys.path.insert(0, "/workspace")
import torch

MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
PROMPT = "Determine if the following text is fraud or normal.\n\nText: {text}\n\nAnswer:"


def build_rows(texts, labels, idxs, tok, max_len=256):
    """Exact prompt/answer boundary; only the answer tokens carry supervision."""
    rows = []
    for i in idxs:
        p = tok(PROMPT.format(text=texts[i]), add_special_tokens=False)["input_ids"]
        a = tok(" fraud" if labels[i] == 1 else " normal",
                add_special_tokens=False)["input_ids"] + [tok.eos_token_id]
        budget = max_len - len(a)
        if len(p) > budget:
            p = p[:budget]                    # truncate the prompt, never the answer
        rows.append({"ids": p + a, "lab": [-100] * len(p) + a, "label": int(labels[i])})
    return rows


def collate(batch, pad_id, device):
    L = max(len(r["ids"]) for r in batch)
    ids = torch.tensor([r["ids"] + [pad_id] * (L - len(r["ids"])) for r in batch])
    lab = torch.tensor([r["lab"] + [-100] * (L - len(r["lab"])) for r in batch])
    att = torch.tensor([[1] * len(r["ids"]) + [0] * (L - len(r["ids"])) for r in batch])
    return ids.to(device), lab.to(device), att.to(device)


@torch.no_grad()
def evaluate(model, rows, tok, device, batch_size=32):
    """Eval loss plus F1 from P(' fraud') vs P(' normal') at the answer position."""
    model.eval()
    fraud_id = tok(" fraud", add_special_tokens=False)["input_ids"][0]
    normal_id = tok(" normal", add_special_tokens=False)["input_ids"][0]
    tot, nb, tp, fp, fn, tn = 0.0, 0, 0, 0, 0, 0
    for s in range(0, len(rows), batch_size):
        b = rows[s:s + batch_size]
        ids, lab, att = collate(b, tok.pad_token_id, device)
        out = model(input_ids=ids, attention_mask=att, labels=lab)
        tot += float(out.loss); nb += 1
        for k, r in enumerate(b):
            pos = next(j for j, x in enumerate(r["lab"]) if x != -100)
            lg = out.logits[k, pos - 1]
            pred = 1 if float(lg[fraud_id]) > float(lg[normal_id]) else 0
            if pred == 1 and r["label"] == 1: tp += 1
            elif pred == 1 and r["label"] == 0: fp += 1
            elif pred == 0 and r["label"] == 1: fn += 1
            else: tn += 1
    prec = tp / max(1, tp + fp)
    rec = tp / max(1, tp + fn)
    f1 = 2 * prec * rec / max(1e-9, prec + rec)
    model.train()
    return {"loss": tot / max(1, nb), "f1": round(f1, 4),
            "accuracy": round((tp + tn) / max(1, tp + tn + fp + fn), 4),
            "precision": round(prec, 4), "recall": round(rec, 4),
            "tp": tp, "fp": fp, "fn": fn, "tn": tn}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="balanced4k")
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--lr", type=float, default=5e-6)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--max-grad-norm", type=float, default=1.0)
    ap.add_argument("--warmup-ratio", type=float, default=0.1)
    ap.add_argument("--lora-r", type=int, default=16)
    ap.add_argument("--max-samples", type=int, default=4000)
    ap.add_argument("--output-dir", default="/workspace/outputs/lora_manual")
    args = ap.parse_args()

    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import LoraConfig, get_peft_model, TaskType
    from realeval.data import load_text_corpus, group_split

    tok = AutoTokenizer.from_pretrained(MODEL)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    ds = load_text_corpus(args.corpus, max_samples=args.max_samples)
    texts, labels = ds["texts"], ds["labels"]
    tr_idx, te_idx = group_split(texts, labels, test_ratio=0.2, seed=42)
    train_rows = build_rows(texts, labels, tr_idx, tok)
    test_rows = build_rows(texts, labels, te_idx, tok)
    print(f"[data] {args.corpus}: {len(texts)} rows, {len(set(texts))} distinct")
    print(f"[data] train {len(train_rows)} / test {len(test_rows)}  "
          f"(train pos {sum(r['label'] for r in train_rows)})")

    model = AutoModelForCausalLM.from_pretrained(
        MODEL, torch_dtype=torch.bfloat16, device_map="auto")
    model = get_peft_model(model, LoraConfig(
        r=args.lora_r, lora_alpha=32, lora_dropout=0.05, task_type=TaskType.CAUSAL_LM,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"]))
    model.print_trainable_parameters()
    device = next(model.parameters()).device

    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=args.lr, weight_decay=0.01)
    spe = math.ceil(len(train_rows) / args.batch_size)
    total = spe * args.epochs
    warm = max(1, int(total * args.warmup_ratio))

    def lr_at(step):
        if step < warm:
            return args.lr * step / warm
        prog = (step - warm) / max(1, total - warm)
        return args.lr * 0.5 * (1 + math.cos(math.pi * prog))

    out_dir = Path(args.output_dir); out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[train] {total} steps ({spe}/epoch), warmup {warm}, bs {args.batch_size}")

    g = torch.Generator().manual_seed(42)
    best_f1, history, gstep = -1.0, [], 0
    recent, converged = [], False
    model.train()
    t0 = time.perf_counter()

    for epoch in range(args.epochs):
        if converged:
            break
        order = torch.randperm(len(train_rows), generator=g).tolist()
        for s in range(0, len(order), args.batch_size):
            batch = [train_rows[i] for i in order[s:s + args.batch_size]]
            ids, lab, att = collate(batch, tok.pad_token_id, device)

            out = model(input_ids=ids, attention_mask=att, labels=lab)
            loss = out.loss
            if not torch.isfinite(loss):
                sys.exit(f"[ABORT] non-finite loss at step {gstep}")

            opt.zero_grad(set_to_none=True)
            loss.backward()
            gn = torch.nn.utils.clip_grad_norm_(params, args.max_grad_norm)
            if not torch.isfinite(gn):
                sys.exit(f"[ABORT] non-finite grad_norm at step {gstep}")
            for pg in opt.param_groups:
                pg["lr"] = lr_at(gstep)
            opt.step()
            gstep += 1

            if gstep <= 5 or gstep % 10 == 0:
                print(f"  step {gstep:4d}/{total}  loss {float(loss):7.4f}  "
                      f"gn {float(gn):6.2f}  lr {lr_at(gstep):.2e}")

            # This task saturates quickly. Continuing on a near-flat loss surface is what
            # collapses Adam's second moment and overflows the gradient in bf16, so stop
            # once the loss has been negligible for a while.
            recent.append(float(loss))
            if len(recent) > 20:
                recent.pop(0)
            if len(recent) == 20 and max(recent) < 0.02:
                print(f"  [converged] max loss over last 20 steps "
                      f"{max(recent):.4f} < 0.02 at step {gstep}")
                converged = True
                break

        ev = evaluate(model, test_rows, tok, device)
        print(f"[epoch {epoch}] eval_loss {ev['loss']:.4f}  F1 {ev['f1']}  "
              f"acc {ev['accuracy']}  P {ev['precision']}  R {ev['recall']}  "
              f"({time.perf_counter()-t0:.0f}s)")
        history.append({"epoch": epoch, **ev})

        if ev["f1"] > best_f1:
            best_f1 = ev["f1"]
            ck = out_dir / "best"
            model.save_pretrained(ck); tok.save_pretrained(ck)
            print(f"[epoch {epoch}] new best F1 {best_f1} -> {ck}")

    (out_dir / "history.json").write_text(json.dumps(
        {"history": history, "best_f1": best_f1, "corpus": args.corpus,
         "lr": args.lr, "batch_size": args.batch_size, "epochs": args.epochs}, indent=2))
    print(f"\n[done] best F1 {best_f1}  adapter -> {out_dir/'best'}")


if __name__ == "__main__":
    main()
