"""experiments/consistency_check.py — measured-vs-claimed consistency auditor.

alignment.py / contract.py only check FIELD PRESENCE. This auditor checks that the
numbers feeding the paper are actually trustworthy:

  1. COMPUTATION TYPE — the result must be a real H100 run (`computation` starts with
     "h100"), not a silent smoke/sklearn/proxy fallback.
  2. SELF-CITED FIELDS — some result keys are hardcoded paper values (e.g. exp5
     paper_reference.*, exp6 paper_reference.*). They are CITED, never MEASURED, and
     must never be treated as evidence.
  3. PAPER-CLAIM DRIFT — headline measured metrics are compared against the paper's
     claimed values; MATCH within tolerance, else DRIFT (with delta) so the
     table/figure/text gets updated to the measured number.

Usage:
    python -m experiments.consistency_check            # human report
    python -m experiments.consistency_check --json     # machine-readable
Exit code is non-zero if any SMOKE or DRIFT (P0) issue is found.
"""
from __future__ import annotations

import json
from typing import Any

from realeval.io.paths import RESULTS as RESULTS_DIR

_NOT_FOUND = object()


def _dig(obj: Any, path: tuple) -> Any:
    cur = obj
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return _NOT_FOUND
        cur = cur[key]
    return cur


def _latest_result(exp_short: str) -> dict | None:
    candidates = sorted(RESULTS_DIR.glob(f"{exp_short}_*.json"))
    if not candidates:
        return None
    return json.loads(candidates[-1].read_text(encoding="utf-8"))


# Headline metrics vs the paper's claimed value: (dotted path, claimed, tol, label).
# DRIFT here is EXPECTED for several items and is the signal to update the paper.
PAPER_CLAIMS: dict[str, list[tuple]] = {
    "exp1":  [(("f1",), 0.916, 0.03, "QAD component F1")],
    "exp2":  [(("variants", "kl_only", "f1"), 0.916, 0.03, "Pure-KL F1 (claimed optimal)")],
    "exp3":  [(("conditions", "ov_freeze_full", "f1"), 0.923, 0.03, "QAD+OVF F1")],
    "exp5":  [(("taf28k", "f1"), 0.923, 0.03, "TAF-28k IID F1"),
              (("chifraud", "f1"), 0.860, 0.03, "ChiFraud OOD F1")],
    "exp9":  [(("with_cot", "f1"), 0.923, 0.03, "with-CoT F1 (claimed better)")],
    "exp10": [(("scales", "teacher", "f1_fixed"), 0.916, 0.05, "0.5B teacher F1")],
    "exp11": [(("schemes", "int4", "f1"), 0.900, 0.05, "INT4 F1")],
    "exp12": [(("storage_decomposition_point8", "total_advantage_x"), 28.0, 4.0, "storage advantage x")],
    "exp13": [(("strategies", "late_fusion", "f1"), 0.923, 0.03, "fusion SYSTEM F1 (headline)")],
}

# Fields that are hardcoded paper self-citations, never independent measurements.
CITED_FIELDS: dict[str, list[tuple]] = {
    "exp5": [("bf16_matched_advfraud",)],
    "exp6": [("paper_reference", "alpha_generic"),
             ("paper_reference", "alpha_tuned"),
             ("paper_reference", "speculative_speedups")],
}


def audit(targets: list[str] | None = None) -> dict[str, list[dict]]:
    exps = targets or sorted(set(PAPER_CLAIMS) | set(CITED_FIELDS))
    report: dict[str, list[dict]] = {}
    for exp in exps:
        items: list[dict] = []
        data = _latest_result(exp)
        if data is None:
            report[exp] = [{"kind": "MISSING_RESULT", "severity": "P1"}]
            continue

        comp = str(data.get("computation", ""))
        if not comp.startswith("h100"):
            items.append({"kind": "SMOKE", "severity": "P0",
                          "detail": f"computation={comp!r} — NOT a real H100 run"})

        for path, claimed, tol, label in PAPER_CLAIMS.get(exp, []):
            val = _dig(data, path)
            dotted = ".".join(path)
            if val is _NOT_FOUND or val is None:
                items.append({"kind": "MISSING", "severity": "P1", "field": dotted, "label": label})
            elif isinstance(val, (int, float)):
                delta = float(val) - float(claimed)
                status = "MATCH" if abs(delta) <= tol else "DRIFT"
                items.append({"kind": status, "severity": "OK" if status == "MATCH" else "P0",
                              "field": dotted, "label": label,
                              "measured": round(float(val), 4), "claimed": claimed,
                              "delta": round(delta, 4)})

        for path in CITED_FIELDS.get(exp, []):
            if _dig(data, path) is not _NOT_FOUND:
                items.append({"kind": "CITED", "severity": "WARN", "field": ".".join(path),
                              "detail": "hardcoded paper value — NOT a measurement; never cite as evidence"})

        report[exp] = items
    return report


def print_report(report: dict[str, list[dict]]) -> bool:
    """Print human report; return True if any P0 issue (SMOKE/DRIFT) present."""
    icon = {"SMOKE": "🔴", "DRIFT": "🔴", "MISSING": "🟠", "MISSING_RESULT": "🟠",
            "CITED": "🟡", "MATCH": "🟢"}
    has_p0 = False
    for exp, items in sorted(report.items()):
        print(f"\n[{exp}]")
        if not items:
            print("  (no checks)")
        for it in items:
            k = it["kind"]
            if it.get("severity") == "P0":
                has_p0 = True
            if k in ("MATCH", "DRIFT"):
                print(f"  {icon.get(k,'·')} {k:5s} {it['label']}: measured={it['measured']} "
                      f"vs claimed={it['claimed']} (Δ={it['delta']:+.4f})")
            elif k == "CITED":
                print(f"  {icon['CITED']} CITED {it['field']} — {it['detail']}")
            elif k == "SMOKE":
                print(f"  {icon['SMOKE']} SMOKE {it['detail']}")
            else:
                print(f"  {icon.get(k,'·')} {k} {it.get('field', it.get('detail',''))}")
    print("\n=== P0 issues present: %s ===" % ("YES" if has_p0 else "no"))
    return has_p0


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Measured-vs-claimed consistency auditor")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args()
    report = audit()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        has_p0 = any(it.get("severity") == "P0" for its in report.values() for it in its)
    else:
        has_p0 = print_report(report)
    return 1 if has_p0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
