"""runner/orchestrator.py — 实验编排器。

负责多实验的顺序调度、运行前归档、结果归并、resume 与字段对齐校验。
"""
from __future__ import annotations

import json
import logging
from typing import Any

from realeval.io.archive import archive_if_needed
from realeval.io.paths import RESULTS as RESULTS_DIR
from realeval.io.serialization import save_all_results
from metrics.contract import check_alignment, print_alignment_report
from runner.experiment_runner import run_experiment
from runner.registry import EXPERIMENTS, SHORT_TO_FULL

logger = logging.getLogger("runner.orchestrator")


def _load_existing(short: str) -> dict[str, Any] | None:
    """加载某个实验最新的已有结果（用于 --resume）。"""
    files = sorted(RESULTS_DIR.glob(f"{short}_*.json"))
    if not files:
        return None
    try:
        return json.loads(files[-1].read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def run_selected(
    config: dict[str, Any],
    selected: list[str],
    *,
    resume: bool = False,
    no_archive: bool = False,
    aggregate: bool = True,
) -> dict[str, Any]:
    """运行指定实验列表。

    Args:
        config: 实验配置。
        selected: 实验短 ID 列表。
        resume: 是否跳过已有结果的实验。
        no_archive: 是否跳过运行前归档。
        aggregate: 是否在运行结束后写入 ``all_experiments.json``。

    Returns:
        ``{exp_short: result}`` 字典。
    """
    if not no_archive:
        try:
            archived = archive_if_needed()
            if archived:
                logger.info("旧实验结果已归档至：%s", archived)
        except Exception as exc:
            logger.warning("归档步骤失败（继续运行）：%s", exc)

    results: dict[str, Any] = {}
    for entry in EXPERIMENTS:
        if entry.short not in selected:
            continue
        if resume:
            existing = _load_existing(entry.short)
            # Only reuse a genuinely successful prior run. A result marked
            # computation="failed" (see experiment_runner) must be re-run, not
            # skipped — otherwise --resume would freeze the failure into
            # all_experiments.json.
            if existing is not None and str(existing.get("computation", "")) != "failed":
                results[entry.short] = existing
                logger.info("跳过 %s（已有结果）", entry.short)
                continue
            if existing is not None:
                logger.info("重跑 %s（上次结果为 failed，不复用）", entry.short)
        logger.info("运行 %s：%s", entry.short, entry.description)
        results[entry.short] = run_experiment(entry.module, entry.short, config)

    if aggregate and results:
        save_all_results(results)

    return results


def run_all(
    config: dict[str, Any],
    *,
    resume: bool = False,
    no_archive: bool = False,
    validate_alignment: bool = True,
) -> dict[str, Any]:
    """运行全部 14 个实验。

    Args:
        config: 实验配置。
        resume: 是否跳过已有结果的实验。
        no_archive: 是否跳过运行前归档。
        validate_alignment: 是否在运行后自动执行字段对齐校验。

    Returns:
        ``{exp_short: result}`` 字典。
    """
    selected = [e.short for e in EXPERIMENTS]
    results = run_selected(
        config,
        selected,
        resume=resume,
        no_archive=no_archive,
        aggregate=True,
    )

    if validate_alignment:
        try:
            logger.info("运行字段对齐校验...")
            report = check_alignment(list(results.keys()))
            failed = print_alignment_report(report)
            if failed:
                logger.warning("部分实验字段未对齐图像脚本——运行 --align 查看详情")
            else:
                logger.info("所有字段对齐通过")
        except Exception as exc:
            logger.warning("对齐校验失败（非致命）：%s", exc)

    return results
