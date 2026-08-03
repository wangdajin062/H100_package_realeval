"""experiments/alignment.py — 实验 → 图像脚本字段对齐校验器。

在每次 runner 运行后自动校验，确保 paper_data.py 的 _from_result()
调用都能在实验产出 JSON 中找到对应字段。
"""
from __future__ import annotations

from pathlib import Path
import json
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "outputs" / "results"

EXPECTED_FIELDS: dict[str, list[tuple[str, ...]]] = {
    "exp1": [
        ("f1",), ("std",), ("trajectory",),
        ("kl_final",), ("kl_plateau",), ("kl_converged",),
        ("ovf_activation_step",), ("total_steps",),
        ("snr_min",), ("snr_max",), ("drift_pct_final",),
    ],
    "exp2": [
        ("variants", "kl_only", "f1"),
        ("variants", "kl_only", "kl_final"),
        ("variants", "kl_only", "std"),
        ("variants", "mse_only", "f1"),
        ("variants", "mse_only", "kl_final"),
        ("variants", "mse_only", "std"),
        ("variants", "ce_only", "f1"),
        ("variants", "ce_only", "kl_final"),
        ("variants", "ce_only", "std"),
        ("variants", "kl_mse_combined", "f1"),
        ("variants", "kl_mse_combined", "kl_final"),
        ("variants", "kl_mse_combined", "std"),
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
        ("layer_selection", "early", "f1"),
        ("layer_selection", "early", "variance_drift_pct"),
        ("layer_selection", "mid", "f1"),
        ("layer_selection", "mid", "variance_drift_pct"),
        ("layer_selection", "late", "f1"),
        ("layer_selection", "late", "variance_drift_pct"),
        ("layer_selection", "all", "f1"),
        ("rho_sweep", "rho_0.0", "f1"),
        ("rho_sweep", "rho_0.0", "ppl"),
        ("rho_sweep", "rho_0.1", "f1"),
        ("rho_sweep", "rho_0.2", "f1"),
        ("rho_sweep", "rho_0.3", "f1"),
        ("rho_sweep", "rho_0.4", "f1"),
        ("rho_sweep", "rho_0.5", "f1"),
    ],
    "exp4": [
        ("classifiers", "logreg", "f1"),
        ("classifiers", "xgb", "f1"),
        ("classifiers", "mlp", "f1"),
        ("classifiers", "qwen_base", "f1"),
    ],
    "exp5": [
        ("taf28k", "f1"),
        ("chifraud", "f1"),
        ("advfraud", "full_pool", "f1"),
        ("advfraud", "curated", "f1"),
        ("bf16_matched_advfraud",),
        ("ldp_tradeoff", "eps_1.5", "f1"),
        ("ldp_tradeoff", "eps_3.0", "f1"),
        ("cross_taf_on_chifraud", "f1"),
        ("cross_chifraud_on_taf", "f1"),
    ],
    "exp6": [
        ("diagnostic_B", "h100_measured", "generic"),
        ("paper_reference", "alpha_generic"),
        ("paper_reference", "alpha_tuned"),
        ("paper_reference", "gamma_deploy"),
        ("paper_reference", "speculative_speedups"),
    ],
    "exp8": [
        ("latency_detail",),
        ("batch_benchmark",),
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
        ("schemes", "bf16", "f1"),
        ("schemes", "bf16", "std"),
        ("schemes", "int4", "f1"),
        ("schemes", "int4", "std"),
        ("schemes", "nf4", "f1"),
        ("schemes", "nf4", "std"),
        ("schemes", "fp16", "f1"),
        ("schemes", "fp16", "std"),
        ("schemes", "int8", "f1"),
        ("schemes", "int8", "std"),
    ],
    "exp14": [
        ("models", "q4km_0.5b_llama_cpp", "f1"),
        ("models", "q4km_0.5b_llama_cpp", "std"),
    ],
}


_NOT_FOUND = object()


def _dig(obj: dict[str, Any], path: tuple[str, ...]) -> Any:
    """沿路径钻取嵌套 dict。键缺失返回 _NOT_FOUND，值为 None 则正常返回 None。"""
    cur: Any = obj
    for key in path:
        if not isinstance(cur, dict):
            return _NOT_FOUND
        if key not in cur:
            return _NOT_FOUND
        cur = cur[key]
    return cur


def _latest_result(exp_short: str) -> dict[str, Any] | None:
    candidates = sorted(RESULTS_DIR.glob(f"{exp_short}_*.json"))
    if not candidates:
        return None
    return json.loads(candidates[-1].read_text(encoding="utf-8"))


def check_alignment(targets: list[str] | None = None) -> dict[str, list[str]]:
    """返回 {exp_short: [missing_paths]} 诊断报告。"""
    exp_list = targets or sorted(EXPECTED_FIELDS)
    report: dict[str, list[str]] = {}
    for exp in exp_list:
        data = _latest_result(exp)
        if data is None:
            report[exp] = ["NO_RESULT_FILE"]
            continue
        missing: list[str] = []
        for path in EXPECTED_FIELDS.get(exp, []):
            if _dig(data, path) is _NOT_FOUND:
                missing.append(".".join(path))
        report[exp] = missing
    return report


def print_alignment_report(report: dict[str, list[str]]) -> bool:
    """打印对齐报告，返回是否有失败项。"""
    failed = False
    for exp, missing in sorted(report.items()):
        if missing:
            failed = True
            print(f"[FAIL] {exp}")
            for item in missing:
                print(f"  - {item}")
        else:
            print(f"[PASS] {exp}")
    return failed
