"""statlib — Statistics Library for Reproducible Research.

Public API:
    bootstrap_ci, cohens_d, cliffs_delta, describe — core statistical functions
"""

from statlib.stats import bootstrap_ci, cohens_d, cliffs_delta, describe

__all__ = [
    "bootstrap_ci",
    "cohens_d",
    "cliffs_delta",
    "describe",
]
