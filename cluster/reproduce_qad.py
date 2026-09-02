#!/usr/bin/env python
"""reproduce_qad.py — reproducible NVFP4 QAD training + sha256 manifest (R1 A-road).

Produces the headline QAD student (Table 3/4, F1=0.923 etc.) through the SAME code
path as exp1 (``real_qad_distill_train``: nvfp4 QAT/NBE, pure-KL, OV-Freeze), pins the
seed, then records a sha256 manifest + full hyper-parameter snapshot + git commit so
the checkpoint is reproducible from a clean clone.

This closes the R1 gap: ``config/experiments.yaml`` previously pointed the PTQ student
adapter at a manual ``/workspace/outputs/lora_manual/best`` with no committed
reproduction record. The NVFP4 (headline) path was always reproducible via exp1's
``save_name="exp1_qad"`` — this script now records its sha256 + commit pointer.

Usage (RunPod /workspace):
    PYTHONPATH=/workspace /workspace/venv/bin/python cluster/reproduce_qad.py
"""
from __future__ import annotations
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _sha256_dir(d: Path) -> str:
    """Deterministic sha256 over a checkpoint directory (sorted relative paths + file digests)."""
    h = hashlib.sha256()
    files = sorted(p for p in d.rglob("*") if p.is_file() and p.name != "repro_manifest.json")
    for f in files:
        h.update(f.relative_to(d).as_posix().encode())
        h.update(b"\0")
        h.update(hashlib.sha256(f.read_bytes()).digest())
    return h.hexdigest()


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True).strip()
    except Exception:
        return "unknown"


def _git_status() -> str:
    """Short porcelain status so the manifest records a dirty tree (uncommitted files)."""
    try:
        return subprocess.check_output(["git", "status", "--porcelain"], cwd=str(ROOT), text=True).strip() or "clean"
    except Exception:
        return "unknown"


def main() -> None:
    from experiments.common import set_seed, seed_base_from_config
    from config import load_config
    from realeval.io.paths import MODELS
    from experiments import exp1_qad_production as exp1

    config = load_config(str(ROOT / "config" / "experiments.yaml"))
    seed_base = seed_base_from_config(config)  # matches exp1's seed-0 run exactly
    set_seed(seed_base)

    print(f"[reproduce_qad] seed_base={seed_base} "
          f"quantize={config['training']['quantize']} "
          f"epochs={config['training']['epochs']} lr={config['training']['learning_rate']}")

    result = exp1.run(config)

    save_dir = MODELS / "exp1_qad"
    if not save_dir.is_dir():
        print("[reproduce_qad] ERROR: checkpoint not saved by exp1 (save_name='exp1_qad')")
        sys.exit(1)
    digest = _sha256_dir(save_dir)

    manifest = {
        "checkpoint": str(save_dir),
        "sha256": digest,
        "sha256_note": "digest covers the checkpoint directory EXCLUDING repro_manifest.json, so re-runs do not self-invalidate",
        "git_commit": _git_commit(),
        "git_status": _git_status(),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "seed_base": seed_base,
        "config": {
            "models": config.get("models"),
            "training": config.get("training"),
            "distillation": config.get("distillation"),
            "data": config.get("data"),
        },
        "result": {k: result[k] for k in (
            "f1", "accuracy", "kl_final", "kl_converged", "drift_pct_final",
            "snr_min", "snr_max", "n_train", "n_test", "is_synthetic") if k in result},
    }
    out = save_dir / "repro_manifest.json"
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[reproduce_qad] F1={result.get('f1')}  sha256={digest[:16]}…  manifest -> {out}")


if __name__ == "__main__":
    main()
