"""metrics/contract.py — 实验结果 → 图像脚本字段合约校验。

本模块定义 ``docs/figure_scripts/paper_data.py`` 消费的所有字段路径，
并提供 ``validate_result`` / ``check_alignment`` / ``validate_latest_results``
等工具函数。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "outputs" / "results"

_NOT_FOUND = object()

# 各实验必须提供的字段路径（与 docs/experiment_result_contract.md 对齐）
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


def _dig(obj: dict[str, Any], path: tuple[str, ...]) -> Any:
    """沿路径钻取嵌套 dict。键缺失返回 ``_NOT_FOUND``，值为 None 则正常返回 None。"""
    cur: Any = obj
    for key in path:
        if not isinstance(cur, dict):
            return _NOT_FOUND
        if key not in cur:
            return _NOT_FOUND
        cur = cur[key]
    return cur


def validate_result(result: dict[str, Any], exp_id: str) -> list[str]:
    """校验单个实验结果是否满足字段合约。

    Returns:
        缺失字段路径列表；空列表表示通过。
    """
    missing: list[str] = []
    for path in EXPECTED_FIELDS.get(exp_id, []):
        if _dig(result, path) is _NOT_FOUND:
            missing.append(".".join(path))
    return missing


def _latest_result(exp_short: str) -> dict[str, Any] | None:
    candidates = sorted(RESULTS_DIR.glob(f"{exp_short}_*.json"))
    if not candidates:
        return None
    return json.loads(candidates[-1].read_text(encoding="utf-8"))


def check_alignment(targets: list[str] | None = None) -> dict[str, list[str]]:
    """返回 ``{exp_short: [missing_paths]}`` 诊断报告。"""
    exp_list = targets or sorted(EXPECTED_FIELDS)
    report: dict[str, list[str]] = {}
    for exp in exp_list:
        data = _latest_result(exp)
        if data is None:
            report[exp] = ["NO_RESULT_FILE"]
            continue
        report[exp] = validate_result(data, exp)
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


def validate_latest_results(targets: list[str] | None = None, strict: bool = False) -> dict[str, list[str]]:
    """按实验返回最新结果文件的缺失字段诊断。

    Args:
        targets: 指定实验列表；None 表示校验所有已知实验。
        strict: True 时额外标记 computation 不是 ``h100*`` 的结果。
    """
    exp_list = targets or sorted(EXPECTED_FIELDS)
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
        missing.extend(validate_result(data, exp))
        if exp == "exp8":
            if (_dig(data, ("latencies", "int8")) is _NOT_FOUND
                    and _dig(data, ("latencies", "bf16")) is _NOT_FOUND):
                missing.append("latencies.int8|latencies.bf16")
        report[exp] = missing
    return report
