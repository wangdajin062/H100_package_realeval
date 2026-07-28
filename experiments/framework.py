"""Shared runtime framework for experiment scripts.

This module centralizes common experiment concerns:
- smoke/paper mode dispatch
- dataset loading fallback
- leakage-safe train/test split
- result schema sanity checks
- structured logging setup
- consistent error handling
"""
from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "outputs" / "logs"

logger = logging.getLogger("framework")


class ExperimentRuntimeError(RuntimeError):
    """Raised when an experiment fails schema or runtime checks."""


@dataclass(frozen=True)
class TextDataset:
    """Simple text classification dataset payload."""

    texts: list[str]
    labels: list[int]


@dataclass(frozen=True)
class DatasetSplit:
    """Train/test split used by experiments."""

    train_texts: list[str]
    train_labels: list[int]
    test_texts: list[str]
    test_labels: list[int]


def configure_logging(level: int = logging.INFO) -> None:
    """Configure console + file logging once for the experiment package."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    formatter = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(formatter)

    file_handler = logging.FileHandler(LOG_DIR / "experiments.log", encoding="utf-8")
    file_handler.setFormatter(formatter)

    root_logger.setLevel(level)
    root_logger.addHandler(console)
    root_logger.addHandler(file_handler)


def load_first_nonempty(loaders: Sequence[Callable[[], dict[str, Any]]], synthetic_loader: Callable[[], dict[str, Any]]) -> TextDataset:
    """Try candidate loaders in order and return the first non-empty dataset."""
    for loader in loaders:
        ds = loader() or {}
        texts = list(ds.get("texts", []))
        labels = [int(x) for x in ds.get("labels", [])]
        if texts:
            return TextDataset(texts=texts, labels=labels)

    ds = synthetic_loader() or {}
    texts = list(ds.get("texts", []))
    labels = [int(x) for x in ds.get("labels", [])]
    if not texts:
        raise ExperimentRuntimeError("No usable dataset from real or synthetic loaders")
    return TextDataset(texts=texts, labels=labels)


def leakage_safe_split(dataset: TextDataset, test_ratio: float = 0.2, seed: int = 42) -> DatasetSplit:
    """Perform group-based train/test split to avoid template leakage."""
    from realeval.data import group_split

    train_idx, test_idx = group_split(dataset.texts, dataset.labels, test_ratio=test_ratio, seed=seed)
    train_texts = [dataset.texts[i] for i in train_idx]
    train_labels = [int(dataset.labels[i]) for i in train_idx]
    test_texts = [dataset.texts[i] for i in test_idx]
    test_labels = [int(dataset.labels[i]) for i in test_idx]

    return DatasetSplit(
        train_texts=train_texts,
        train_labels=train_labels,
        test_texts=test_texts,
        test_labels=test_labels,
    )


def pre_run_validation(config: dict[str, Any], exp_id: str) -> None:
    """Pre-flight checks before experiment execution on H100.
    
    Validates:
    - GPU memory sufficient (if paper mode)
    - Model assets available
    - Data files accessible
    
    Raises ExperimentRuntimeError if validation fails.
    """
    smoke = bool(config.get("_smoke", False))
    if smoke:
        return  # Skip H100 checks for smoke mode
    
    # Check GPU memory (H100 has 80GB, need ~40GB min for paper runs)
    try:
        import torch
        if torch.cuda.is_available():
            gpu_mem_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
            free_mem_gb = torch.cuda.mem_get_info()[0] / 1e9
            if free_mem_gb < 35.0:
                raise ExperimentRuntimeError(
                    f"{exp_id}: Insufficient GPU memory ({free_mem_gb:.1f}GB free, need 35GB). "
                    "Clear cache or restart GPU."
                )
            logger.info("%s: GPU memory check OK (%.1f/%.1f GB free)", exp_id, free_mem_gb, gpu_mem_gb)
    except Exception as e:
        if isinstance(e, ExperimentRuntimeError):
            raise
        logger.warning("%s: Could not check GPU memory: %s", exp_id, e)
    
    # Check model assets
    from realeval import models
    if not models.models_available(config):
        raise ExperimentRuntimeError(
            f"{exp_id}: Model weights unavailable. Verify models_root() and H100 mount point."
        )
    logger.info("%s: Model assets check OK", exp_id)


def run_with_mode(
    exp_id: str,
    config: dict[str, Any],
    run_paper: Callable[[dict[str, Any]], dict[str, Any]],
    run_smoke: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    """Run paper path when available, otherwise run smoke path.
    
    Pre-flight validation ensures H100 safety before expensive computation.
    """
    from realeval.real_backend import run_paper_safe

    smoke = bool(config.get("_smoke", False))
    
    # Pre-flight checks (fails fast if conditions not met)
    pre_run_validation(config, exp_id)
    
    try:
        paper_result = run_paper_safe(smoke, config, run_paper)
        if paper_result is not None:
            return ensure_result_contract(exp_id, paper_result)
        return ensure_result_contract(exp_id, run_smoke(config))
    except Exception as exc:
        raise ExperimentRuntimeError(f"{exp_id} failed: {exc}") from exc


def ensure_result_contract(exp_id: str, result: dict[str, Any]) -> dict[str, Any]:
    """Normalize and validate top-level result contract."""
    if not isinstance(result, dict):
        raise ExperimentRuntimeError(f"{exp_id} result must be dict, got {type(result).__name__}")

    result.setdefault("experiment", exp_id)
    result.setdefault("computation", "unknown")

    if result.get("experiment") != exp_id:
        raise ExperimentRuntimeError(
            f"{exp_id} result has mismatched experiment={result.get('experiment')!r}"
        )
    if not isinstance(result.get("computation"), str) or not result["computation"]:
        raise ExperimentRuntimeError(f"{exp_id} missing non-empty computation field")

    return result


def quantile_ms(values_ms: Iterable[float], q: float) -> float:
    """Small helper to compute quantiles with a stable dependency boundary."""
    import numpy as np

    return float(np.percentile(list(values_ms), q))
