"""Tests for metrics/contract.py field contract."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from metrics.contract import CITED_FIELDS, EXPECTED_FIELDS, validate_result

ROOT = Path(__file__).resolve().parent.parent
PAPER_DATA = ROOT / "docs" / "figure_scripts" / "paper_data.py"


def _from_result_calls(src: str) -> list[tuple[str, tuple[str, ...]]]:
    """Extract all (exp_name, key_path) from _from_result calls in paper_data.py."""
    tree = ast.parse(src)
    calls = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id != "_from_result":
            continue
        args = node.args
        if len(args) < 2:
            continue
        try:
            exp_name = ast.literal_eval(args[0])
            keys = tuple(ast.literal_eval(a) for a in args[1:])
        except (ValueError, SyntaxError):
            continue
        if not isinstance(exp_name, str):
            continue
        calls.append((exp_name, keys))
    return calls


def test_expected_fields_cover_paper_data():
    """Every non-cited _from_result path in paper_data.py must be in EXPECTED_FIELDS."""
    src = PAPER_DATA.read_text(encoding="utf-8")
    calls = _from_result_calls(src)
    assert calls, "No _from_result calls found in paper_data.py"

    for exp_name, keys in calls:
        # Skip if the call is explicitly cited (paper self-reference)
        if exp_name in CITED_FIELDS and keys in CITED_FIELDS[exp_name]:
            continue
        assert exp_name in EXPECTED_FIELDS, f"{exp_name} missing from EXPECTED_FIELDS"
        assert keys in EXPECTED_FIELDS[exp_name], (
            f"{exp_name}.{'.'.join(keys)} missing from EXPECTED_FIELDS"
        )


def test_validate_result_detects_missing_measured():
    """validate_result reports missing measured fields."""
    result = {"experiment": "exp1", "f1": 0.9}  # missing std, trajectory, etc.
    report = validate_result(result, "exp1")
    assert report["measured"]
    assert "std" in report["measured"]


def test_validate_result_ignores_cited_by_default():
    """Cited fields are not required by default."""
    result = {"experiment": "exp5", "taf28k": {"f1": 0.9}}
    report = validate_result(result, "exp5")
    assert "bf16_matched_advfraud" not in report["measured"]


def test_validate_result_can_include_cited():
    """Cited fields can be optionally checked."""
    result = {"experiment": "exp5", "taf28k": {"f1": 0.9}}
    report = validate_result(result, "exp5", include_cited=True)
    assert "bf16_matched_advfraud" in report["cited"]
