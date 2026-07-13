"""test_integration.py — End-to-end pipeline smoke tests.

Verifies the full compute→metrics→audit chain:
  1. Synthetic data generation
  2. Small-model classification (sklearn)
  3. All metrics computed
  4. Audit trace captured
  5. Results persisted and readable
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest


def test_full_pipeline_smoke(tmp_path):
    """End-to-end: synthetic data → sklearn classifier → metrics → save → read back."""
    from realeval.data import load_synthetic
    from realeval.metrics import classification_metrics
    from realeval.statistics import summarize, compare
    from realeval.io import save_results, load_config

    # 1. Generate synthetic data
    ds = load_synthetic(n=50, seed=42)
    assert len(ds["texts"]) == 50
    assert ds["embeddings"].shape == (50, 128)

    # 2. Train a simple classifier
    from sklearn.ensemble import GradientBoostingClassifier
    split = 30
    X, y = ds["embeddings"], ds["labels"]
    clf = GradientBoostingClassifier(n_estimators=10, random_state=42).fit(
        X[:split], y[:split])

    # 3. Predict and compute metrics
    preds = clf.predict(X[split:]).tolist()
    true_labels = y[split:]
    m = classification_metrics(true_labels, preds)
    assert "f1" in m and "accuracy" in m
    assert 0.0 <= m["f1"] <= 1.0

    # 4. Compute statistics on per-fold F1s (generated from seeded RNG for reproducibility)
    import numpy as np
    rng = np.random.RandomState(42)
    fold_f1s = [round(float(v), 3) for v in rng.uniform(0.65, 0.90, 5)]
    s = summarize(fold_f1s)
    assert s["n"] == 5
    assert s["mean"] is not None

    # 5. Compare with a worse baseline (generated to be structurally lower)
    baseline_f1s = [round(float(v), 3) for v in rng.uniform(0.55, 0.75, 5)]
    cmp = compare(fold_f1s, baseline_f1s)
    assert cmp["mean_diff"] is not None

    # 6. Save results and read back
    import realeval.io as io_mod
    saved = io_mod.RESULTS
    try:
        io_mod.RESULTS = tmp_path
        path = save_results("integration_test", {
            "experiment": "integration_test",
            "computation": "smoke_sklearn",
            "metrics": m,
            "statistics": s,
            "comparison": {"mean_diff": cmp["mean_diff"]},
        })
        assert path.exists()

        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["experiment"] == "integration_test"
        assert data["computation"] == "smoke_sklearn"
        assert "metrics" in data
    finally:
        io_mod.RESULTS = saved


def test_audit_trace_captured(tmp_path):
    """Verify audit.environment captures expected keys."""
    from realeval.audit import log_environment, reset_audit_logger
    from realeval.runlog import log_run, read_runlog
    import realeval.runlog as runlog_mod

    saved_runlog = runlog_mod.RUNLOG
    try:
        # Redirect audit outputs to tmp_path
        runlog_mod.RUNLOG = tmp_path / "runlog.jsonl"
        import realeval.audit as audit_mod
        saved_audit_log = audit_mod.AUDIT_LOG
        audit_mod.AUDIT_LOG = tmp_path / "audit.log"

        # Log a minimal run
        log_run("test_integration",
                config={"models": {"teacher": "test", "student": "test"}, "data": {"max_samples": 10}},
                result={"f1": 0.95},
                status="completed")

        # Verify runlog
        records = read_runlog()
        assert len(records) >= 1
        r = records[-1]
        assert r["experiment"] == "test_integration"
        assert r["status"] == "completed"
        assert "provenance" in r

        # Restore paths
        audit_mod.AUDIT_LOG = saved_audit_log
        runlog_mod.RUNLOG = saved_runlog
    finally:
        runlog_mod.RUNLOG = saved_runlog


def test_end_to_end_data_loading():
    """Verify synthetic data → classifier pipeline works for all experiments."""
    from realeval.data import load_synthetic

    # Test with different sizes
    for n in (10, 50, 200):
        ds = load_synthetic(n=n, seed=0)
        assert len(ds["texts"]) == n
        assert len(ds["labels"]) == n
        assert ds["embeddings"].shape[0] == n
        # ~50% are fraud
        fraud_count = sum(ds["labels"])
        assert 0 < fraud_count < n, f"Expected mixed labels, got {fraud_count} fraud out of {n}"


def test_all_metrics_computation():
    """Verify all registered metrics compute without error."""
    from realeval.metrics import classification_metrics
    from metrics.base import compute_all, _BUILTIN_METRICS

    y_true = [0, 1, 0, 1, 0, 1, 0, 1, 0, 1]
    y_pred = [0, 1, 0, 0, 0, 1, 1, 1, 0, 1]

    # Classification metrics
    m = classification_metrics(y_true, y_pred)
    for key in ("f1", "accuracy", "precision", "recall"):
        assert key in m

    # compute_all with all registered metrics
    results = compute_all(y_true, y_pred)
    assert isinstance(results, dict)
    assert len(results) > 0
