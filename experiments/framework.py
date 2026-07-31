"""experiments/framework.py — 实验共享运行时框架

集中处理实验公共关切：
- smoke/paper 模式分发
- 数据集加载回退链
- 防泄漏训练/测试分割
- 结果 schema 合规检查
- 结构化日志配置
- 统一错误处理
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
    """实验失败 schema 或运行时检查时抛出。"""


@dataclass(frozen=True)
class TextDataset:
    """文本分类数据集载体。"""
    texts: list[str]
    labels: list[int]


@dataclass(frozen=True)
class DatasetSplit:
    """实验使用的训练/测试分割。"""
    train_texts: list[str]
    train_labels: list[int]
    test_texts: list[str]
    test_labels: list[int]


def configure_logging(level: int = logging.INFO) -> None:
    """一次性配置控制台 + 文件双路日志。"""
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


def load_first_nonempty(
    loaders: Sequence[Callable[[], dict[str, Any]]],
    synthetic_loader: Callable[[], dict[str, Any]],
) -> TextDataset:
    """按顺序尝试各 loader，返回第一个非空数据集；全部失败则使用合成数据。"""
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
        raise ExperimentRuntimeError("所有加载器（含合成）均返回空数据集")
    return TextDataset(texts=texts, labels=labels)


def leakage_safe_split(
    dataset: TextDataset,
    test_ratio: float = 0.2,
    seed: int = 42,
) -> DatasetSplit:
    """基于分组的训练/测试分割，避免模板泄漏。"""
    from realeval.data import group_split

    train_idx, test_idx = group_split(dataset.texts, dataset.labels,
                                      test_ratio=test_ratio, seed=seed)
    return DatasetSplit(
        train_texts=[dataset.texts[i] for i in train_idx],
        train_labels=[int(dataset.labels[i]) for i in train_idx],
        test_texts=[dataset.texts[i] for i in test_idx],
        test_labels=[int(dataset.labels[i]) for i in test_idx],
    )


def pre_run_validation(config: dict[str, Any], exp_id: str) -> None:
    """H100 实验执行前的预检查。

    验证项：GPU 显存是否充足、模型资产是否可用。
    smoke 模式下跳过全部 H100 检查。

    Raises:
        ExperimentRuntimeError: 任一检查不通过时抛出。
    """
    if bool(config.get("_smoke", False)):
        return

    try:
        import torch
        if torch.cuda.is_available():
            gpu_mem_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
            free_mem_gb = torch.cuda.mem_get_info()[0] / 1e9
            if free_mem_gb < 35.0:
                raise ExperimentRuntimeError(
                    f"{exp_id}：GPU 显存不足（{free_mem_gb:.1f}GB 可用，需要 35GB）。"
                    "请清理缓存或重启 GPU。"
                )
            logger.info("%s：GPU 显存检查通过（%.1f/%.1f GB 可用）",
                        exp_id, free_mem_gb, gpu_mem_gb)
    except ExperimentRuntimeError:
        raise
    except Exception as exc:
        logger.warning("%s：无法检查 GPU 显存：%s", exp_id, exc)

    from realeval import models
    if not models.models_available(config):
        raise ExperimentRuntimeError(
            f"{exp_id}：模型权重不可用。请检查 models_root() 和 H100 挂载点。"
        )
    logger.info("%s：模型资产检查通过", exp_id)


def run_with_mode(
    exp_id: str,
    config: dict[str, Any],
    run_paper: Callable[[dict[str, Any]], dict[str, Any]],
    run_smoke: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    """优先运行 paper 路径，不可用时回退到 smoke 路径。

    预检查确保 H100 安全性后再执行高代价计算。
    """
    from realeval.real_backend import run_paper_safe

    pre_run_validation(config, exp_id)

    try:
        paper_result = run_paper_safe(bool(config.get("_smoke", False)), config, run_paper)
        if paper_result is not None:
            return ensure_result_contract(exp_id, paper_result)
        return ensure_result_contract(exp_id, run_smoke(config))
    except Exception as exc:
        raise ExperimentRuntimeError(f"{exp_id} 运行失败：{exc}") from exc


def ensure_result_contract(exp_id: str, result: dict[str, Any]) -> dict[str, Any]:
    """规范化并验证顶层结果合约。

    Raises:
        ExperimentRuntimeError: result 不满足最小合约要求时抛出。
    """
    if not isinstance(result, dict):
        raise ExperimentRuntimeError(
            f"{exp_id} 结果必须为 dict，实际得到 {type(result).__name__}"
        )

    result.setdefault("experiment", exp_id)
    result.setdefault("computation", "unknown")

    if result.get("experiment") != exp_id:
        raise ExperimentRuntimeError(
            f"{exp_id} 结果中 experiment={result.get('experiment')!r} 与期望不符"
        )
    if not isinstance(result.get("computation"), str) or not result["computation"]:
        raise ExperimentRuntimeError(f"{exp_id} 缺少非空 computation 字段")

    return result


def quantile_ms(values_ms: Iterable[float], q: float) -> float:
    """计算毫秒单位延迟的分位数（q 取 0-100）。"""
    import numpy as np
    return float(np.percentile(list(values_ms), q))
