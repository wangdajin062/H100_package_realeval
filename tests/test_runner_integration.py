"""Integration tests for the refactored runner/CLI."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_validate_contract_cli_runs():
    """The --validate-contract CLI flag runs without crashing."""
    result = subprocess.run(
        [sys.executable, "-m", "experiments.runner", "--validate-contract"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        errors="replace",  # Windows GBK 控制台下子进程输出可能含非 GBK 字节
    )
    # It may fail if results are missing, but it should not crash.
    assert (
        "Contract validation" in result.stderr
        or "[PASS]" in result.stdout
        or "[FAIL]" in result.stdout
    )
