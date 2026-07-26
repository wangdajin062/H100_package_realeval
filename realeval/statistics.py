"""realeval/statistics.py — Basic Statistics (Mean, Std, 95% CI) + research-grade functions

Only computes statistics from real measured values.
Never reads summary.csv, paper_values, or any pre-computed metric.
"""
from __future__ import annotations
import logging
import math
import numpy as np
from typing import Sequence

logger = logging.getLogger("statistics")


def mean(values: Sequence[float]) -> float:
    """Arithmetic mean. Returns 0.0 for empty sequences."""
    n = len(values)
    if n == 0:
        return 0.0
    return sum(values) / n


def std(values: Sequence[float], ddof: int = 1) -> float:
    """Sample standard deviation (ddof=1). Returns 0.0 for empty or single-value sequences."""
    n = len(values)
    if n <= 1:
        return 0.0
    m = mean(values)
    variance = sum((v - m) ** 2 for v in values) / (n - ddof)
    return math.sqrt(variance)


def ci95(values: Sequence[float]) -> tuple[float, float]:
    """95% confidence interval (lower, upper) via Student's t-distribution.

    Uses the normal approximation when n >= 30 for computational simplicity.
    For n < 30, uses Student's t critical value (requires scipy; falls back to z=1.96).
    Returns (0.0, 0.0) for sequences with fewer than 2 values.
    """
    n = len(values)
    if n < 2:
        return (0.0, 0.0)
    m = mean(values)
    se = std(values, ddof=1) / math.sqrt(n)
    if se == 0.0:
        return (m, m)
    if n >= 30:
        z = 1.96  # normal approximation
    else:
        try:
            from scipy.stats import t as students_t
            z = float(students_t.ppf(0.975, n - 1))
        except ImportError:
            z = 1.96  # fallback if scipy unavailable
    return (m - z * se, m + z * se)


def describe(values: Sequence[float]) -> dict:
    """Return a summary dict with mean, std, min, max, n, and 95% CI.

    This is the primary public API. Meant for experiment results that need
    a quick statistical summary without importing multiple functions.
    """
    arr = list(values)
    n = len(arr)
    if n == 0:
        return {"mean": None, "std": None, "min": None, "max": None, "n": 0, "ci95": (None, None)}
    m = mean(arr)
    lo, hi = ci95(arr)
    return {
        "mean": round(m, 6),
        "std": round(std(arr), 6),
        "min": round(min(arr), 6),
        "max": round(max(arr), 6),
        "n": n,
        "ci95": (round(lo, 6), round(hi, 6)),
    }


# ── Research-grade statistics (from V4) ──


def summarize(samples, n_boot=2000, ci=0.95, seed=0) -> dict:
    """Mean/std/n + bootstrap CI for a 1-D sample. Delegates to statlib.stats.bootstrap_ci."""
    x = np.asarray(samples, dtype=float)
    x = x[~np.isnan(x)]
    if x.size == 0:
        return {"n": 0, "mean": None, "std": None, "ci_low": None, "ci_high": None}
    if x.size == 1:
        m = float(x[0])
        return {"n": 1, "mean": m, "std": 0.0, "ci_low": m, "ci_high": m}
    try:
        from statlib.stats import bootstrap_ci
    except ImportError:
        logger.debug("statlib not available; using basic statistics without bootstrap CI")
        return {"n": int(x.size), "mean": float(x.mean()), "std": float(x.std(ddof=1)),
                "ci_low": None, "ci_high": None}
    result = bootstrap_ci(x.tolist(), n_bootstrap=n_boot, ci=ci, seed=seed)
    return {"n": result["n"], "mean": result["mean"], "std": result["std"],
            "ci_low": result["ci_lower"], "ci_high": result["ci_upper"]}


def cohens_d(a, b) -> float:
    """Standardised mean difference (pooled SD). Delegates to statlib.stats.cohens_d."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    if a.size < 2 or b.size < 2:
        return float("nan")
    try:
        from statlib.stats import cohens_d as _cohens_d
    except ImportError:
        logger.debug("statlib not available; Cohen's d unavailable")
        return float("nan")
    return float(_cohens_d(a.tolist(), b.tolist())["cohens_d"])


def cliffs_delta(a, b) -> float:
    """Non-parametric effect size in [-1, 1]. Delegates to statlib.stats.cliffs_delta."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    if a.size == 0 or b.size == 0:
        return float("nan")
    try:
        from statlib.stats import cliffs_delta as _cliffs_delta
    except ImportError:
        logger.debug("statlib not available; Cliff's delta unavailable")
        return float("nan")
    return float(_cliffs_delta(a.tolist(), b.tolist())["cliffs_delta"])


def compare(a, b, paired=False) -> dict:
    """Compare two conditions: summaries, difference, p-value (t-test/Wilcoxon), and effect sizes.

    Gracefully degrades when scipy is unavailable, returning None for all p-values
    (consistent with ci95's fallback behaviour).
    """
    a, b = np.asarray(a, float), np.asarray(b, float)
    out = {"a": summarize(a), "b": summarize(b),
           "mean_diff": float(b.mean() - a.mean()) if a.size and b.size else None,
           "t_p": None, "cohens_d": cohens_d(a, b), "cliffs_delta": cliffs_delta(a, b)}
    try:
        from scipy import stats as st
    except ImportError:
        return out
    try:
        if paired and a.size == b.size and a.size >= 2:
            out["t_p"] = float(st.ttest_rel(a, b).pvalue)
            try:
                out["wilcoxon_p"] = float(st.wilcoxon(a, b).pvalue)
            except Exception:
                out["wilcoxon_p"] = None
        elif a.size >= 2 and b.size >= 2:
            out["t_p"] = float(st.ttest_ind(a, b).pvalue)
            try:
                out["mannwhitney_p"] = float(st.mannwhitneyu(a, b, alternative="two-sided").pvalue)
            except Exception:
                out["mannwhitney_p"] = None
    except Exception:
        out["t_p"] = None
    return out
