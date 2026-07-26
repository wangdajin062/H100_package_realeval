"""metrics/base.py — Unified Metric Interface

All metrics implement: compute(y_true, y_pred, **kwargs) → {name: value, ...}
Adding a new metric (BLEU, ROUGE, WER, ...) never requires changing the main pipeline.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any


class Metric(ABC):
    """Abstract metric. name() returns the metric identifier, compute() returns the value.

    y_true and y_pred are optional: latency/throughput/memory metrics ignore them
    and receive their data through **kwargs.
    """
    @staticmethod
    @abstractmethod
    def name() -> str:
        ...

    @abstractmethod
    def compute(self, y_true: list | None = None, y_pred: list | None = None, **kwargs) -> dict[str, float]:
        """Compute the metric. Returns {name: value} dict for composability."""
        ...


def _coerce_labels(y_true: list, y_pred: list) -> tuple[list, list]:
    """Normalize labels to int for type-safe comparison.

    Handles string labels ('1', '0', 'fraud', 'normal'), float labels (1.0, 0.0),
    and already-int labels. Returns two lists of int.
    """
    def _to_int(val):
        if isinstance(val, bool):
            return int(val)
        if isinstance(val, (int, float)):
            return int(val)
        s = str(val).strip().lower()
        if s in ("1", "true", "yes", "fraud", "positive", "pos"):
            return 1
        if s in ("0", "false", "no", "normal", "negative", "neg"):
            return 0
        try:
            return int(float(s))
        except (ValueError, TypeError):
            return -1  # unknown → count as neither tp/fp/fn, letting sklearn handle it
    return [_to_int(v) for v in y_true], [_to_int(v) for v in y_pred]


class Accuracy(Metric):
    @staticmethod
    def name() -> str:
        return "accuracy"

    def compute(self, y_true: list, y_pred: list, **kwargs) -> dict[str, float]:
        if len(y_true) == 0:
            return {"accuracy": 0.0}
        try:
            from sklearn.metrics import accuracy_score
            yt, yp = _coerce_labels(y_true, y_pred)
            score = accuracy_score(yt, yp)
            return {"accuracy": round(float(score), 6)}
        except Exception:
            yt, yp = _coerce_labels(y_true, y_pred)
            correct = sum(1 for t, p in zip(yt, yp) if t == p)
            return {"accuracy": round(correct / len(yt), 6)}


class Precision(Metric):
    """Binary precision. Delegates to sklearn for robust type handling."""
    @staticmethod
    def name() -> str:
        return "precision"

    def compute(self, y_true: list, y_pred: list, **kwargs) -> dict[str, float]:
        if not y_true or not y_pred:
            return {"precision": 0.0}
        try:
            from sklearn.metrics import precision_score
            yt, yp = _coerce_labels(y_true, y_pred)
            score = precision_score(yt, yp, pos_label=1, zero_division=0.0)
            return {"precision": round(float(score), 6)}
        except Exception:
            return {"precision": 0.0}


class Recall(Metric):
    """Binary recall. Delegates to sklearn for robust type handling."""
    @staticmethod
    def name() -> str:
        return "recall"

    def compute(self, y_true: list, y_pred: list, **kwargs) -> dict[str, float]:
        if not y_true or not y_pred:
            return {"recall": 0.0}
        try:
            from sklearn.metrics import recall_score
            yt, yp = _coerce_labels(y_true, y_pred)
            score = recall_score(yt, yp, pos_label=1, zero_division=0.0)
            return {"recall": round(float(score), 6)}
        except Exception:
            return {"recall": 0.0}


class F1Score(Metric):
    @staticmethod
    def name() -> str:
        return "f1"

    def compute(self, y_true: list, y_pred: list, **kwargs) -> dict[str, float]:
        if not y_true or not y_pred:
            return {"f1": 0.0}
        try:
            from sklearn.metrics import f1_score
            yt, yp = _coerce_labels(y_true, y_pred)
            score = f1_score(yt, yp, pos_label=1, zero_division=0.0)
            return {"f1": round(float(score), 6)}
        except Exception:
            return {"f1": 0.0}


class AUCROC(Metric):
    @staticmethod
    def name() -> str:
        return "auc_roc"

    def compute(self, y_true: list, y_pred: list, y_score: list | None = None, **kwargs) -> dict[str, float]:
        if y_score is None:
            return {"auc_roc": 0.0}
        try:
            from sklearn.metrics import roc_auc_score
            return {"auc_roc": round(float(roc_auc_score(y_true, y_score)), 6)}
        except Exception:
            return {"auc_roc": 0.0}


# ── Performance metrics ──

class LatencyMetric(Metric):
    """P50/P90/P99 latency from raw sample timings."""
    @staticmethod
    def name() -> str:
        return "latency"

    def compute(self, y_true: list | None = None, y_pred: list | None = None, latency_samples: list[float] | None = None, **kwargs) -> dict[str, float]:
        if not latency_samples:
            return {"latency_p50_ms": 0.0, "latency_p90_ms": 0.0, "latency_p99_ms": 0.0}
        import numpy as np
        arr = np.array(latency_samples)
        return {
            "latency_p50_ms": round(float(np.percentile(arr, 50)), 3),
            "latency_p90_ms": round(float(np.percentile(arr, 90)), 3),
            "latency_p99_ms": round(float(np.percentile(arr, 99)), 3),
            "latency_mean_ms": round(float(np.mean(arr)), 3),
        }


class ThroughputMetric(Metric):
    @staticmethod
    def name() -> str:
        return "throughput"

    def compute(self, y_true: list | None = None, y_pred: list | None = None, total_samples: int | None = None,
                wall_time_s: float | None = None, **kwargs) -> dict[str, float]:
        if not total_samples or not wall_time_s or wall_time_s <= 0:
            return {"throughput_sps": 0.0}
        return {"throughput_sps": round(total_samples / wall_time_s, 2)}


class MemoryMetric(Metric):
    @staticmethod
    def name() -> str:
        return "memory"

    def compute(self, y_true: list | None = None, y_pred: list | None = None, peak_mem_mb: float | None = None, **kwargs) -> dict[str, float]:
        if peak_mem_mb is None:
            return {"peak_memory_mb": 0.0}
        return {"peak_memory_mb": round(peak_mem_mb, 1)}


# ── Registry ──

_BUILTIN_METRICS: dict[str, type[Metric]] = {
    "accuracy": Accuracy,
    "precision": Precision,
    "recall": Recall,
    "f1": F1Score,
    "auc_roc": AUCROC,
    "latency": LatencyMetric,
    "throughput": ThroughputMetric,
    "memory": MemoryMetric,
}


def get_metric(name: str) -> Metric:
    """Get a metric instance by name. Raises KeyError if not registered."""
    if name not in _BUILTIN_METRICS:
        raise KeyError(f"Unknown metric: {name}. Registered: {list(_BUILTIN_METRICS)}")
    return _BUILTIN_METRICS[name]()


def register_metric(cls: type[Metric]):
    """Register a custom metric. Use as decorator on Metric subclass."""
    _BUILTIN_METRICS[cls.name()] = cls
    return cls


def compute_all(y_true: list, y_pred: list, metric_names: list[str] | None = None, **kwargs) -> dict:
    """Compute all registered (or specified) metrics in one call."""
    names = metric_names or list(_BUILTIN_METRICS)
    results = {}
    for name in names:
        try:
            m = get_metric(name)
            results.update(m.compute(y_true, y_pred, **kwargs))
        except KeyError:
            import logging
            logging.getLogger("metrics").warning("Unknown metric: %s (skipping)", name)
    return results
