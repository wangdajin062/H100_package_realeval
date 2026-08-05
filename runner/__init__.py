"""runner — 实验注册、运行与编排。

本包承担实验流水线的编排职责：
  - registry:         14 个实验的注册表
  - experiment_runner:单实验运行封装
  - orchestrator:     多实验调度、归档、归并
"""
from __future__ import annotations

from runner.experiment_runner import import_experiment, run_experiment
from runner.orchestrator import run_all, run_selected
from runner.registry import EXPERIMENTS, SHORT_TO_FULL

__all__ = [
    "EXPERIMENTS",
    "SHORT_TO_FULL",
    "import_experiment",
    "run_experiment",
    "run_all",
    "run_selected",
]
