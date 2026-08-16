"""metrics/contract.py — 实验结果 → 图像脚本字段合约校验。

本模块定义 ``docs/figure_scripts/paper_data.py`` 消费的所有字段路径，
并提供 ``validate_result`` / ``check_alignment`` / ``validate_latest_results``
等工具函数。

字段分为两类：
  - MEASURED：必须由实验真实产出的字段（默认强制检查）。
  - CITED：来自论文自引用或外部文献的字段，不视为独立测量；默认不强制，
    但可选择检查其是否存在并单独标注。
"""
from __future__ import annotations

import json
from typing import Any

from realeval.io.paths import RESULTS as RESULTS_DIR

_NOT_FOUND = object()

# 各实验必须真实产出的字段路径（与 docs/experiment_result_contract.md 对齐）
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
        ("variants", "kl_task", "f1"),
        ("variants", "kl_task", "kl_final"),
        ("variants", "kl_task", "std"),
    ],
    "exp3": [
        ("conditions", "no_reg", "f1"),
        ("conditions", "no_reg", "std"),
        ("conditions", "no_reg", "variance_drift_pct"),
        ("conditions", "ov_freeze_full", "f1"),
        ("conditions", "ov_freeze_full", "std"),
        ("conditions", "ov_freeze_full", "variance_drift_pct"),
        ("conditions", "ov_freeze_half", "f1"),
        ("conditions", "ov_freeze_half", "std"),
        ("conditions", "ov_freeze_half", "variance_drift_pct"),
        ("conditions", "ov_freeze_quarter", "f1"),
        ("conditions", "ov_freeze_quarter", "std"),
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
        ("rho_sweep", "rho_0.1", "ppl"),
        ("rho_sweep", "rho_0.2", "f1"),
        ("rho_sweep", "rho_0.2", "ppl"),
        ("rho_sweep", "rho_0.3", "f1"),
        ("rho_sweep", "rho_0.3", "ppl"),
        ("rho_sweep", "rho_0.4", "f1"),
        ("rho_sweep", "rho_0.4", "ppl"),
        ("rho_sweep", "rho_0.5", "f1"),
        ("rho_sweep", "rho_0.5", "ppl"),
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
        ("ldp_tradeoff", "eps_1.5", "f1"),
        ("cross_taf_on_chifraud", "f1"),
        ("cross_chifraud_on_taf", "f1"),
    ],
    "exp6": [
        ("diagnostic_B", "h100_measured", "generic"),
    ],
    "exp7": [
        ("pii_report",),
        ("asv_eer_pct",),
        ("speaker_id_accuracy",),
        # glo_reconstruction_corr is DEMO-only (random projection, no real proj_fn) —
        # deliberately NOT listed here so it is never validated as a MEASURED field
        # (P1-M4). See exp7 glo_reconstruction_is_demo / note.
        ("n_speakers",),
    ],
    "exp8": [
        ("latency_detail", "bf16", "p50_ms"),
        ("latency_detail", "bf16", "p99_ms"),
        ("latency_detail", "fp16", "p50_ms"),
        ("latency_detail", "fp16", "p99_ms"),
        ("latency_detail", "int4", "p50_ms"),
        ("latency_detail", "int4", "p99_ms"),
        ("batch_benchmark",),
    ],
    "exp9": [
        ("with_cot", "f1"),
        ("with_cot", "fpr"),
        ("without_cot", "f1"),
        ("without_cot", "fpr"),
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
        ("schemes", "nvfp4", "f1"),
        ("schemes", "nvfp4", "std"),
    ],
    "exp12": [
        ("competitor_comparison_real", "QAD_MultiGuard_INT4", "f1"),
        # storage 分解键总会产出；但 footprints_mb 依赖磁盘上的模型文件，
        # 缺失时各 advantage 值为 None（键仍存在）。
        ("storage_decomposition_point8", "footprints_mb"),
        ("storage_decomposition_point8", "quantization_alone_x"),
        ("storage_decomposition_point8", "param_scale_alone_x"),
        ("storage_decomposition_point8", "total_advantage_x"),
    ],
    "exp13": [
        ("strategies", "softmax_linear", "f1"),
        ("strategies", "softmax_linear", "accuracy"),
        ("strategies", "softmax_linear", "latency_ms"),
        ("strategies", "sigmoid_linear", "f1"),
        ("strategies", "sigmoid_linear", "accuracy"),
        ("strategies", "sigmoid_linear", "latency_ms"),
        ("strategies", "transformer", "f1"),
        ("strategies", "transformer", "accuracy"),
        ("strategies", "transformer", "latency_ms"),
    ],
    "exp14": [
        ("models", "q4km_0.5b_llama_cpp", "f1"),
        ("models", "q4km_0.5b_llama_cpp", "std"),
    ],
}

# 来自论文自引用或外部文献的字段；不视为本实验的独立测量。
CITED_FIELDS: dict[str, list[tuple[str, ...]]] = {
    "exp5": [
        ("bf16_matched_advfraud",),
    ],
    "exp6": [
        ("paper_reference", "alpha_generic"),
        ("paper_reference", "alpha_tuned"),
        ("paper_reference", "gamma_deploy"),
        ("paper_reference", "speculative_speedups"),
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


def _missing_paths(result: dict[str, Any], exp_id: str, paths: list[tuple[str, ...]]) -> list[str]:
    """返回结果中缺失的字段路径列表。"""
    missing: list[str] = []
    for path in paths:
        if _dig(result, path) is _NOT_FOUND:
            missing.append(".".join(path))
    return missing


def validate_result(
    result: dict[str, Any],
    exp_id: str,
    *,
    include_cited: bool = False,
) -> dict[str, list[str]]:
    """校验单个实验结果是否满足字段合约。

    Returns:
        {"measured": [...], "cited": [...]}，分别为缺失的 measured / cited 字段路径。
    """
    out: dict[str, list[str]] = {"measured": _missing_paths(result, exp_id, EXPECTED_FIELDS.get(exp_id, []))}
    if include_cited:
        out["cited"] = _missing_paths(result, exp_id, CITED_FIELDS.get(exp_id, []))
    return out


def _latest_result(exp_short: str) -> dict[str, Any] | None:
    candidates = sorted(RESULTS_DIR.glob(f"{exp_short}_*.json"))
    if not candidates:
        return None
    try:
        return json.loads(candidates[-1].read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # Treat a corrupt/truncated result file as missing rather than crashing
        # contract validation (matches orchestrator/report tolerance).
        return None


def check_alignment(
    targets: list[str] | None = None,
    *,
    include_cited: bool = False,
) -> dict[str, dict[str, list[str]]]:
    """返回 ``{exp_short: {"measured": [...], "cited": [...]}}`` 诊断报告。"""
    exp_list = targets or sorted(EXPECTED_FIELDS)
    report: dict[str, dict[str, list[str]]] = {}
    for exp in exp_list:
        data = _latest_result(exp)
        if data is None:
            report[exp] = {"measured": ["NO_RESULT_FILE"], "cited": []}
            continue
        report[exp] = validate_result(data, exp, include_cited=include_cited)
    return report


def print_alignment_report(
    report: dict[str, dict[str, list[str]]],
    *,
    include_cited: bool = False,
) -> bool:
    """打印对齐报告，返回是否有 measured 失败项。"""
    failed = False
    for exp, items in sorted(report.items()):
        measured = items.get("measured", [])
        cited = items.get("cited", []) if include_cited else []
        if measured:
            failed = True
            print(f"[FAIL] {exp}")
            for item in measured:
                print(f"  - {item}")
        elif cited:
            print(f"[PASS] {exp}  (cited missing: {cited})")
        else:
            print(f"[PASS] {exp}")
    return failed


def validate_latest_results(
    targets: list[str] | None = None,
    *,
    strict: bool = False,
    include_cited: bool = False,
) -> dict[str, list[str]]:
    """按实验返回最新结果文件的缺失字段诊断。

    Args:
        targets: 指定实验列表；None 表示校验所有已知实验。
        strict: True 时额外标记 computation 不是 ``h100*`` 的结果。
        include_cited: True 时同时检查 cited 字段。

    Returns:
        {exp_short: [diagnostic_strings]}，为与旧 CLI 兼容的扁平列表格式。
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

        validated = validate_result(data, exp, include_cited=include_cited)
        missing.extend(validated["measured"])
        if include_cited and validated.get("cited"):
            missing.extend(f"CITED:{c}" for c in validated["cited"])

        if exp == "exp8":
            if (_dig(data, ("latencies", "int8")) is _NOT_FOUND
                    and _dig(data, ("latencies", "bf16")) is _NOT_FOUND):
                missing.append("latencies.int8|latencies.bf16")
        report[exp] = missing
    return report
