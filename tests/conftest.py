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
    """Redirect all writable output roots to tmp_path for test isolation."""
    import realeval.io as io_mod
    import realeval.runlog as runlog_mod
    import realeval.paths as paths_mod

    saved_results = io_mod.RESULTS
    saved_runlog = runlog_mod.RUNLOG
    saved_data = paths_mod.DATA if hasattr(paths_mod, "DATA") else None

    io_mod.RESULTS = tmp_path / "results"
    runlog_mod.RUNLOG = tmp_path / "runlog.jsonl"

    # Prevent writes to real outputs/ during tests
    monkeypatch.setenv("REALEVAL_OUTPUT_ROOT", str(tmp_path / "outputs"))

    yield tmp_path

    io_mod.RESULTS = saved_results
    runlog_mod.RUNLOG = saved_runlog
    if saved_data is not None:
        paths_mod.DATA = saved_data
