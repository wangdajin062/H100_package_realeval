"""realeval/io/paths.py — 输出目录与路径常量。

所有输出路径集中管理，避免各模块重复计算 ``Path(__file__).resolve().parent.parent``。
"""
from __future__ import annotations

from pathlib import Path

ROOT: Path = Path(__file__).resolve().parent.parent.parent
OUTDIR: Path = ROOT / "outputs"

RESULTS: Path = OUTDIR / "results"
PREDICTIONS: Path = OUTDIR / "predictions"
FIGURES: Path = OUTDIR / "figures"
METRICS_DIR: Path = OUTDIR / "metrics"
TABLES_DIR: Path = OUTDIR / "tables"
ARCHIVE: Path = OUTDIR / "archive"

ALL_EXPERIMENTS_FILE: Path = RESULTS / "all_experiments.json"


def get_results_dir() -> Path:
    """返回并确保 ``outputs/results`` 目录存在。"""
    RESULTS.mkdir(parents=True, exist_ok=True)
    return RESULTS
