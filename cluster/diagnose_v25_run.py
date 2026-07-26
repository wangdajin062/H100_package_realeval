#!/usr/bin/env python
"""diagnose_v25_run.py — Root-cause diagnosis for the 2026-07-22 H100 run.

Three red flags to explain:

  RF1  exp6 alpha_generic = 0.0          speculative decoding accepted ZERO tokens
  RF2  exp5 accuracy ~= 0.50             cross-dataset collapsed to chance
       exp3 F1 identical (0.6744)        ablation shows no downstream effect
  RF3  exp1 F1 = 0.9988, ce 1.27 -> 0.009 in one epoch    possible leakage/overfit

Each check is independent and prints PASS / FAIL / INCONCLUSIVE with the evidence.
Nothing is written to the repo; this is read-only apart from a JSON report.

Usage:
    python diagnose_v25_run.py                      # run every check
    python diagnose_v25_run.py --only rf1           # single check
    python diagnose_v25_run.py --results-dir ./results

Requires: the same env the experiments run in (torch + transformers + realeval on PYTHONPATH).
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

REPORT: dict = {"checks": {}}


def _hdr(title: str):
    print("\n" + "=" * 78)
    print(f"  {title}")
    print("=" * 78)


def _verdict(key: str, status: str, detail: str, evidence: dict | None = None):
    icon = {"PASS": "[PASS]", "FAIL": "[FAIL]", "WARN": "[WARN]",
            "INCONCLUSIVE": "[????]"}[status]
    print(f"\n{icon} {detail}")
    REPORT["checks"][key] = {"status": status, "detail": detail,
                             "evidence": evidence or {}}


# ═════════════════════════════════════════════════════════════════════════════
# RF1 — why is speculative-decoding alpha exactly 0.0?
# ═════════════════════════════════════════════════════════════════════════════
def check_rf1_tokenizer_compat(target_id: str, draft_id: str):
    """A vocab mismatch makes alpha=0 mathematically inevitable."""
    _hdr("RF1-a  draft/target tokenizer compatibility")
    try:
        from transformers import AutoTokenizer
        t_tok = AutoTokenizer.from_pretrained(target_id)
        d_tok = AutoTokenizer.from_pretrained(draft_id)
        t_size, d_size = len(t_tok), len(d_tok)
        print(f"  target {target_id}: vocab={t_size}")
        print(f"  draft  {draft_id}: vocab={d_size}")

        # Sample-level agreement: do both tokenisers encode the same string identically?
        probe = "Please verify your account by clicking the link within 24 hours."
        t_ids = t_tok(probe).input_ids
        d_ids = d_tok(probe).input_ids
        same_ids = t_ids == d_ids
        print(f"  probe encoding identical: {same_ids}")
        if not same_ids:
            print(f"    target ids[:12] = {t_ids[:12]}")
            print(f"    draft  ids[:12] = {d_ids[:12]}")

        ev = {"target_vocab": t_size, "draft_vocab": d_size,
              "probe_ids_identical": same_ids}
        if t_size != d_size or not same_ids:
            _verdict("rf1_tokenizer", "FAIL",
                     "Tokenisers are NOT interchangeable. Speculative decoding requires "
                     "the draft to propose tokens in the target's own vocabulary; with a "
                     "mismatch every proposal lands in a near-zero-probability region and "
                     "alpha collapses to 0.", ev)
        else:
            _verdict("rf1_tokenizer", "PASS",
                     "Tokenisers agree; vocab mismatch is NOT the cause of alpha=0.", ev)
    except Exception as e:
        _verdict("rf1_tokenizer", "INCONCLUSIVE", f"Could not load tokenisers: {e}")


def check_rf1_acceptance_math(target_id: str, draft_id: str, n_probe: int = 3,
                              gamma: int = 5):
    """Reproduce a few acceptance steps by hand and print p_target/p_draft ratios."""
    _hdr("RF1-b  live acceptance-ratio probe (does the rule ever accept?)")
    try:
        import torch
        import torch.nn.functional as F
        from transformers import AutoModelForCausalLM, AutoTokenizer

        dev = "cuda" if torch.cuda.is_available() else "cpu"
        tok = AutoTokenizer.from_pretrained(target_id)
        if tok.pad_token is None:
            tok.pad_token = tok.eos_token
        target = AutoModelForCausalLM.from_pretrained(
            target_id, torch_dtype=torch.bfloat16).to(dev).eval()
        draft = AutoModelForCausalLM.from_pretrained(
            draft_id, torch_dtype=torch.bfloat16).to(dev).eval()

        prompts = ["Please verify your account.",
                   "Meeting at 3pm as scheduled.",
                   "Congratulations, you won a prize."][:n_probe]

        ratios, accepted, proposed = [], 0, 0
        rng = torch.Generator().manual_seed(42)
        with torch.no_grad():
            for p in prompts:
                seq = tok(p, return_tensors="pt").input_ids.to(dev)
                dtoks, dprobs = [], []
                cur = seq
                for _ in range(gamma):
                    probs = F.softmax(draft(cur).logits[0, -1].float(), -1)
                    tk = int(torch.argmax(probs))
                    dtoks.append(tk); dprobs.append(float(probs[tk]))
                    cur = torch.cat([cur, torch.tensor([[tk]], device=dev)], 1)
                ext = torch.cat([seq, torch.tensor([dtoks], device=dev)], 1)
                tlog = target(ext).logits.float()
                base = seq.shape[1]
                for i, tk in enumerate(dtoks):
                    pt = float(F.softmax(tlog[0, base + i - 1], -1)[tk])
                    pd = dprobs[i]
                    r = pt / (pd + 1e-9)
                    ratios.append(r)
                    proposed += 1
                    u = float(torch.rand(1, generator=rng))
                    if u <= min(1.0, r):
                        accepted += 1

        import statistics
        alpha = accepted / max(1, proposed)
        print(f"  proposed={proposed}  accepted={accepted}  alpha={alpha:.4f}")
        print(f"  p_target/p_draft ratio: min={min(ratios):.4g} "
              f"median={statistics.median(ratios):.4g} max={max(ratios):.4g}")
        n_zero = sum(1 for r in ratios if r < 1e-6)
        print(f"  ratios below 1e-6: {n_zero}/{len(ratios)}")

        ev = {"alpha_probe": round(alpha, 4), "n_proposed": proposed,
              "ratio_min": min(ratios), "ratio_median": statistics.median(ratios),
              "ratio_max": max(ratios), "n_near_zero_ratios": n_zero}

        if alpha == 0.0 and n_zero == len(ratios):
            _verdict("rf1_acceptance", "FAIL",
                     "Every p_target/p_draft ratio is ~0: the target assigns essentially "
                     "zero probability to the draft's argmax tokens. Consistent with a "
                     "vocab/tokeniser mismatch or a draft that is not actually loaded.", ev)
        elif alpha == 0.0:
            _verdict("rf1_acceptance", "FAIL",
                     "Ratios are non-degenerate but nothing was accepted — inspect the "
                     "acceptance rule implementation (rng draw, min(1, ratio) direction).", ev)
        else:
            _verdict("rf1_acceptance", "PASS",
                     f"Acceptance works in isolation (alpha={alpha:.3f}). The 0.0 in the "
                     "released exp6 output therefore comes from the experiment's own code "
                     "path, not from the models.", ev)
        del target, draft
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception as e:
        traceback.print_exc()
        _verdict("rf1_acceptance", "INCONCLUSIVE", f"probe failed: {e}")


# ═════════════════════════════════════════════════════════════════════════════
# RF2 — why did exp5/exp3 collapse to ~chance, and why is F1 constant?
# ═════════════════════════════════════════════════════════════════════════════
def check_rf2_checkpoint_flow(repo_root: Path):
    """Does exp1 persist a trained student, and do exp3/exp5 load it?"""
    _hdr("RF2-a  does the trained student survive from exp1 to exp3/exp5?")
    save_hits, load_hits = [], []
    exp_dir = repo_root / "experiments"
    if not exp_dir.is_dir():
        _verdict("rf2_checkpoint", "INCONCLUSIVE",
                 f"experiments/ not found under {repo_root}")
        return

    save_kw = ("save_pretrained", "torch.save", "state_dict()", "save_checkpoint")
    load_kw = ("from_pretrained(", "load_state_dict", "load_checkpoint")

    for f in sorted(exp_dir.glob("exp*.py")):
        txt = f.read_text(errors="ignore")
        for kw in save_kw:
            if kw in txt:
                save_hits.append((f.name, kw))
        # only count loads that point at a local checkpoint dir, not the HF hub id
        for line in txt.splitlines():
            if any(k in line for k in load_kw) and ("outputs" in line or "checkpoint" in line
                                                    or "student_variant" in line):
                load_hits.append((f.name, line.strip()[:90]))

    print("  checkpoint SAVE sites:")
    for n, kw in save_hits or [("<none>", "")]:
        print(f"    {n}: {kw}")
    print("  checkpoint LOAD sites (local paths only):")
    for n, ln in load_hits or [("<none>", "")]:
        print(f"    {n}: {ln}")

    ckpt_dirs = [p for p in (repo_root / "outputs").glob("**/*")
                 if p.is_dir() and ("checkpoint" in p.name or "student" in p.name)]
    print(f"  checkpoint dirs on disk: {[str(p) for p in ckpt_dirs] or 'none'}")

    ev = {"save_sites": save_hits, "load_sites": load_hits,
          "checkpoint_dirs": [str(p) for p in ckpt_dirs]}

    if not save_hits:
        _verdict("rf2_checkpoint", "FAIL",
                 "No experiment saves a trained student. exp1's fine-tuned weights are "
                 "discarded when the process exits, so exp3/exp5 necessarily evaluate the "
                 "BASE model — which explains F1 ~= 0.67 and accuracy ~= 0.50 everywhere, "
                 "and why the OV-Freeze ablation shows an identical F1 in every row.", ev)
    elif not load_hits:
        _verdict("rf2_checkpoint", "FAIL",
                 "Something is saved but no experiment loads a local checkpoint; "
                 "downstream experiments still run on the base model.", ev)
    else:
        _verdict("rf2_checkpoint", "WARN",
                 "Save and load sites both exist — verify they refer to the same path.", ev)


def check_rf2_constant_f1(results_dir: Path):
    """Confirm numerically that F1 is invariant across ablation conditions."""
    _hdr("RF2-b  is the downstream F1 literally constant across ablation arms?")
    exp3 = sorted(results_dir.glob("exp3_*.json"))
    exp5 = sorted(results_dir.glob("exp5_*.json"))
    if not exp3:
        _verdict("rf2_constant_f1", "INCONCLUSIVE", "no exp3 result found")
        return
    d3 = json.loads(exp3[-1].read_text())
    f1s = []
    for group in ("conditions", "layer_selection", "rho_sweep"):
        for arm, vals in (d3.get(group) or {}).items():
            if isinstance(vals, dict) and vals.get("f1") is not None:
                f1s.append((f"{group}/{arm}", vals["f1"]))
    for name, v in f1s:
        print(f"    {name:32s} F1={v}")
    uniq = sorted({v for _, v in f1s})
    print(f"  distinct F1 values across {len(f1s)} arms: {uniq}")

    exp5_f1 = None
    if exp5:
        d5 = json.loads(exp5[-1].read_text())
        exp5_f1 = (d5.get("taf28k") or {}).get("f1")
        print(f"  exp5 TAF-28k F1 = {exp5_f1}")

    ev = {"n_arms": len(f1s), "distinct_f1": uniq, "exp5_taf28k_f1": exp5_f1}
    if len(uniq) == 1:
        same_as_exp5 = exp5_f1 is not None and abs(uniq[0] - exp5_f1) < 1e-9
        _verdict("rf2_constant_f1", "FAIL",
                 f"F1 is identical ({uniq[0]}) in all {len(f1s)} ablation arms"
                 + (" and equals exp5's base-model F1 — the ablation is not affecting the "
                    "model that gets scored." if same_as_exp5 else "."), ev)
    else:
        _verdict("rf2_constant_f1", "PASS",
                 "F1 varies across arms; the ablation does reach the scored model.", ev)


def check_rf2_prediction_balance(results_dir: Path):
    """accuracy ~= 0.5 with F1 ~= 0.67 is the signature of predicting one class."""
    _hdr("RF2-c  does the model predict a single class? (F1/accuracy signature)")
    rows = []
    for pat, keys in (("exp5_*.json", ("taf28k", "chifraud")),
                      ("exp4_*.json", ("classifiers",))):
        for p in sorted(results_dir.glob(pat)):
            d = json.loads(p.read_text())
            for k in keys:
                node = d.get(k)
                if not isinstance(node, dict):
                    continue
                if k == "classifiers":
                    for clf, v in node.items():
                        rows.append((f"exp4/{clf}", v.get("f1"), v.get("accuracy")))
                else:
                    rows.append((f"exp5/{k}", node.get("f1"), node.get("accuracy")))
            adv = (d.get("advfraud") or {}).get("full_pool")
            if adv:
                rows.append(("exp5/advfraud", adv.get("f1"), adv.get("accuracy")))

    suspicious = []
    for name, f1, acc in rows:
        if f1 is None or acc is None:
            continue
        flag = ""
        # Predicting the majority class inflates F1 while accuracy sits at the prior.
        if acc <= 0.55 and f1 >= 0.60:
            flag = "  <-- degenerate (single-class prediction)"
            suspicious.append(name)
        print(f"    {name:22s} F1={f1:<8} acc={acc:<8}{flag}")

    ev = {"rows": rows, "degenerate": suspicious}
    if suspicious:
        _verdict("rf2_balance", "FAIL",
                 f"{len(suspicious)} evaluation(s) show F1 high with accuracy at chance "
                 f"({', '.join(suspicious)}). The classifier is emitting one label for "
                 "nearly every input; the F1 is an artefact of class prior, not skill.", ev)
    else:
        _verdict("rf2_balance", "PASS", "No degenerate F1/accuracy pairs.", ev)


# ═════════════════════════════════════════════════════════════════════════════
# RF3 — is exp1's near-perfect F1 the result of leakage?
# ═════════════════════════════════════════════════════════════════════════════
def check_rf3_split_integrity(repo_root: Path):
    """Inspect group_split: does it prevent near-duplicate texts spanning the split?"""
    _hdr("RF3-a  train/test split integrity (group_split implementation)")
    data_py = repo_root / "realeval" / "data.py"
    if not data_py.exists():
        _verdict("rf3_split", "INCONCLUSIVE", f"{data_py} not found")
        return
    txt = data_py.read_text(errors="ignore")
    start = txt.find("def group_split")
    if start < 0:
        _verdict("rf3_split", "INCONCLUSIVE", "group_split not defined in data.py")
        return
    body = txt[start:start + 2200]
    print(body[:1400])

    groups_by_hash = "hash" in body or "md5" in body or "sha" in body
    groups_by_text = "set(" in body and "texts" in body
    shuffles = "shuffle" in body or "permutation" in body
    ev = {"groups_by_hash": groups_by_hash, "groups_by_text_identity": groups_by_text,
          "shuffles": shuffles}

    if not (groups_by_hash or groups_by_text):
        _verdict("rf3_split", "WARN",
                 "group_split does not appear to group by text identity or hash. If the "
                 "corpus contains templated/near-duplicate messages, the same message can "
                 "appear on both sides of the split and inflate F1 towards 1.0.", ev)
    else:
        _verdict("rf3_split", "PASS",
                 "group_split groups by text identity/hash before splitting.", ev)


def check_rf3_duplicate_overlap(repo_root: Path, data_root: Path, n_max: int = 4000):
    """Directly measure exact-duplicate overlap between the train and test halves."""
    _hdr("RF3-b  measured duplicate overlap between train and test")
    try:
        sys.path.insert(0, str(repo_root))
        from realeval.data import group_split, load_dataset
        ds = load_dataset("balanced4k", max_samples=n_max)
        texts, labels = ds["texts"], ds["labels"]
        tr_idx, te_idx = group_split(texts, labels, test_ratio=0.2, seed=42)
        tr = {texts[i].strip() for i in tr_idx}
        te = {texts[i].strip() for i in te_idx}
        overlap = tr & te
        print(f"  n_train={len(tr_idx)}  n_test={len(te_idx)}")
        print(f"  unique train texts={len(tr)}  unique test texts={len(te)}")
        print(f"  EXACT duplicate texts on both sides: {len(overlap)}")
        for s in list(overlap)[:5]:
            print(f"    dup: {s[:88]}")

        ratio = len(overlap) / max(1, len(te))
        ev = {"n_train": len(tr_idx), "n_test": len(te_idx),
              "n_overlap": len(overlap), "overlap_ratio_of_test": round(ratio, 4)}
        if ratio > 0.01:
            _verdict("rf3_overlap", "FAIL",
                     f"{len(overlap)} test texts ({ratio:.1%} of the test set) also appear "
                     "verbatim in training. exp1's F1 of 0.9988 is measuring memorisation, "
                     "not generalisation.", ev)
        else:
            _verdict("rf3_overlap", "PASS",
                     "No meaningful exact-duplicate overlap between the halves.", ev)
    except Exception as e:
        traceback.print_exc()
        _verdict("rf3_overlap", "INCONCLUSIVE", f"could not run split: {e}")


def check_rf3_loss_curve(results_dir: Path):
    """A two-order-of-magnitude drop inside one epoch is a leakage/overfit signature."""
    _hdr("RF3-c  exp1 training-loss trajectory shape")
    files = sorted(results_dir.glob("exp1_*.json"))
    if not files:
        _verdict("rf3_curve", "INCONCLUSIVE", "no exp1 result found")
        return
    d = json.loads(files[-1].read_text())
    traj = d.get("trajectory") or []
    for t in traj:
        print(f"    epoch {t.get('epoch')}: ce={t.get('ce')}"
              + (f"  val_ce={t.get('val_ce')}" if "val_ce" in t else ""))
    ces = [t.get("ce") for t in traj if t.get("ce") is not None]
    has_val = any("val_ce" in t for t in traj)
    ev = {"n_epochs": len(traj), "ce_first": ces[0] if ces else None,
          "ce_second": ces[1] if len(ces) > 1 else None,
          "final_f1": d.get("f1"), "has_val_ce": has_val,
          "n_train": d.get("n_train"), "n_test": d.get("n_test")}

    problems = []
    if len(ces) > 1 and ces[0] > 0 and (ces[0] / max(ces[1], 1e-9)) > 50:
        problems.append(f"loss fell {ces[0]/ces[1]:.0f}x between the first two epochs")
    if not has_val:
        problems.append("no validation loss is recorded, so early stopping cannot be justified")
    if (d.get("f1") or 0) > 0.99:
        problems.append(f"final F1={d.get('f1')} is implausibly high for this task")

    if problems:
        _verdict("rf3_curve", "FAIL",
                 "Training curve is consistent with leakage or memorisation: "
                 + "; ".join(problems) + ".", ev)
    else:
        _verdict("rf3_curve", "PASS", "Training curve looks unremarkable.", ev)


# ═════════════════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", type=Path,
                    default=Path("/workspace/H100_package_realeval"))
    ap.add_argument("--results-dir", type=Path, default=Path("results"))
    ap.add_argument("--data-root", type=Path, default=Path("/workspace/datasets"))
    ap.add_argument("--target", default="Qwen/Qwen2.5-0.5B-Instruct")
    ap.add_argument("--draft",  default="Qwen/Qwen2-0.5B")
    ap.add_argument("--only", choices=("rf1", "rf2", "rf3"), default=None)
    ap.add_argument("--out", type=Path, default=Path("diagnosis_report.json"))
    args = ap.parse_args()

    print(f"repo_root   = {args.repo_root}")
    print(f"results_dir = {args.results_dir}")
    print(f"target      = {args.target}")
    print(f"draft       = {args.draft}")

    if args.only in (None, "rf1"):
        check_rf1_tokenizer_compat(args.target, args.draft)
        check_rf1_acceptance_math(args.target, args.draft)
    if args.only in (None, "rf2"):
        check_rf2_checkpoint_flow(args.repo_root)
        check_rf2_constant_f1(args.results_dir)
        check_rf2_prediction_balance(args.results_dir)
    if args.only in (None, "rf3"):
        check_rf3_split_integrity(args.repo_root)
        check_rf3_duplicate_overlap(args.repo_root, args.data_root)
        check_rf3_loss_curve(args.results_dir)

    # ── summary ──
    _hdr("SUMMARY")
    order = {"FAIL": 0, "WARN": 1, "INCONCLUSIVE": 2, "PASS": 3}
    for k, v in sorted(REPORT["checks"].items(), key=lambda kv: order[kv[1]["status"]]):
        print(f"  [{v['status']:12s}] {k}")
    fails = [k for k, v in REPORT["checks"].items() if v["status"] == "FAIL"]
    print(f"\n  {len(fails)} check(s) FAILED: {', '.join(fails) if fails else 'none'}")

    args.out.write_text(json.dumps(REPORT, indent=2, default=str))
    print(f"\nreport -> {args.out}")


if __name__ == "__main__":
    main()
