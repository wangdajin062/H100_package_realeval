"""Experiments — 14 Real Computation Experiments for QAD-MultiGuard.

Public API:
    EXPERIMENTS — registry of all experiment modules
    run_all     — run all (or selected) experiments
"""
from __future__ import annotations

__all__ = ["EXPERIMENTS", "run_all"]


def __getattr__(name: str):
    """按需导入 runner 内部，避免模块初始化期间的导入循环告警。"""
    if name == "EXPERIMENTS":
        from runner.registry import EXPERIMENTS
        return EXPERIMENTS
    if name == "run_all":
        from runner.orchestrator import run_all
        return run_all
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
