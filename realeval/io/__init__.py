"""realeval/io — 配置加载、结果序列化、路径管理与归档清理。

本包是实验侧所有磁盘 I/O 的唯一入口。其他模块应通过
``from realeval.io import load_config, save_results, archive_if_needed`` 使用，
而非直接操作 YAML/JSON 文件。
"""
from __future__ import annotations

from realeval.io.archive import archive_if_needed, clear_outputs
from realeval.io.paths import (
    ALL_EXPERIMENTS_FILE,
    ARCHIVE,
    FIGURES,
    METRICS_DIR,
    OUTDIR,
    PREDICTIONS,
    RESULTS,
    ROOT,
    TABLES_DIR,
    get_results_dir,
)
from realeval.io.serialization import (
    load_all_results,
    load_config,
    save_all_results,
    save_results,
)

__all__ = [
    "ROOT",
    "OUTDIR",
    "RESULTS",
    "PREDICTIONS",
    "FIGURES",
    "METRICS_DIR",
    "TABLES_DIR",
    "ARCHIVE",
    "ALL_EXPERIMENTS_FILE",
    "get_results_dir",
    "load_config",
    "load_all_results",
    "save_results",
    "save_all_results",
    "archive_if_needed",
    "clear_outputs",
]
