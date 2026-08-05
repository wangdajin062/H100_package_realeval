"""experiments/common.py — 实验脚本共享工具集。

消除 14 个实验脚本间的重复代码：
- set_seed(): torch + numpy + cuda 三合一（修复 exp2 遗漏 np.random.seed 的 bug）
- load_and_split_dataset(): 统一数据加载 + 防泄漏分割
- n_seeds_from_config(): 统一 multi-seed 计数读取
- run_multi_seed() / aggregate_seed_results(): 多 seed 运行与聚合
- multi_seed_std(): 多 seed 标准差
- build_variant_result(): 统一 variant / scheme / condition 结果结构
- config_override(): deepcopy + merge
- resolve_qad_path(): QAD 模型路径解析
"""
from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any, Callable, TypeVar

import numpy as np
import torch

from experiments.framework import (
    DatasetSplit,
    TextDataset,
    leakage_safe_split,
    load_first_nonempty,
)
from metrics.aggregation import (
    aggregate_seed_results as _aggregate_seed_results,
    multi_seed_std,
    run_multi_seed,
)

logger = logging.getLogger("common")

T = TypeVar("T")


def set_seed(seed: int) -> None:
    """torch + numpy + cuda 三合一 seed 设置."""
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    np.random.seed(seed)


def load_and_split_dataset(
    config: dict[str, Any],
    default_dataset: str = "taf28k",
    default_max_samples: int | None = None,
    test_ratio: float = 0.2,
    seed: int = 42,
    synthetic_n: int = 200,
) -> DatasetSplit:
    """统一的数据加载 + 防泄漏分割。

    按顺序尝试真实数据加载器，全部失败则回退到合成数据。
    """
    from realeval import data as realeval_data

    dataset_name = config.get("data", {}).get("dataset", default_dataset)
    max_samples = config.get("data", {}).get("max_samples", default_max_samples)
    ds: TextDataset = load_first_nonempty(
        loaders=[lambda: realeval_data.load_dataset(dataset_name, max_samples=max_samples)],
        synthetic_loader=lambda: realeval_data.load_synthetic(n=synthetic_n),
    )
    return leakage_safe_split(ds, test_ratio=test_ratio, seed=seed)


def n_seeds_from_config(config: dict[str, Any], exp_id: str) -> int:
    """从 reproducibility.{exp_id}_seeds 读取 seed 数，默认 3。

    兼容现有的 per-experiment 配置键 (exp1_seeds, exp2_seeds, ...)。
    """
    return int(config.get("reproducibility", {}).get(f"{exp_id}_seeds", 3))


def multi_seed_std(values: list[float]) -> float | None:
    """多 seed 的样本标准差（ddof=1）。单 seed 返回 None。"""
    if len(values) <= 1:
        return None
    return round(float(np.std(values, ddof=1)), 4)


def config_override(config: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    """deepcopy config 并递归 merge overrides 到指定 section。

    用法: config_override(config, training={"epochs": 3})
    """
    cfg = copy.deepcopy(config)
    for section, updates in overrides.items():
        cfg.setdefault(section, {}).update(updates)
    return cfg


def resolve_qad_path() -> Path:
    """解析 exp1 产出的 QAD 模型路径。"""
    return Path(__file__).resolve().parent.parent / "outputs" / "models" / "exp1_qad"


def aggregate_seed_results(
    values: list[float],
    *,
    ndigits: int = 4,
) -> dict[str, Any]:
    """聚合多 seed 标量结果，返回统一结构。

    Returns:
        ``{"mean": ..., "std": ..., "list": [...], "n_seeds": ...}``
    """
    return _aggregate_seed_results(values, ndigits=ndigits)


def build_variant_result(
    values: list[float],
    extra: dict[str, Any] | None = None,
    *,
    ndigits: int = 4,
) -> dict[str, Any]:
    """构造统一 variant / scheme / condition 结果字典。

    Args:
        values: 多 seed 的标量结果列表（如 F1 列表）。
        extra: 需要额外合并的字段（如 ``{"kl_final": ...}``）。
        ndigits: 均值保留小数位数。

    Returns:
        ``{"f1": mean, "std": std, "f1_list": [...], "n_seeds": n, **extra}``
    """
    agg = aggregate_seed_results(values, ndigits=ndigits)
    out: dict[str, Any] = {
        "f1": agg["mean"],
        "std": agg["std"],
        "f1_list": agg["list"],
        "n_seeds": agg["n_seeds"],
    }
    if extra:
        out.update(extra)
    return out
