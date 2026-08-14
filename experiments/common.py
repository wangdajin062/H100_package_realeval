"""experiments/common.py — 实验脚本共享工具集。

消除 14 个实验脚本间的重复代码：
- set_seed(): torch + numpy + cuda 三合一（修复 exp2 遗漏 np.random.seed 的 bug）
- seed_base_from_config(): 统一 seed 基数读取（兼容 claim_engine 注入的 config["seed"]）
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
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Callable, TypeVar

import numpy as np
import torch

from realeval.io.paths import MODELS, SPLITS

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
    split = leakage_safe_split(ds, test_ratio=test_ratio, seed=seed)
    # Persist the held-out test set so downstream eval-only experiments (exp5/13/14)
    # can reuse EXACTLY this partition and never evaluate the exp1-trained model on
    # its own training data (P1-M1). Skip synthetic fallbacks — they carry no
    # cross-experiment identity.
    if not ds.is_synthetic:
        save_split_manifest(dataset_name, split.test_texts)
    return split


# ── Shared leakage-safe split manifest (P1-M1) ──────────────────────────────────
# exp1/2/3/4/9/10/11/12 already split via stratified group_split. exp5/13/14 used a
# positional tail slice, which (a) is not stratified, (b) skips template-group dedup,
# and (c) does not match exp1's random split — so ~80% of the "test" tail actually sat
# in exp1's training set. These helpers give every experiment ONE consistent, leakage-
# safe test partition: prefer exp1's persisted manifest; else a deterministic group_split.

def _split_text_hash(text: str) -> str:
    return hashlib.sha1(str(text).encode("utf-8")).hexdigest()[:16]


def save_split_manifest(dataset_key: str, test_texts: list[str]) -> None:
    """Persist the set of held-out test-sample hashes for *dataset_key*."""
    try:
        SPLITS.mkdir(parents=True, exist_ok=True)
        (SPLITS / f"{dataset_key}.json").write_text(
            json.dumps({"test_hashes": sorted({_split_text_hash(t) for t in test_texts})}),
            encoding="utf-8",
        )
    except OSError as exc:  # manifest is best-effort; never break training on IO error
        logger.warning("Could not write split manifest for %s: %s", dataset_key, exc)


def load_split_manifest(dataset_key: str) -> set[str] | None:
    """Load the held-out test-hash set for *dataset_key*, or None if absent/unreadable."""
    path = SPLITS / f"{dataset_key}.json"
    if not path.exists():
        return None
    try:
        return set(json.loads(path.read_text(encoding="utf-8")).get("test_hashes", []))
    except (json.JSONDecodeError, OSError):
        return None


def leakage_safe_indices(
    texts: list[str], labels: list[Any], *, test_ratio: float = 0.2, seed: int = 42
) -> tuple[list[int], list[int]]:
    """Stratified, template-group-safe (train_idx, test_idx) — the same split exp1 uses."""
    from realeval.data import group_split
    return group_split(texts, labels, test_ratio=test_ratio, seed=seed)


def shared_test_indices(
    dataset_key: str, texts: list[str], labels: list[Any], *,
    test_ratio: float = 0.2, seed: int = 42,
) -> list[int]:
    """Indices of the leakage-safe test partition for *dataset_key*.

    Prefers exp1's persisted held-out set (intersected with the samples actually
    loaded here) so eval never overlaps training; falls back to a deterministic
    group_split when no manifest exists.
    """
    manifest = load_split_manifest(dataset_key)
    if manifest:
        idx = [i for i, t in enumerate(texts) if _split_text_hash(t) in manifest]
        if idx:
            return idx
        logger.warning("Split manifest for %s matched 0 loaded samples; using group_split", dataset_key)
    _, test_idx = leakage_safe_indices(texts, labels, test_ratio=test_ratio, seed=seed)
    return list(test_idx)


def shared_test_split(
    dataset_key: str, texts: list[str], labels: list[Any], *,
    test_ratio: float = 0.2, seed: int = 42,
) -> tuple[list[str], list[Any]]:
    """(test_texts, test_labels) for the leakage-safe test partition of *dataset_key*."""
    idx = shared_test_indices(dataset_key, texts, labels, test_ratio=test_ratio, seed=seed)
    return [texts[i] for i in idx], [labels[i] for i in idx]


def n_seeds_from_config(config: dict[str, Any], exp_id: str) -> int:
    """从 reproducibility.{exp_id}_seeds 读取 seed 数，默认 3。

    兼容现有的 per-experiment 配置键 (exp1_seeds, exp2_seeds, ...)。
    """
    return int(config.get("reproducibility", {}).get(f"{exp_id}_seeds", 3))


def seed_base_from_config(config: dict[str, Any]) -> int:
    """从 config 读取 seed 基数，默认 1000。

    claim_engine 每次重复运行前注入 cfg["seed"] = 42 + s；普通运行无 "seed"
    键时保持默认 1000，保证既有 H100 论文运行结果 bit-identical。
    """
    return int(config.get("seed", 1000))


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
    return MODELS / "exp1_qad"


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
