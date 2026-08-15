"""metrics — 指标提取、聚合与字段合约校验。

本包负责从实验结果字典中提取 headline 指标、校验图像脚本字段合约、
以及多 seed / batch benchmark 等通用聚合逻辑。
"""
from __future__ import annotations

from metrics.aggregation import (
    aggregate_seed_results,
)
from metrics.contract import (
    EXPECTED_FIELDS,
    check_alignment,
    print_alignment_report,
    validate_latest_results,
    validate_result,
)
from metrics.extraction import extract_headline

__all__ = [
    "EXPECTED_FIELDS",
    "validate_result",
    "validate_latest_results",
    "check_alignment",
    "print_alignment_report",
    "extract_headline",
    "aggregate_seed_results",
]
