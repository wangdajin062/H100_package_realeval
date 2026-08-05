"""runner/experiment_runner.py — 单实验运行封装。

统一处理：模块导入、显存清理、provenance 记录、结果保存、异常边界。
"""
from __future__ import annotations

import importlib
import logging
from typing import Any

from realeval.io.serialization import save_results
from realeval.runlog import log_experiment_end, log_experiment_start
from utils.logging import get_logger

logger = logging.getLogger("runner.experiment_runner")


def import_experiment(module_name: str) -> Any:
    """按模块名导入实验模块。"""
    return importlib.import_module(f"experiments.{module_name}")


def run_experiment(
    module_name: str,
    short: str,
    config: dict[str, Any],
    *,
    cleanup_gpu: bool = True,
) -> dict[str, Any]:
    """运行单个实验，保存结果，返回结果字典。

    Args:
        module_name: experiments/ 下的模块名（如 ``exp1_qad_production``）。
        short: 实验短 ID（如 ``exp1``）。
        config: 实验配置。
        cleanup_gpu: 是否在运行前后清理 GPU 显存。

    Returns:
        实验结果字典。若实验抛出异常，返回 ``{"experiment": short, "computation": "failed", "error": ...}``。
    """
    exp_logger = get_logger("experiment", short)

    if cleanup_gpu:
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.reset_peak_memory_stats()
        except Exception:
            pass

    log_experiment_start(short, config)
    exp_logger.info("开始运行 %s", short)

    try:
        mod = import_experiment(module_name)
        result = mod.run(config)
        save_results(short, result)
        log_experiment_end(short, result)
        exp_logger.info("完成 %s，结果键：%s", short, sorted(result.keys()))
    except Exception as exc:
        logger.error("实验 %s 失败：%s", short, exc, exc_info=True)
        exp_logger.error("失败：%s", exc)
        result = {"experiment": short, "computation": "failed", "error": str(exc)}
        try:
            save_results(short, result)
        except Exception:
            pass
        log_experiment_end(short, result)

    if cleanup_gpu:
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                peak = torch.cuda.max_memory_allocated() / 1e9
                exp_logger.info("GPU 内存已清理（峰值 %.1fGB）", peak)
        except Exception:
            pass

    return result
