"""Tests for realeval/io/archive.py archive/cleanup behavior."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from realeval.io.archive import archive_if_needed, clear_outputs
from realeval.io.paths import RESULTS


def test_clear_outputs_removes_result_jsons(tmp_path, monkeypatch):
    """clear_outputs removes exp*_*.json and all_experiments.json from results dir."""
    # Redirect RESULTS to a temp dir for isolation
    monkeypatch.setattr("realeval.io.archive.RESULTS", tmp_path)
    monkeypatch.setattr("realeval.io.archive.PREDICTIONS", tmp_path / "predictions")
    # _CLEAR_GLOBS/_CLEAR_DIRS are initialized at import time, so update them to
    # point to tmp_path — otherwise the real outputs/ tree gets deleted.
    monkeypatch.setattr(
        "realeval.io.archive._CLEAR_GLOBS",
        [(tmp_path, "exp*_*.json", False), (tmp_path, "all_experiments.json", False)],
    )
    monkeypatch.setattr("realeval.io.archive._CLEAR_DIRS", [])
    (tmp_path / "predictions").mkdir(parents=True, exist_ok=True)

    (tmp_path / "exp1_20260805_120000.json").write_text("{}")
    (tmp_path / "all_experiments.json").write_text("{}")

    deleted = clear_outputs(dry_run=False)
    assert any("exp1_20260805_120000.json" in d for d in deleted)
    assert not list(tmp_path.glob("exp*_*.json"))


def test_archive_if_needed_force(tmp_path, monkeypatch):
    """archive_if_needed(force=True) produces a Markdown archive even if empty."""
    monkeypatch.setattr("realeval.io.archive.RESULTS", tmp_path)
    monkeypatch.setattr("realeval.io.archive.PREDICTIONS", tmp_path / "predictions")
    monkeypatch.setattr("realeval.io.archive.FIGURES", tmp_path / "figures")
    monkeypatch.setattr("realeval.io.archive.METRICS_DIR", tmp_path / "metrics")
    monkeypatch.setattr("realeval.io.archive.TABLES_DIR", tmp_path / "tables")
    monkeypatch.setattr("realeval.io.archive.ARCHIVE", tmp_path / "archive")
    # CRITICAL: archive_if_needed() ends with clear_outputs(), which reads the
    # import-time-built _CLEAR_GLOBS/_CLEAR_DIRS — not the patched scalars above.
    # Without these two patches the test DELETES the real outputs/ tree.
    monkeypatch.setattr(
        "realeval.io.archive._CLEAR_GLOBS",
        [(tmp_path, "exp*_*.json", False), (tmp_path, "all_experiments.json", False)],
    )
    monkeypatch.setattr("realeval.io.archive._CLEAR_DIRS", [])

    (tmp_path / "predictions").mkdir(parents=True, exist_ok=True)

    path = archive_if_needed(force=True)
    assert path is not None
    archive_path = Path(path)
    assert archive_path.exists()
    assert "experiment_results.md" in archive_path.name
    text = archive_path.read_text(encoding="utf-8")
    assert "实验结果归档快照" in text
