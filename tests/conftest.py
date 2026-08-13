"""tests/conftest.py — Shared fixtures and test isolation setup.

Redirects writable outputs to temporary directories so tests never
touch the real outputs/ or data/ trees.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolate_outputs(monkeypatch, tmp_path):
    """Redirect all writable output roots to tmp_path for test isolation.

    REALEVAL_OUTPUT_ROOT covers subprocesses (fresh import honors it), but
    in-process modules froze their path constants at import time — those
    bindings must be patched per module, or tests will write to (and delete
    from) the real outputs/ tree. (2026-08-11 incident)
    """
    import realeval.io as io_mod
    import realeval.audit as runlog_mod
    import realeval.paths as paths_mod

    saved_results = io_mod.RESULTS
    saved_runlog = runlog_mod.RUNLOG
    saved_data = paths_mod.DATA if hasattr(paths_mod, "DATA") else None

    out = tmp_path / "outputs"
    io_mod.RESULTS = tmp_path / "results"
    runlog_mod.RUNLOG = tmp_path / "runlog.jsonl"

    # Prevent writes to real outputs/ during tests (subprocess path)
    monkeypatch.setenv("REALEVAL_OUTPUT_ROOT", str(out))

    # In-process path: rebind import-time-frozen constants in every module
    # that captured them from realeval.io.paths.
    import realeval.io.archive as archive_mod
    import realeval.io.paths as io_paths_mod
    import realeval.io.serialization as serialization_mod

    results = out / "results"
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

    yield tmp_path

    io_mod.RESULTS = saved_results
    runlog_mod.RUNLOG = saved_runlog
    if saved_data is not None:
        paths_mod.DATA = saved_data
