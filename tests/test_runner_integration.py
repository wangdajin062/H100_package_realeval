"""Integration tests for the refactored runner/CLI."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "outputs" / "results"


def test_runner_requires_explicit_mode():
    """Calling runner without --smoke or --paper must exit non-zero."""
    result = subprocess.run(
        [sys.executable, "-m", "experiments.runner"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "--smoke" in result.stderr and "--paper" in result.stderr


def test_runner_smoke_exp1_produces_valid_result():
    """Run exp1 in smoke mode and verify result schema."""
    result = subprocess.run(
        [sys.executable, "-m", "experiments.runner", "--smoke", "--exp", "1", "--no-archive"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    result_files = sorted(RESULTS.glob("exp1_*.json"))
    assert result_files, "exp1 result JSON not found"

    data = json.loads(result_files[-1].read_text(encoding="utf-8"))
    assert data["experiment"] == "exp1"
    assert "computation" in data
    assert "f1" in data


def test_validate_contract_cli_runs():
    """The --validate-contract CLI flag runs without crashing."""
    result = subprocess.run(
        [sys.executable, "-m", "experiments.runner", "--validate-contract"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    # It may fail if results are missing or smoke, but it should not crash.
    assert (
        "Contract validation" in result.stderr
        or "[PASS]" in result.stdout
        or "[FAIL]" in result.stdout
    )
