"""realeval/io/paths.py — 输出目录与路径常量。

所有输出路径集中管理，避免各模块重复计算 ``Path(__file__).resolve().parent.parent``。

``REALEVAL_OUTPUT_ROOT`` 环境变量可把输出根目录重定向到临时位置——测试隔离
（含 runner 子进程）依赖它；未设置时默认 ``<repo>/outputs``，行为与之前一致。
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT: Path = Path(__file__).resolve().parent.parent.parent
OUTDIR: Path = Path(os.environ.get("REALEVAL_OUTPUT_ROOT", str(ROOT / "outputs")))

RESULTS: Path = OUTDIR / "results"
PREDICTIONS: Path = OUTDIR / "predictions"
FIGURES: Path = OUTDIR / "figures"
METRICS_DIR: Path = OUTDIR / "metrics"
TABLES_DIR: Path = OUTDIR / "tables"
ARCHIVE: Path = OUTDIR / "archive"
LOGS: Path = OUTDIR / "logs"
EVIDENCE: Path = OUTDIR / "evidence"
AUDIT_DIR: Path = OUTDIR / "audit"
CLAIMS: Path = OUTDIR / "claims"
MODELS: Path = OUTDIR / "models"

ALL_EXPERIMENTS_FILE: Path = RESULTS / "all_experiments.json"


def get_results_dir() -> Path:
    """返回并确保 ``outputs/results`` 目录存在。"""
    RESULTS.mkdir(parents=True, exist_ok=True)
    return RESULTS
