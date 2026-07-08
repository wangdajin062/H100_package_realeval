"""metrics/base.py — Unified Metric Interface

All metrics implement: compute(y_true, y_pred, **kwargs) → {name: value, ...}
Adding a new metric (BLEU, ROUGE, WER, ...) never requires changing the main pipeline.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any


class Metric(ABC):
    """Abstract metric. name() returns the metric identifier, compute() returns the value."""
    @staticmethod
    @abstractmethod
    def name() -> str:
        ...

    @abstractmethod
    def compute(self, y_true: list, y_pred: list, **kwargs) -> dict[str, float]:
        """Compute the metric. Returns {name: value} dict for composability."""
        ...


class Accuracy(Metric):
    @staticmethod
    def name() -> str:
        return "accuracy"

    def compute(self, y_true: list, y_pred: list, **kwargs) -> dict[str, float]:
        if len(y_true) == 0:
            return {"accuracy": 0.0}
        correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
        return {"accuracy": round(correct / len(y_true), 6)}


class Precision(Metric):
    @staticmethod
    def name() -> str:
        return "precision"

    def compute(self, y_true: list, y_pred: list, **kwargs) -> dict[str, float]:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
        if tp + fp == 0:
            return {"precision": 0.0}
        return {"precision": round(tp / (tp + fp), 6)}


class Recall(Metric):
    @staticmethod
    def name() -> str:
        return "recall"

    def compute(self, y_true: list, y_pred: list, **kwargs) -> dict[str, float]:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
        if tp + fn == 0:
            return {"recall": 0.0}
        return {"recall": round(tp / (tp + fn), 6)}


class F1Score(Metric):
    @staticmethod
    def name() -> str:
        return "f1"

    def compute(self, y_true: list, y_pred: list, **kwargs) -> dict[str, float]:
        prec = Precision().compute(y_true, y_pred)["precision"]
        rec = Recall().compute(y_true, y_pred)["recall"]
        if prec + rec == 0:
            return {"f1": 0.0}
        return {"f1": round(2 * prec * rec / (prec + rec), 6)}


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

    def compute(self, y_true: list, y_pred: list, latency_samples: list[float] | None = None, **kwargs) -> dict[str, float]:
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

    def compute(self, y_true: list, y_pred: list, total_samples: int | None = None,
                wall_time_s: float | None = None, **kwargs) -> dict[str, float]:
        if not total_samples or not wall_time_s or wall_time_s <= 0:
            return {"throughput_sps": 0.0}
        return {"throughput_sps": round(total_samples / wall_time_s, 2)}


class MemoryMetric(Metric):
    @staticmethod
    def name() -> str:
        return "memory"

    def compute(self, y_true: list, y_pred: list, peak_mem_mb: float | None = None, **kwargs) -> dict[str, float]:
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
            pass
    return results
