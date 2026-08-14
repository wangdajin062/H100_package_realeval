"""realeval/audit.py — Reproducibility Audit & Experiment Run Log

Two complementary subsystems:

1. **Audit Log** (outputs/logs/audit.log)
   Records reproduction-critical environment fields: GPU, CUDA, torch, driver,
   dataset, model, seed. Minimal by design — no config details, experiment results,
   or internal events.

2. **Run Log** (outputs/logs/runlog.jsonl)
   Structured JSON Lines log of every experiment run with full provenance:
   git commit, environment snapshot, config hash, seed, timestamps.
   Supports log_run() / read_runlog() for programmatic access.

Usage:
  from realeval.audit import log_environment, log_run, read_runlog, provenance
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from realeval.io.paths import LOGS

ROOT = Path(__file__).resolve().parent.parent
AUDIT_LOG = LOGS / "audit.log"
RUNLOG = LOGS / "runlog.jsonl"

# ── logger singletons ──────────────────────────────────────────────────────────

_audit_logger: logging.Logger | None = None
_runlog_logger: logging.Logger | None = None


def _get_runlog_logger() -> logging.Logger:
    global _runlog_logger
    if _runlog_logger is None:
        _runlog_logger = logging.getLogger("runlog")
    return _runlog_logger


# ── audit log ──────────────────────────────────────────────────────────────────


def reset_audit_logger():
    """Reset the audit logger singleton. Useful for test isolation."""
    global _audit_logger
    if _audit_logger is not None:
        for h in _audit_logger.handlers[:]:
            _audit_logger.removeHandler(h)
            h.close()
    _audit_logger = None


def get_audit_logger() -> logging.Logger:
    """Get or create the audit logger singleton."""
    global _audit_logger
    if _audit_logger is not None:
        return _audit_logger
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    lg = logging.getLogger("audit")
    lg.setLevel(logging.INFO)
    lg.handlers.clear()
    fh = logging.FileHandler(AUDIT_LOG, mode="a", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s [AUDIT] %(message)s"))
    lg.addHandler(fh)
    lg.propagate = False
    _audit_logger = lg
    return lg


def log_environment(config: dict = None):
    """Record reproduction-critical environment fields.

    Delegates to audit.tracker.RunTracker for structured audit output.
    Also writes a summary to the legacy audit log for backward compatibility.
    """
    # Delegate to structured audit tracker (conditional on audit.tracker availability)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    tracker = None
    try:
        from audit.tracker import RunTracker
        tracker = RunTracker("environment")
        tracker.collect_all(config)
        tracker.write_all()
    except ImportError:
        pass  # audit.tracker is an optional dependency; degrade gracefully

    # Legacy log summary (backward compat)
    lg = get_audit_logger()
    lg.info("=== Reproduction Environment ===")
    if tracker is not None:
        lg.info("Structured audit: %s", tracker.run_dir)
        env = tracker._data.get("environment", {})
    else:
        lg.info("Structured audit: unavailable (audit.tracker not installed)")
        env = {}
    lg.info("Python=%s", env.get("python_version", "unknown"))
    lg.info("Platform=%s", env.get("platform", "unknown"))
    lg.info("Torch=%s", env.get("torch_version", "unknown"))
    lg.info("CUDA=%s", env.get("cuda_version", "unknown"))
    hw = tracker._data.get("hardware", {}) if tracker is not None else {}
    gpu_names = hw.get("gpu_names", [])
    if gpu_names:
        lg.info("GPU=%s count=%d", gpu_names[0], hw.get("gpu_count", 0))
    else:
        lg.info("GPU=None")
    lg.info("Driver=%s", env.get("nvidia_driver", "unknown"))
    if config and "data" in config:
        source = config["data"].get("source", "unknown")
        max_s = config["data"].get("max_samples", "all")
        lg.info("Dataset=source=%s max_samples=%s", source, max_s)
    else:
        lg.info("Dataset=unknown")
    if config and "models" in config:
        teacher = config["models"].get("teacher", "unknown")
        student = config["models"].get("student", "unknown")
        lg.info("Model=teacher=%s student=%s", teacher, student)
    else:
        lg.info("Model=unknown")
    # Record the seed base actually in effect. REALEVAL_SEED is not consumed by the
    # experiments (they use config["seed"], default 1000, via seed_base_from_config),
    # so hard-coding "42" here misreported the reproducibility record. Prefer an explicit
    # REALEVAL_SEED override if present, else the config seed base; per-run seeds are base+index.
    if os.environ.get("REALEVAL_SEED"):
        seed = os.environ["REALEVAL_SEED"]
    elif config:
        seed = str(config.get("seed", 1000))
    else:
        seed = "1000"
    lg.info("Seed base=%s (per-run seed = base + seed_index)", seed)
    lg.info("=== End Reproduction Environment ===")


# ── run log: provenance helpers ────────────────────────────────────────────────


def _git_commit() -> str | None:
    """Return the current git commit SHA, or None if not in a git repo."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], timeout=5, stderr=subprocess.DEVNULL,
            cwd=str(ROOT)
        ).decode().strip()
    except Exception:
        return None


def _git_dirty() -> bool | None:
    """Return True if the working tree has uncommitted changes."""
    try:
        out = subprocess.check_output(
            ["git", "status", "--porcelain"], timeout=5, stderr=subprocess.DEVNULL,
            cwd=str(ROOT)
        ).decode().strip()
        return len(out) > 0
    except Exception:
        return None


def _env_snapshot() -> dict:
    """Capture environment: Python, torch, CUDA, driver versions."""
    info = {}
    info["python_version"] = sys.version.split()[0]
    try:
        import torch
        info["torch_version"] = torch.__version__
        info["cuda_available"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            info["cuda_version"] = torch.version.cuda
            info["gpu_count"] = torch.cuda.device_count()
            info["gpu_names"] = [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
    except Exception:
        info["torch_version"] = "not_installed"
    # NVIDIA driver
    try:
        drv = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
            timeout=5, stderr=subprocess.DEVNULL
        ).decode().strip().splitlines()
        info["nvidia_driver"] = drv[0] if drv else None
    except Exception:
        info["nvidia_driver"] = None
    return info


def _config_hash(config: dict) -> str:
    """SHA256 of sorted, JSON-serialized config (stable across runs)."""
    raw = json.dumps(config, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _data_hash(data_paths: list[str] | None = None) -> dict:
    """SHA256 of dataset files. Returns {path: hexdigest[:16]}."""
    if not data_paths:
        return {}
    hashes = {}
    for p in data_paths:
        path = Path(p)
        if not path.exists():
            hashes[str(path)] = None
            continue
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        hashes[str(path)] = h.hexdigest()[:16]
    return hashes


def collect_provenance(config: dict | None = None) -> dict:
    """Collect full reproducibility provenance record.

    Returns a dict with: timestamp, git_commit, git_dirty, env, config_hash, seed.
    """
    prov = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "git_commit": _git_commit(),
        "git_dirty": _git_dirty(),
        "env": _env_snapshot(),
    }
    if config:
        prov["config_hash"] = _config_hash(config)
        prov["seed"] = config.get("reproducibility", {}).get("seed")
    return prov


# Alias for claim_engine compatibility
provenance = collect_provenance


# ── run log: experiment lifecycle ──────────────────────────────────────────────


def log_experiment_start(exp_name: str, config: dict = None):
    """Log the start of an experiment with provenance."""
    logger = _get_runlog_logger()
    logger.info("=== Experiment %s started ===", exp_name)
    prov = collect_provenance(config)
    logger.info("Provenance: git=%s dirty=%s config_hash=%s seed=%s",
                prov.get("git_commit", "?")[:8] if prov.get("git_commit") else "?",
                prov.get("git_dirty", "?"),
                prov.get("config_hash", "?"),
                prov.get("seed", "?"))
    if config:
        logger.info("Config: %s", config)


def log_experiment_end(exp_name: str, result: dict = None):
    """Log the completion of an experiment."""
    logger = _get_runlog_logger()
    logger.info("=== Experiment %s completed ===", exp_name)
    if result:
        logger.info("Result keys: %s", list(result.keys()))


def log_run(experiment: str, config: dict, result: dict, status: str = "completed",
            data_paths: list[str] | None = None):
    """Append a run record to runlog.jsonl with full provenance.

    Args:
        experiment: Experiment name (e.g. 'exp1').
        config: Experiment configuration dict.
        result: Experiment result dict.
        status: 'completed' or 'failed'.
        data_paths: Optional list of dataset file paths for hashing.
    """
    RUNLOG.parent.mkdir(parents=True, exist_ok=True)
    prov = collect_provenance(config)
    if data_paths:
        prov["data_hashes"] = _data_hash(data_paths)
    record = {
        "provenance": prov,
        "experiment": experiment,
        "status": status,
        "config": config,
        "result": result,
    }
    with open(RUNLOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def read_runlog() -> list[dict]:
    """Read all records from the JSON Lines runlog. Returns empty list if file missing."""
    if not RUNLOG.exists():
        return []
    records = []
    with open(RUNLOG, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records
