"""Experiments — 14 Real Computation Experiments for QAD-MultiGuard.

Public API:
    EXPERIMENTS — registry of all experiment modules
    run_all — run all (or selected) experiments
"""

from experiments.runner import EXPERIMENTS, run_all

__all__ = ["EXPERIMENTS", "run_all"]

