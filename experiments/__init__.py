"""Experiments — 14 Real Computation Experiments for QAD-MultiGuard.

Public API:
    EXPERIMENTS — registry of all experiment modules
    run_all — run all (or selected) experiments
"""
from __future__ import annotations

__all__ = ["EXPERIMENTS", "run_all"]


def __getattr__(name: str):
    """按需导入 runner 内部，避免模块初始化期间的导入循环告警。

    ``python -m experiments.runner`` 时 runpy 先执行 experiments/__init__.py，
    若此处顶层 import experiments.runner，会触发
    RuntimeWarning: 'experiments.runner' found in sys.modules after import of
    package 'experiments'。改为属性访问时惰性导入（PEP 562），行为不变。
    """
    if name == "EXPERIMENTS":
        from experiments.runner import EXPERIMENTS
        return EXPERIMENTS
    if name == "run_all":
        from experiments.runner import run_all
        return run_all
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
