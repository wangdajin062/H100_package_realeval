"""student_loader.py — resolve a student_variant to a LoRA adapter and load it.

Added by apply_all_fixes.py. Without this, cluster/train_sft.py writes an adapter to
outputs/sft_checkpoints/ that no experiment ever loads, so every downstream experiment
silently scores the untuned base model.
"""
from __future__ import annotations

import os
import warnings
from pathlib import Path

ADAPTER_ROOT = Path(os.environ.get("REALEVAL_ADAPTER_ROOT",
                                   "/workspace/outputs/sft_checkpoints"))
BASE_MODEL_DEFAULT = "Qwen/Qwen2.5-0.5B-Instruct"


def _is_adapter_dir(p: Path) -> bool:
    return (p / "adapter_config.json").is_file()


def _latest_checkpoint(root: Path):
    if not root.is_dir():
        return None
    cands = [d for d in root.glob("checkpoint-*") if _is_adapter_dir(d)]
    if not cands:
        return root if _is_adapter_dir(root) else None

    def _step(d):
        try:
            return int(d.name.split("-")[-1])
        except ValueError:
            return -1
    return max(cands, key=_step)


def discover_adapters(root: Path = ADAPTER_ROOT) -> dict:
    found = {}
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
                    adapter_path=None):
    """Explicit path -> config['students'][variant] -> ROOT/<variant> -> newest ckpt."""
    if adapter_path:
        p = Path(adapter_path)
        if _is_adapter_dir(p):
            return p
        warnings.warn(f"adapter_path {p} has no adapter_config.json", RuntimeWarning)

    if config:
        declared = (config.get("students") or {}).get(variant)
        if declared and _is_adapter_dir(Path(declared)):
            return Path(declared)

    if variant in ("base", None, ""):
        return None

    per_variant = ADAPTER_ROOT / variant
    if _is_adapter_dir(per_variant):
        return per_variant
    return _latest_checkpoint(ADAPTER_ROOT)


def attach_adapter(model, variant: str = "base", config: dict | None = None,
                   adapter_path=None, merge: bool = True, quantize=None):
    """Attach a LoRA adapter to an already-loaded base model.

    Raises when a non-base variant is requested but no adapter exists — silently
    returning the base model is the failure mode that produced identical F1 across
    all thirteen ablation arms.
    """
    adapter = resolve_adapter(variant, config, adapter_path)
    if adapter is None:
        if variant not in ("base", None, ""):
            raise RuntimeError(
                f"student_variant='{variant}' requested but no LoRA adapter found under "
                f"{ADAPTER_ROOT}. Train one (cluster/train_sft.py) or pass adapter_path. "
                "Refusing to fall back to the base model.")
        return model

    from peft import PeftModel
    print(f"[student_loader] variant={variant} + adapter {adapter}")
    model = PeftModel.from_pretrained(model, str(adapter))
    if merge and quantize not in ("int4", "nf4", "int8"):
        model = model.merge_and_unload()
        print("[student_loader] adapter merged")
    return model


def load_student(config: dict | None = None, variant: str = "base",
                 quantize=None, adapter_path=None, base_model=None, merge: bool = True):
    """Load base + adapter in one call. Returns (model, tokenizer)."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    base_id = (base_model or (config or {}).get("models", {}).get("teacher")
               or BASE_MODEL_DEFAULT)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    kwargs = {"torch_dtype": torch.bfloat16}
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

    model = attach_adapter(model, variant, config, adapter_path, merge, quantize)
    model.eval()
    return model, tok
