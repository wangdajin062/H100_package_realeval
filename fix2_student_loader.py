"""fix2_student_loader.py — Make the trained LoRA adapter reachable from experiments.

Problem
-------
`cluster/train_sft.py` writes a PEFT/LoRA adapter to

    /workspace/outputs/sft_checkpoints/checkpoint-250/
        adapter_config.json
        adapter_model.safetensors   (35 MB)

but a scan of `experiments/*.py` finds **no save sites and no load sites**. Every
downstream experiment therefore evaluates the untuned base model. That single fact
explains the whole cluster of red flags in the 2026-07-22 run:

    exp5  accuracy ~= 0.50 on every corpus        (base model, no task knowledge)
    exp3  F1 identical (0.6744) in all 13 arms    (same base model scored 13 times)
    exp6  alpha = 0.0                             (draft/target both untuned)

Fix
---
This module provides `load_student(...)`, which resolves a `student_variant` name to a
concrete adapter directory, attaches it to the base model, and merges it for inference.
Experiments call it instead of loading the base checkpoint directly.

Variant resolution order (first hit wins):
    1. explicit path passed as `adapter_path`
    2. config["students"][variant]                       (if the config declares one)
    3. $REALEVAL_ADAPTER_ROOT/<variant>/                  (per-variant directory)
    4. $REALEVAL_ADAPTER_ROOT/ latest checkpoint-*        (the SFT default)
    5. base model, with a loud warning                    (never silent)

Usage in an experiment
----------------------
    from fix2_student_loader import load_student

    model, tok = load_student(config, variant="qad_ovf", quantize="int4")

Or wire it into realeval.real_backend so every experiment benefits — see
`patch_real_backend()` at the bottom for the three-line change.

Self-test
---------
    python fix2_student_loader.py --self-test
    python fix2_student_loader.py --list          # show discoverable adapters
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from pathlib import Path

ADAPTER_ROOT = Path(os.environ.get("REALEVAL_ADAPTER_ROOT",
                                   "/workspace/outputs/sft_checkpoints"))
BASE_MODEL_DEFAULT = "Qwen/Qwen2.5-0.5B-Instruct"


# ── discovery ────────────────────────────────────────────────────────────────
def _is_adapter_dir(p: Path) -> bool:
    return (p / "adapter_config.json").is_file()


def _latest_checkpoint(root: Path) -> Path | None:
    """Newest `checkpoint-<step>` directory containing an adapter."""
    if not root.is_dir():
        return None
    cands = [d for d in root.glob("checkpoint-*") if _is_adapter_dir(d)]
    if not cands:
        return root if _is_adapter_dir(root) else None

    def _step(d: Path) -> int:
        try:
            return int(d.name.split("-")[-1])
        except ValueError:
            return -1

    return max(cands, key=_step)


def discover_adapters(root: Path = ADAPTER_ROOT) -> dict[str, Path]:
    """Map a human-readable variant name to an adapter directory."""
    found: dict[str, Path] = {}
    if not root.is_dir():
        return found
    latest = _latest_checkpoint(root)
    if latest:
        found["latest"] = latest
    for d in sorted(root.iterdir()):
        if d.is_dir() and _is_adapter_dir(d):
            found[d.name] = d
    return found


def resolve_adapter(variant: str, config: dict | None = None,
                    adapter_path: str | Path | None = None) -> Path | None:
    """Resolve a variant name to an adapter directory, or None for the base model."""
    if adapter_path:
        p = Path(adapter_path)
        if _is_adapter_dir(p):
            return p
        warnings.warn(f"adapter_path {p} has no adapter_config.json", RuntimeWarning)

    if config:
        declared = (config.get("students") or {}).get(variant)
        if declared:
            p = Path(declared)
            if _is_adapter_dir(p):
                return p
            warnings.warn(f"config students.{variant} -> {p} is not an adapter dir",
                          RuntimeWarning)

    if variant in ("base", None, ""):
        return None

    per_variant = ADAPTER_ROOT / variant
    if _is_adapter_dir(per_variant):
        return per_variant

    latest = _latest_checkpoint(ADAPTER_ROOT)
    if latest:
        return latest

    return None


# ── loading ──────────────────────────────────────────────────────────────────
def load_student(config: dict | None = None,
                 variant: str = "base",
                 quantize: str | None = None,
                 adapter_path: str | Path | None = None,
                 base_model: str | None = None,
                 merge: bool = True):
    """Load the base model plus (optionally) a LoRA adapter for `variant`.

    Returns (model, tokenizer). Raises RuntimeError when a non-base variant is requested
    but no adapter can be found — silently returning the base model is exactly the
    failure mode that produced the 0.6744-everywhere run.
    """
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    base_id = (base_model
               or (config or {}).get("models", {}).get("teacher")
               or BASE_MODEL_DEFAULT)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    # ── quantisation kwargs ──
    kwargs: dict = {"torch_dtype": torch.bfloat16}
    if quantize in ("int4", "nf4"):
        from transformers import BitsAndBytesConfig
        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4" if quantize == "nf4" else "fp4",
            bnb_4bit_compute_dtype=torch.bfloat16)
        kwargs["device_map"] = {"": 0} if device == "cuda" else "cpu"
    elif quantize == "int8":
        from transformers import BitsAndBytesConfig
        kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
        kwargs["device_map"] = {"": 0} if device == "cuda" else "cpu"
    elif quantize == "fp32":
        kwargs["torch_dtype"] = torch.float32

    tok = AutoTokenizer.from_pretrained(base_id)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(base_id, **kwargs)
    if "device_map" not in kwargs:
        model = model.to(device)

    # ── attach adapter ──
    adapter = resolve_adapter(variant, config, adapter_path)
    if adapter is None:
        if variant not in ("base", None, ""):
            raise RuntimeError(
                f"student_variant='{variant}' requested but no LoRA adapter was found "
                f"under {ADAPTER_ROOT}. Train one first (cluster/train_sft.py) or pass "
                f"adapter_path=... explicitly. Refusing to fall back to the base model, "
                f"because that silently produces base-model numbers for every experiment.")
        print(f"[student_loader] variant=base -> {base_id} (no adapter, as requested)")
        return model, tok

    from peft import PeftModel
    print(f"[student_loader] variant={variant} -> base {base_id} + adapter {adapter}")
    model = PeftModel.from_pretrained(model, str(adapter))
    if merge and quantize not in ("int4", "nf4", "int8"):
        # merge_and_unload gives a plain nn.Module (faster inference, no PEFT hooks).
        # Not available for bitsandbytes-quantised bases; keep the wrapper there.
        model = model.merge_and_unload()
        print("[student_loader] adapter merged into base weights")
    model.eval()
    return model, tok


# ── wiring instructions ──────────────────────────────────────────────────────
PATCH_HINT = r'''
Wire into realeval/real_backend.py so every experiment picks the adapter up
--------------------------------------------------------------------------
Find the place inside `real_llm_classify` where the model is loaded, e.g.

    model, tok = models.load_causal_lm(config["models"]["teacher"], quantize=quantize)

and replace it with

    from fix2_student_loader import load_student
    model, tok = load_student(config,
                              variant=config.get("student_variant", "base"),
                              quantize=quantize)

Then declare the variants in config/experiments.yaml:

    students:
      qad_ovf:      /workspace/outputs/sft_checkpoints/checkpoint-250
      qad_no_ovf:   /workspace/outputs/sft_checkpoints_no_ovf/checkpoint-250
      bitdistiller: /workspace/outputs/sft_bitdistiller/checkpoint-250

Any experiment that sets `config["student_variant"]` now evaluates the tuned student.
Experiments that do not set it keep the base-model behaviour explicitly.
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="List discoverable adapters")
    ap.add_argument("--self-test", action="store_true",
                    help="Load base + latest adapter and run one forward pass")
    ap.add_argument("--variant", default="latest")
    ap.add_argument("--hint", action="store_true", help="Print wiring instructions")
    args = ap.parse_args()

    if args.hint:
        print(PATCH_HINT); return

    if args.list or not (args.self_test):
        found = discover_adapters()
        print(f"adapter root: {ADAPTER_ROOT}")
        if not found:
            print("  (none found)")
        for name, p in found.items():
            cfg = {}
            try:
                cfg = json.loads((p / "adapter_config.json").read_text())
            except Exception:
                pass
            print(f"  {name:16s} -> {p}")
            if cfg:
                print(f"      r={cfg.get('r')} alpha={cfg.get('lora_alpha')} "
                      f"targets={cfg.get('target_modules')}")
        if not args.self_test:
            return

    if args.self_test:
        print("\n[self-test] loading base + adapter …")
        model, tok = load_student(variant=args.variant)
        import torch
        enc = tok("Please verify your account immediately.", return_tensors="pt")
        enc = {k: v.to(model.device) for k, v in enc.items()}
        with torch.no_grad():
            out = model(**enc)
        print(f"[self-test] forward OK, logits shape = {tuple(out.logits.shape)}")


if __name__ == "__main__":
    main()
