"""student_loader.py — resolve a student_variant to a LoRA adapter and load it.

Added by apply_all_fixes.py. Without this, cluster/train_sft.py writes an adapter to
outputs/sft_checkpoints/ that no experiment ever loads, so every downstream experiment
silently scores the untuned base model.
"""
from __future__ import annotations

import logging
import os
import warnings
from pathlib import Path

from realeval.real_backend import AssetsUnavailable

logger = logging.getLogger("student_loader")

# Adapter root resolution:
#   1. REALEVAL_ADAPTER_ROOT environment variable
#   2. /workspace/outputs/sft_checkpoints (RunPod default)
#   3. Package-relative outputs/sft_checkpoints (local sandbox fallback)
_ADAPTER_ROOT_DEFAULT = Path("/workspace/outputs/sft_checkpoints")
if not _ADAPTER_ROOT_DEFAULT.is_dir() and not any(os.environ.get(m) for m in
    ("RUNPOD_POD_ID", "RUNPOD_POD_HOSTNAME", "RUNPOD_API_KEY")):
    # 本地回退遵循 REALEVAL_OUTPUT_ROOT（测试隔离）；延迟导入避免包初始化循环
    from realeval.io.paths import OUTDIR
    _ADAPTER_ROOT_DEFAULT = OUTDIR / "sft_checkpoints"
ADAPTER_ROOT = Path(os.environ.get("REALEVAL_ADAPTER_ROOT", str(_ADAPTER_ROOT_DEFAULT)))


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
    # No adapter dir for this variant: return None so the caller raises instead of
    # attaching the WRONG variant's newest checkpoint. (Falling back to the latest
    # checkpoint here silently swapped the failure mode from "base used as finetuned"
    # to "wrong adapter attached" — audit P2-12.)
    logger.warning("No adapter dir for variant %r under %s; no fallback (returning None)", variant, ADAPTER_ROOT)
    return None


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
            raise AssetsUnavailable(
                f"student_variant='{variant}' requested but no LoRA adapter found under "
                f"{ADAPTER_ROOT}. Train one (cluster/train_sft.py) or pass adapter_path.")
        return model

    from peft import PeftModel
    print(f"[student_loader] variant={variant} + adapter {adapter}")
    model = PeftModel.from_pretrained(model, str(adapter))
    if merge and quantize not in ("int4", "nf4", "int8"):
        model = model.merge_and_unload()
        print("[student_loader] adapter merged")
    return model
