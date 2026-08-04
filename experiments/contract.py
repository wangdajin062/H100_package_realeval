"""Result contract validation for paper figure data bridge.

Validate that latest experiment result JSONs expose the fields consumed by
`docs/figure_scripts/paper_data.py`.
"""
from __future__ import annotations

from pathlib import Path
import json
from typing import Any

from experiments.alignment import EXPECTED_FIELDS as REQUIRED_PATHS
from experiments.alignment import _NOT_FOUND, _dig

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "outputs" / "results"


def _latest_result(exp_short: str) -> dict[str, Any] | None:
    candidates = sorted(RESULTS_DIR.glob(f"{exp_short}_*.json"))
    if not candidates:
        return None
    return json.loads(candidates[-1].read_text(encoding="utf-8"))


def validate_latest_results(targets: list[str] | None = None, strict: bool = False) -> dict[str, list[str]]:
    """Return missing-path diagnostics grouped by experiment short name.

    When strict=True, also flags results whose `computation` is NOT a real H100 run
    (i.e. a silent smoke/sklearn/proxy fallback), which alignment/presence checks miss.
    """
    exp_list = targets or sorted(REQUIRED_PATHS)
    report: dict[str, list[str]] = {}
    for exp in exp_list:
        missing: list[str] = []
        data = _latest_result(exp)
        if data is None:
            report[exp] = ["missing result file"]
            continue
        if strict:
            comp = str(data.get("computation", ""))
            if not comp.startswith("h100"):
                missing.append(f"NON_H100_COMPUTATION:{comp}")
        for path in REQUIRED_PATHS.get(exp, []):
            if _dig(data, path) is _NOT_FOUND:
                missing.append(".".join(path))
        if exp == "exp8":
            if (_dig(data, ("latencies", "int8")) is _NOT_FOUND
                    and _dig(data, ("latencies", "bf16")) is _NOT_FOUND):
                missing.append("latencies.int8|latencies.bf16")
        report[exp] = missing
    return report


def main() -> int:
    import sys
    strict = "--strict" in sys.argv
    report = validate_latest_results(strict=strict)
    has_error = False
    for exp, missing in report.items():
        if missing:
            has_error = True
            print(f"[FAIL] {exp}")
            for item in missing:
                print(f"  - {item}")
        else:
            print(f"[PASS] {exp}")
    return 1 if has_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
