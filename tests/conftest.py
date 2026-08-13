"""tests/conftest.py — Shared fixtures and test isolation setup.

Redirects writable outputs to temporary directories so tests never
touch the real outputs/ or data/ trees.
"""

from __future__ import annotations

import atexit
import os
import shutil
import tempfile
from pathlib import Path

import pytest

# 在 pytest 收集阶段（import test 模块之前）就把输出根重定向到临时目录，
# 避免模块级 configure_logging() 在 import 时写真实 outputs/logs/experiments.log。
# 各测试的 fixture 仍会用 tmp_path 覆盖此值，实现 per-test 隔离。
_TEST_OUTPUT_ROOT = tempfile.mkdtemp(prefix="realeval-test-output-")
os.environ["REALEVAL_OUTPUT_ROOT"] = _TEST_OUTPUT_ROOT
atexit.register(shutil.rmtree, _TEST_OUTPUT_ROOT, ignore_errors=True)


@pytest.fixture(autouse=True)
def isolate_outputs(monkeypatch, tmp_path):
    """Redirect all writable output roots to tmp_path for test isolation.

    REALEVAL_OUTPUT_ROOT covers subprocesses (fresh import honors it), but
    in-process modules froze their path constants at import time — those
    bindings must be patched per module, or tests will write to (and delete
    from) the real outputs/ tree. (2026-08-11 incident)

    All output paths now derive from ``realeval.io.paths`` (see the
    ``REALEVAL_OUTPUT_ROOT`` support added there), so every module that
    captured a path constant at import time is rebind here.
    """
    import realeval.io as io_mod

    out = tmp_path / "outputs"
    monkeypatch.setattr(io_mod, "RESULTS", out / "results", raising=False)

    # Prevent writes to real outputs/ during tests (subprocess path)
    monkeypatch.setenv("REALEVAL_OUTPUT_ROOT", str(out))

    # In-process path: rebind import-time-frozen constants in every module
    # that captured them from realeval.io.paths.
    import realeval.io.archive as archive_mod
    import realeval.io.paths as io_paths_mod
    import realeval.io.serialization as serialization_mod
    import realeval.audit as audit_mod
    import realeval.report as report_mod
    import realeval.benchmark as benchmark_mod
    import realeval.real_backend as real_backend_mod
    import audit.evidence_graph as evidence_mod
    import audit.tracker as tracker_mod
    import experiments.framework as framework_mod
    import experiments.consistency_check as consistency_mod
    import experiments.claim_engine as claim_engine_mod
    import experiments.paper_pipeline as paper_pipeline_mod
    import experiments.common as common_mod

    results = out / "results"
    # io/serialization/archive path constants
    for mod in (io_paths_mod, serialization_mod, archive_mod):
        monkeypatch.setattr(mod, "RESULTS", results, raising=False)
        monkeypatch.setattr(mod, "PREDICTIONS", out / "predictions", raising=False)
    monkeypatch.setattr(serialization_mod, "ALL_EXPERIMENTS_FILE",
                        results / "all_experiments.json", raising=False)
    for name in ("FIGURES", "METRICS_DIR", "TABLES_DIR", "ARCHIVE"):
        monkeypatch.setattr(archive_mod, name, out / name.lower().removesuffix("_dir"),
                            raising=False)
    monkeypatch.setattr(
        archive_mod, "_CLEAR_GLOBS",
        [(results, "exp*_*.json", False), (results, "all_experiments.json", False)],
        raising=False,
    )
    monkeypatch.setattr(archive_mod, "_CLEAR_DIRS", [], raising=False)

    # logs / audit / evidence / tracker
    monkeypatch.setattr(audit_mod, "AUDIT_LOG", out / "logs" / "audit.log", raising=False)
    monkeypatch.setattr(audit_mod, "RUNLOG", out / "logs" / "runlog.jsonl", raising=False)
    monkeypatch.setattr(framework_mod, "LOG_DIR", out / "logs", raising=False)
    monkeypatch.setattr(evidence_mod, "EVIDENCE_DIR", out / "evidence", raising=False)
    monkeypatch.setattr(tracker_mod, "AUDIT_ROOT", out / "audit", raising=False)

    # report / benchmark
    monkeypatch.setattr(report_mod, "OUT", out, raising=False)
    monkeypatch.setattr(report_mod, "TABLES", out / "tables", raising=False)
    monkeypatch.setattr(report_mod, "FIGS", out / "figures", raising=False)
    monkeypatch.setattr(report_mod, "RESULTS", results, raising=False)
    monkeypatch.setattr(report_mod, "METRICS", out / "metrics", raising=False)
    monkeypatch.setattr(benchmark_mod, "OUT", out / "metrics", raising=False)

    # claims / consistency / pipeline / models
    monkeypatch.setattr(claim_engine_mod, "OUT", out / "claims", raising=False)
    monkeypatch.setattr(consistency_mod, "RESULTS_DIR", results, raising=False)
    monkeypatch.setattr(paper_pipeline_mod, "RESULTS", results, raising=False)
    monkeypatch.setattr(common_mod, "MODELS", out / "models", raising=False)
    monkeypatch.setattr(real_backend_mod, "MODELS", out / "models", raising=False)

    yield tmp_path
