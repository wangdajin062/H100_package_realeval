"""realeval/audit.py — Minimal Audit Log for Reproducibility

Only records:
  - GPU model/name
  - CUDA version
  - Torch version
  - NVIDIA Driver version
  - Dataset name(s)
  - Model name(s)
  - Random seed(s)

Writes to outputs/logs/audit.log (append). Does NOT record config details,
experiment results, or internal events — those have no reproduction value.
"""
from __future__ import annotations
import logging
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT_LOG = ROOT / "outputs" / "logs" / "audit.log"

_logger: logging.Logger | None = None


def reset_audit_logger():
    """Reset the audit logger singleton. Useful for test isolation."""
    global _logger
    if _logger is not None:
        for h in _logger.handlers[:]:
            _logger.removeHandler(h)
            h.close()
    _logger = None


def get_audit_logger() -> logging.Logger:
    """Get or create the audit logger singleton."""
    global _logger
    if _logger is not None:
        return _logger
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    lg = logging.getLogger("audit")
    lg.setLevel(logging.INFO)
    lg.handlers.clear()
    fh = logging.FileHandler(AUDIT_LOG, mode="a", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s [AUDIT] %(message)s"))
    lg.addHandler(fh)
    lg.propagate = False
    _logger = lg
    return lg


def log_environment(config: dict = None):
    """Record reproduction-critical environment fields.

    Delegates to audit.tracker.RunTracker for structured audit output.
    Also writes a summary to the legacy audit log for backward compatibility.
    """
    import os
    import sys

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
    seed = os.environ.get("REALEVAL_SEED", "42")
    lg.info("Seed=%s", seed)
    lg.info("=== End Reproduction Environment ===")
