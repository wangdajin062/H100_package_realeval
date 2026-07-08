"""test_evidence_graph.py — End-to-end Claim→Evidence→Paper integration tests."""
from __future__ import annotations
import json
import tempfile
from pathlib import Path

import numpy as np
import pytest


class TestEvidenceGraph:
    def test_create_and_save_graph(self):
        from audit.evidence_graph import EvidenceGraph
        g = EvidenceGraph("TEST-001")
        c = g.add_claim({"hypothesis": "Test claim", "acceptance": {"f1": ">0.9"}})
        e = g.add_experiment({"name": "test_exp"}, parents=[c])
        r = g.add_run({"model": "test_model", "seed": 42}, parents=[e])
        p = g.add_predictions({"n_samples": 100}, parents=[r])
        m = g.add_metric({"f1": 0.95}, parents=[p])
        s = g.add_statistics({"ci_95": [0.93, 0.97]}, parents=[m])
        ev = g.add_evidence({"supports_claim": True}, parents=[s])
        g.add_conclusion({"verdict": "PASS"}, parents=[ev])
        ok, errors = g.validate()
        assert ok, f"Validation errors: {errors}"
        path = g.save()
        assert path.exists()
        # Round-trip
        g2 = EvidenceGraph.load(path)
        assert g2.graph_id == "TEST-001"
        assert len(g2.nodes) == 8

    def test_trace(self):
        from audit.evidence_graph import EvidenceGraph
        g = EvidenceGraph("TRACE-001")
        c = g.add_claim({"hypothesis": "Traceable"})
        r = g.add_run({"model": "m"}, parents=[c])
        m = g.add_metric({"f1": 0.8}, parents=[r])
        chain = g.trace(m)
        assert len(chain) == 3
        types = {n["node_type"] for n in chain}
        assert types == {"claim", "run", "metric"}

    def test_validate_missing_parent(self):
        from audit.evidence_graph import EvidenceGraph
        g = EvidenceGraph("BAD-001")
        g.add_metric({"f1": 0.5}, parents=["nonexistent_node"])
        ok, errors = g.validate()
        assert not ok
        assert any("nonexistent_node" in e for e in errors)


class TestClaimEvaluation:
    def test_evaluate_pass(self):
        from audit.evidence_graph import evaluate_claim
        claim = {"acceptance": {"f1": ">0.9", "latency_ms": "<100"}}
        evidence = {"f1": 0.95, "latency_ms": 80}
        result = evaluate_claim(claim, evidence)
        assert result["verdict"] == "PASS"

    def test_evaluate_fail(self):
        from audit.evidence_graph import evaluate_claim
        claim = {"acceptance": {"f1": ">0.9"}}
        evidence = {"f1": 0.85}
        result = evaluate_claim(claim, evidence)
        assert result["verdict"] == "FAIL"

    def test_evaluate_unsupported(self):
        from audit.evidence_graph import evaluate_claim
        claim = {"acceptance": {"f1": ">0.9"}}
        evidence = {}
        result = evaluate_claim(claim, evidence)
        assert result["verdict"] == "UNSUPPORTED"

    def test_validate_claim_definition(self):
        from audit.evidence_graph import validate_claim_definition
        ok, _ = validate_claim_definition({
            "id": "C1", "hypothesis": "H", "independent_variables": [],
            "dependent_variables": [], "controls": {}, "acceptance": {"f1": ">0.9"}
        })
        assert ok
        ok, errors = validate_claim_definition({"id": "C1"})
        assert not ok


class TestClaimRunner:
    def test_load_claim(self, tmp_path):
        import yaml
        claim_path = tmp_path / "claim_test.yaml"
        claim = {
            "id": "CLAIM-TEST",
            "hypothesis": "Test hypothesis",
            "independent_variables": ["x"],
            "dependent_variables": ["y"],
            "controls": {"seed": 42},
            "acceptance": {"y": ">0.5"},
        }
        # Temporarily monkeypatch CLAIMS_DIR
        import runner.claim_runner as cr
        old_dir = cr.CLAIMS_DIR
        cr.CLAIMS_DIR = tmp_path
        try:
            claim_path.write_text(yaml.dump(claim), encoding="utf-8")
            loaded = cr.load_claim(claim_path)
            assert loaded["id"] == "CLAIM-TEST"
        finally:
            cr.CLAIMS_DIR = old_dir

    def test_run_claim_end_to_end(self, tmp_path):
        from audit.evidence_graph import EvidenceGraph, evaluate_claim

        # Minimal end-to-end: claim → experiment → verdict
        def fake_experiment(config):
            from runner.interface import ExperimentResult
            r = ExperimentResult(experiment_id="test")
            r.collected_metrics = {"f1": 0.95}
            r.statistics = {"f1": {"ci_95": [0.93, 0.97]}}
            r.provenance = {"git_commit": "abc123", "seed": 42}
            return r

        import yaml
        claim = {
            "id": "CLAIM-E2E",
            "hypothesis": "End to end test",
            "independent_variables": ["none"],
            "dependent_variables": ["f1"],
            "controls": {},
            "acceptance": {"f1": ">0.9"},
        }
        claim_path = tmp_path / "claim_e2e.yaml"
        claim_path.write_text(yaml.dump(claim), encoding="utf-8")

        import runner.claim_runner as cr
        old_dir = cr.CLAIMS_DIR
        cr.CLAIMS_DIR = tmp_path
        try:
            result = cr.run_claim(claim_path, fake_experiment)
            assert result["verdict"] == "PASS"
            assert Path(result["evidence_graph_path"]).exists()
        finally:
            cr.CLAIMS_DIR = old_dir


class TestStatistics:
    def test_bootstrap_ci(self):
        from statlib.stats import bootstrap_ci
        samples = list(np.random.RandomState(42).randn(100) + 0.5)
        ci = bootstrap_ci(samples)
        assert ci["n"] == 100
        assert ci["ci_lower"] < ci["mean"] < ci["ci_upper"]

    def test_cohens_d(self):
        from statlib.stats import cohens_d
        x = list(np.random.RandomState(0).randn(100))
        y = list(np.random.RandomState(0).randn(100) + 1.0)  # large effect
        d = cohens_d(x, y)
        assert d["magnitude"] == "large"

    def test_paired_ttest(self):
        from statlib.stats import paired_ttest
        x = list(np.random.RandomState(0).randn(30))
        y = list(np.array(x) + 0.5)  # consistent shift
        result = paired_ttest(x, y)
        assert result["significant_005"]


class TestUnifiedMetrics:
    def test_f1_score(self):
        from metrics.base import F1Score
        f1 = F1Score().compute([0, 1, 0, 1], [0, 1, 1, 0])
        assert f1["f1"] == pytest.approx(0.5, abs=0.01)

    def test_compute_all(self):
        from metrics.base import compute_all
        results = compute_all([0, 1, 0, 1], [0, 1, 1, 0], metric_names=["f1", "accuracy"])
        assert "f1" in results
        assert "accuracy" in results

    def test_register_custom_metric(self):
        from metrics.base import Metric, register_metric, get_metric

        @register_metric
        class CustomMetric(Metric):
            @staticmethod
            def name() -> str:
                return "custom"

            def compute(self, y_true, y_pred, **kwargs):
                return {"custom": 1.0}

        m = get_metric("custom")
        assert m.compute([], []) == {"custom": 1.0}


class TestAuditTracker:
    def test_capture_environment(self):
        from audit.tracker import RunTracker
        t = RunTracker("test_audit")
        env = t.capture_environment()
        assert "python_version" in env

    def test_collect_all_and_write(self):
        from audit.tracker import RunTracker
        t = RunTracker("test_audit_full")
        t.collect_all(config={"seed": 42})
        paths = t.write_all()
        assert len(paths) >= 5  # run, environment, git, hardware, model, manifest
        for p in paths:
            assert p.exists()


class TestProfiler:
    def test_report_empty(self):
        from profiler.gpu_profiler import GpuProfiler
        p = GpuProfiler(interval_sec=0.1, run_label="test")
        r = p.report()
        assert r["n_samples"] == 0
        assert r["duration_s"] == 0.0
