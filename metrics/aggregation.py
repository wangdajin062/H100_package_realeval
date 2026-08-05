"""metrics/aggregation.py — 通用指标聚合工具。

包括多 seed 实验的均值/标准差计算、batch benchmark 表格生成等。
"""
from __future__ import annotations

from typing import Any, Callable, TypeVar

import numpy as np

T = TypeVar("T")


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


def run_multi_seed(
    fn: Callable[[int], T],
    n_seeds: int,
    seed_base: int = 1000,
) -> list[T]:
    """统一多 seed 运行循环。

    Args:
        fn: 接收 seed 并返回单次结果的 callable。
        n_seeds: seed 数量。
        seed_base: seed 起始值，默认 1000（与既有实验脚本一致）。

    Returns:
        每次运行的结果列表。
    """
    return [fn(seed_base + s) for s in range(n_seeds)]


def aggregate_batch_benchmark_csv(
    batch_results: dict[Any, dict[str, Any]],
) -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str]]]:
    """将 batch benchmark 字典转换为 latency/throughput/memory CSV 数据。

    Args:
        batch_results: ``{batch_size: {latency_p50_ms, throughput_sps, peak_mem_mb}}``。

    Returns:
        (latency_rows, throughput_rows, memory_rows)，每项为 (header, body) 元组
        的简化表示；实际写 CSV 由调用方负责。
    """
    latency_rows = []
    throughput_rows = []
    memory_rows = []
    for bs, r in sorted(batch_results.items()):
        latency_rows.append((str(bs), str(r.get("latency_p50_ms", "")), str(r.get("latency_p90_ms", "")), str(r.get("latency_p99_ms", ""))))
        throughput_rows.append((str(bs), str(r.get("throughput_sps", ""))))
        memory_rows.append((str(bs), str(r.get("peak_mem_mb", ""))))
    return latency_rows, throughput_rows, memory_rows
