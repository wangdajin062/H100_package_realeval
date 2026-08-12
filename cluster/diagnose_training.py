#!/usr/bin/env python3
"""diagnose_training.py — 训练 NaN 根因诊断（合并 diag_nan / diag_trainer）

用法:
  python cluster/diagnose_training.py nan        # 精确定位 forward/backward 中 NaN 来源
  python cluster/diagnose_training.py trainer    # 逐 knob 复现 Trainer NaN
  python cluster/diagnose_training.py all        # 运行全部诊断

依赖 /workspace 下的 realeval 包和模型权重。
"""
from __future__ import annotations
import sys
sys.path.insert(0, "/workspace")

import itertools
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig, get_peft_model, TaskType

MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
PROMPT = "Determine if the following text is fraud or normal.\n\nText: {text}\n\nAnswer:"


# ── 共享工具 ──────────────────────────────────────────────────────────────────

def _get_tokenizer():
    tok = AutoTokenizer.from_pretrained(MODEL)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    return tok


# ── nan: 精确定位 forward/backward 中 NaN 来源 ──────────────────────────────

def diagnose_nan():
    """Pinpoint where NaN enters the first forward/backward pass."""
    from realeval.data import load_text_corpus

    tok = _get_tokenizer()

    print("=== loading model (bf16, device_map=auto) ===")
    model = AutoModelForCausalLM.from_pretrained(
        MODEL, torch_dtype=torch.bfloat16, device_map="auto")
    model = get_peft_model(model, LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0.05, task_type=TaskType.CAUSAL_LM,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"]))

    # dtype audit: Adam on bf16 params is a classic NaN source
    dt = {}
    for n, p in model.named_parameters():
        if p.requires_grad:
            dt[str(p.dtype)] = dt.get(str(p.dtype), 0) + 1
    print("trainable param dtypes:", dt, " <- fp32 expected for LoRA")

    ds = load_text_corpus("balanced4k", max_samples=64)
    texts, labels = ds["texts"], ds["labels"]

    ids_list, lab_list = [], []
    for t, l in zip(texts[:8], labels[:8]):
        p = tok(PROMPT.format(text=t), add_special_tokens=False)["input_ids"]
        a = tok(" fraud" if l == 1 else " normal", add_special_tokens=False)["input_ids"]
        a = a + [tok.eos_token_id]
        ids_list.append(p + a)
        lab_list.append([-100] * len(p) + a)

    maxlen = max(len(x) for x in ids_list)
    pad = tok.pad_token_id
    inp = torch.tensor([x + [pad] * (maxlen - len(x)) for x in ids_list])
    lab = torch.tensor([x + [-100] * (maxlen - len(x)) for x in lab_list])
    att = torch.tensor([[1] * len(x) + [0] * (maxlen - len(x)) for x in ids_list])

    dev = next(model.parameters()).device
    inp, lab, att = inp.to(dev), lab.to(dev), att.to(dev)
    n_sup = int((lab != -100).sum())
    print(f"batch: {inp.shape}  supervised tokens: {n_sup}")

    print("\n=== forward ===")
    model.train()
    out = model(input_ids=inp, attention_mask=att, labels=lab)
    print("logits finite:", torch.isfinite(out.logits).all().item(),
          " dtype:", out.logits.dtype,
          " absmax:", float(out.logits.abs().max()))
    print("loss:", float(out.loss), " finite:", torch.isfinite(out.loss).item())

    print("\n=== backward ===")
    out.loss.backward()
    bad = []
    for n, p in model.named_parameters():
        if p.requires_grad and p.grad is not None:
            if not torch.isfinite(p.grad).all():
                bad.append(n)
    print(f"params with non-finite grad: {len(bad)}")
    for n in bad[:8]:
        print("   ", n)
    if not bad:
        gn = torch.nn.utils.clip_grad_norm_(
            [p for p in model.parameters() if p.requires_grad], 1e9)
        print("grad_norm:", float(gn))

    del model
    torch.cuda.empty_cache()


# ── trainer: 逐 knob 复现 Trainer NaN ───────────────────────────────────────

def _build_pad_collator(pad_id: int):
    class PadCollator:
        def __init__(self, pad_id): self.pad_id = pad_id
        def __call__(self, feats):
            L = max(len(f["input_ids"]) for f in feats)
            ids, lab, att = [], [], []
            for f in feats:
                g = L - len(f["input_ids"])
                ids.append(list(f["input_ids"]) + [self.pad_id] * g)
                lab.append(list(f["labels"]) + [-100] * g)
                att.append(list(f["attention_mask"]) + [0] * g)
            return {"input_ids": torch.tensor(ids), "labels": torch.tensor(lab),
                    "attention_mask": torch.tensor(att)}
    return PadCollator(pad_id)


def _build_ds(n=128):
    from datasets import Dataset as HFDataset
    from realeval.data import load_text_corpus

    tok = _get_tokenizer()
    ds = load_text_corpus("balanced4k", max_samples=n)
    rows = {"input_ids": [], "labels": [], "attention_mask": []}
    for t, l in zip(ds["texts"], ds["labels"]):
        p = tok(PROMPT.format(text=t), add_special_tokens=False)["input_ids"][:200]
        a = tok(" fraud" if l == 1 else " normal", add_special_tokens=False)["input_ids"]
        a = a + [tok.eos_token_id]
        rows["input_ids"].append(p + a)
        rows["labels"].append([-100] * len(p) + a)
        rows["attention_mask"].append([1] * (len(p) + len(a)))
    return HFDataset.from_dict(rows)


def _run_trainer(tag: str, **over):
    from transformers import Trainer, TrainingArguments
    from peft import LoraConfig, get_peft_model, TaskType

    tok = _get_tokenizer()
    model = AutoModelForCausalLM.from_pretrained(
        MODEL, torch_dtype=torch.bfloat16, device_map="auto")
    model = get_peft_model(model, LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0.05, task_type=TaskType.CAUSAL_LM,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"]))
    cfg = dict(output_dir="/tmp/diag_out", num_train_epochs=1,
               per_device_train_batch_size=8, gradient_accumulation_steps=4,
               learning_rate=2e-5, warmup_ratio=0.1, lr_scheduler_type="cosine",
               logging_steps=1, max_steps=4, save_strategy="no",
               eval_strategy="no", bf16=True, dataloader_num_workers=4,
               report_to="none")
    cfg.update(over)
    tr = Trainer(model=model, args=TrainingArguments(**cfg),
                 train_dataset=_build_ds(),
                 data_collator=_build_pad_collator(tok.pad_token_id))
    hist = tr.train().metrics
    logs = [l for l in tr.state.log_history if "loss" in l]
    losses = [round(l["loss"], 4) for l in logs]
    gns = [l.get("grad_norm") for l in logs]
    ok = all(g is not None and g == g and g != float("inf") for g in gns)
    print(f"  [{'OK  ' if ok else 'NaN '}] {tag:38s} loss={losses}  grad_norm={gns}")
    del model, tr
    torch.cuda.empty_cache()


def diagnose_trainer():
    """Reproduce the Trainer NaN by turning one knob at a time."""
    print("=== baseline (mirrors train_sft.py) ===")
    _run_trainer("as-is")
    print("\n=== one knob at a time ===")
    _run_trainer("dataloader_num_workers=0", dataloader_num_workers=0)
    _run_trainer("gradient_accumulation_steps=1", gradient_accumulation_steps=1)
    _run_trainer("ga=1 + workers=0", gradient_accumulation_steps=1, dataloader_num_workers=0)
    _run_trainer("max_grad_norm=0.3", max_grad_norm=0.3)
    _run_trainer("bf16=False (fp32)", bf16=False)


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    import argparse
    ap = argparse.ArgumentParser(description="训练 NaN 根因诊断工具")
    ap.add_argument("mode", nargs="?", default="all",
                    choices=["nan", "trainer", "all"],
                    help="诊断模式：nan=forward/backward 定位, trainer=逐 knob 复现, all=全部运行")
    args = ap.parse_args()

    if args.mode in ("nan", "all"):
        print("=" * 72)
        print("  MODE: nan — forward/backward NaN pinpoint")
        print("=" * 72)
        diagnose_nan()

    if args.mode in ("trainer", "all"):
        print("\n" + "=" * 72)
        print("  MODE: trainer — knob-by-knob Trainer NaN reproduction")
        print("=" * 72)
        diagnose_trainer()


if __name__ == "__main__":
    main()
