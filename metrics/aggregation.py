"""metrics/aggregation.py — 通用指标聚合工具。

包括多 seed 实验的均值/标准差计算、batch benchmark 表格生成等。
"""
from __future__ import annotations

from typing import Any

import numpy as np


def multi_seed_std(values: list[float]) -> float | None:
    """多 seed 的样本标准差（ddof=1）。单 seed 返回 None。"""
    if len(values) <= 1:
        return None
    return round(float(np.std(values, ddof=1)), 4)


def aggregate_seed_results(
    values: list[float],
    *,
    ndigits: int = 4,
) -> dict[str, Any]:
    """聚合多 seed 标量结果。

    Returns:
        ``{"mean": ..., "std": ..., "list": [...], "n_seeds": ...}``
    """
    return {
        "mean": round(float(np.mean(values)), ndigits),
        "std": multi_seed_std(values),
        "list": [round(v, ndigits) for v in values],
        "n_seeds": len(values),
    }
