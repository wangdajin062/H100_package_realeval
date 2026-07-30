"""Result contract validation for paper figure data bridge.

Validate that latest experiment result JSONs expose the fields consumed by
`docs/figure_scripts/paper_data.py`.
"""
from __future__ import annotations

from pathlib import Path
import json
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "outputs" / "results"

REQUIRED_PATHS: dict[str, list[tuple[str, ...]]] = {
    "exp1": [("f1",), ("trajectory",), ("kl_final",), ("drift_pct_final",),
             ("kl_plateau",), ("kl_converged",), ("total_steps",), ("ovf_activation_step",),
             ("snr_min",), ("snr_max",)],
    "exp4": [
        ("classifiers", "logreg", "f1"),
        ("classifiers", "xgb", "f1"),
        ("classifiers", "mlp", "f1"),
        ("classifiers", "qwen_base", "f1"),
    ],
    "exp2": [
        ("variants", "kl_only", "f1"),
        ("variants", "kl_only", "kl_final"),
        ("variants", "mse_only", "f1"),
        ("variants", "mse_only", "kl_final"),
        ("variants", "ce_only", "f1"),
        ("variants", "ce_only", "kl_final"),
        ("variants", "kl_mse_combined", "f1"),
        ("variants", "kl_mse_combined", "kl_final"),
        ("variants", "kl_task", "f1"),
        ("variants", "kl_task", "kl_final"),
    ],
    "exp3": [
        ("conditions", "no_reg", "f1"),
        ("conditions", "no_reg", "variance_drift_pct"),
        ("conditions", "ov_freeze_full", "f1"),
        ("conditions", "ov_freeze_full", "variance_drift_pct"),
        ("conditions", "ov_freeze_half", "f1"),
        ("conditions", "ov_freeze_half", "variance_drift_pct"),
        ("conditions", "ov_freeze_quarter", "f1"),
        ("conditions", "ov_freeze_quarter", "variance_drift_pct"),
        ("layer_selection", "all", "f1"),
        ("layer_selection", "late", "variance_drift_pct"),
        ("rho_sweep", "rho_0.3", "f1"),
        ("rho_sweep", "rho_0.3", "ppl"),
    ],
    "exp5": [
        ("taf28k", "f1"),
        ("chifraud", "f1"),
        ("advfraud", "full_pool", "f1"),
        ("advfraud", "curated", "f1"),
        ("bf16_matched_advfraud",),
        ("paper_reference", "ldp_eps_1_5_f1"),
        ("cross_taf_on_chifraud", "f1"),
        ("cross_chifraud_on_taf", "f1"),
    ],
    "exp6": [
        ("diagnostic_B", "h100_measured", "generic"),
        ("diagnostic_B", "h100_measured", "domain"),
        ("paper_reference", "alpha_generic"),
        ("paper_reference", "alpha_tuned"),
        ("paper_reference", "gamma_deploy"),
        ("paper_reference", "speculative_speedups"),
    ],
    "exp8": [
        ("latencies", "int4"),
        ("latencies", "fp16"),
        ("batch_benchmark",),
        ("latency_detail",),
    ],
    "exp10": [
        ("scales", "teacher", "f1_fixed"),
        ("scales", "teacher", "f1_conv"),
        ("scales", "teacher_1.5b", "f1_fixed"),
        ("scales", "teacher_1.5b", "f1_conv"),
        ("scales", "teacher_3b", "f1_fixed"),
        ("scales", "teacher_3b", "f1_conv"),
        ("scales", "teacher_7b", "f1_fixed"),
        ("scales", "teacher_7b", "f1_conv"),
    ],
    "exp11": [
        ("schemes", "int4", "f1"),
        ("schemes", "nf4", "f1"),
        ("schemes", "fp16", "f1"),
        ("schemes", "int8", "f1"),
        ("model_source",),
    ],
    # exp7, exp9, exp12, exp13, exp14 are intentionally omitted from
    # REQUIRED_PATHS because they do not feed any paper figure or main table
    # (Figures 3-8 / Table 2). They are validated indirectly through smoke runs
    # and the paper_pipeline _extract() aggregator.
}


def _dig(obj: dict[str, Any], path: tuple[str, ...]) -> Any:
    cur: Any = obj
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
        if cur is None:
            return None
    return cur


def _latest_result(exp_short: str) -> dict[str, Any] | None:
    candidates = sorted(RESULTS_DIR.glob(f"{exp_short}_*.json"))
    if not candidates:
        return None
    return json.loads(candidates[-1].read_text(encoding="utf-8"))


def validate_latest_results(targets: list[str] | None = None) -> dict[str, list[str]]:
    """Return missing-path diagnostics grouped by experiment short name."""
    exp_list = targets or sorted(REQUIRED_PATHS)
    report: dict[str, list[str]] = {}
    for exp in exp_list:
        missing: list[str] = []
        data = _latest_result(exp)
        if data is None:
            report[exp] = ["missing result file"]
            continue
        for path in REQUIRED_PATHS.get(exp, []):
            value = _dig(data, path)
            if value is None:
                missing.append(".".join(path))
        if exp == "exp8":
            has_int8 = _dig(data, ("latencies", "int8")) is not None
            has_bf16 = _dig(data, ("latencies", "bf16")) is not None
            if not (has_int8 or has_bf16):
                missing.append("latencies.int8|latencies.bf16")
        report[exp] = missing
    return report


def main() -> int:
    report = validate_latest_results()
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
