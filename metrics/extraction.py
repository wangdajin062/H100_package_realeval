"""metrics/extraction.py — 从实验结果中提取 headline 指标。

paper_pipeline.py 与报告生成器使用本模块聚合论文表格所需的关键数值，
避免在多处重复实现相同的字段钻取逻辑。
"""
from __future__ import annotations

from typing import Any


def extract_headline(short: str, result: dict[str, Any]) -> dict[str, Any]:
    """从单个实验结果中提取 headline 指标，用于论文表格与摘要。

    输出字段与 ``docs/figure_scripts/paper_data.py`` 的读取路径保持一致。
    """
    r = result or {}

    if short == "exp1":
        return {
            "F1": r.get("f1"),
            "kl_final": r.get("kl_final"),
            "drift_pct_final": r.get("drift_pct_final"),
            "kl_plateau": r.get("kl_plateau"),
            "kl_converged": r.get("kl_converged"),
            "total_steps": r.get("total_steps"),
            "ovf_step": r.get("ovf_activation_step"),
            "snr_min": r.get("snr_min"),
            "snr_max": r.get("snr_max"),
        }

    if short == "exp2":
        variants = r.get("variants", {})
        return {
            f"kl_final[{k}]": x.get("kl_final")
            for k, x in variants.items()
            if isinstance(x, dict)
        }

    if short == "exp3":
        conditions = r.get("conditions", {})
        out = {
            f"drift[{k}]": x.get("variance_drift_pct")
            for k, x in conditions.items()
            if isinstance(x, dict)
        }
        if isinstance(r.get("layer_selection"), dict):
            out.update({
                f"f1_layer[{k}]": x.get("f1")
                for k, x in r["layer_selection"].items()
                if isinstance(x, dict)
            })
        return out

    if short == "exp4":
        classifiers = r.get("classifiers", {})
        return {
            f"F1[{k}]": x.get("f1")
            for k, x in classifiers.items()
            if isinstance(x, dict)
        }

    if short == "exp5":
        taf = r.get("taf28k", {}).get("f1")
        if taf is None:
            taf = r.get("balanced4k", {}).get("f1")
        chi = r.get("chifraud", {}).get("f1")
        adv = r.get("advfraud", {}).get("full_pool", {}).get("f1") if isinstance(r.get("advfraud"), dict) else None
        adv_curated = r.get("advfraud", {}).get("curated", {}).get("f1") if isinstance(r.get("advfraud"), dict) else None
        cross_tc = r.get("cross_taf_on_chifraud", {}).get("f1") if isinstance(r.get("cross_taf_on_chifraud"), dict) else None
        cross_ct = r.get("cross_chifraud_on_taf", {}).get("f1") if isinstance(r.get("cross_chifraud_on_taf"), dict) else None
        bf16_matched = r.get("bf16_matched_advfraud")
        out: dict[str, Any] = {}
        if taf is not None:
            out["taf28k"] = taf
        if chi is not None:
            out["chifraud"] = chi
        if adv is not None:
            out["advfraud"] = adv
        if adv_curated is not None:
            out["advfraud_curated"] = adv_curated
        if cross_tc is not None:
            out["cross_taf->chi"] = cross_tc
        if cross_ct is not None:
            out["cross_chi->taf"] = cross_ct
        if bf16_matched is not None:
            out["bf16_matched"] = bf16_matched
        return out or {"cross_taf->chi": None, "cross_chi->taf": None}

    if short == "exp6":
        diagnostic = r.get("diagnostic_B", {})
        hm = diagnostic.get("h100_measured", {}) if isinstance(diagnostic, dict) else {}
        ref = r.get("paper_reference", {})
        out = {}
        if isinstance(hm, dict) and hm.get("generic") is not None:
            out["alpha_generic"] = hm["generic"]
        if isinstance(ref, dict) and ref.get("alpha_generic") is not None:
            out["ref_alpha_generic"] = ref["alpha_generic"]
        if isinstance(ref, dict) and ref.get("alpha_tuned") is not None:
            out["ref_alpha_tuned"] = ref["alpha_tuned"]
        return out or {"alpha_generic": None}

    if short == "exp7":
        return {
            "speaker_id_acc": r.get("speaker_id_accuracy"),
            "asv_eer_pct": r.get("asv_eer_pct"),
        }

    if short == "exp8":
        out = {f"lat_ms[{k}]": v for k, v in r.get("latencies", {}).items()}
        bb = r.get("batch_benchmark", {})
        if bb:
            out["batch_benchmark"] = bb
        return out

    if short == "exp9":
        wc = r.get("with_cot", {})
        wo = r.get("without_cot", {})
        return {
            "cot_f1": wc.get("f1") if isinstance(wc, dict) else None,
            "direct_f1": wo.get("f1") if isinstance(wo, dict) else None,
            "cot_fpr": wc.get("fpr") if isinstance(wc, dict) else None,
            "direct_fpr": wo.get("fpr") if isinstance(wo, dict) else None,
        }

    if short == "exp10":
        scales = r.get("scales", {})
        out = {}
        for k, x in scales.items():
            if not isinstance(x, dict):
                continue
            if x.get("f1_fixed") is not None:
                out[f"F1_fixed[{k}]"] = x["f1_fixed"]
            if x.get("f1_conv") is not None:
                out[f"F1_conv[{k}]"] = x["f1_conv"]
        return out

    if short == "exp11":
        schemes = r.get("schemes", {})
        return {
            f"F1[{k}]": x.get("f1")
            for k, x in schemes.items()
            if isinstance(x, dict) and x.get("f1") is not None
        }

    if short == "exp12":
        comp = r.get("competitor_comparison_real", {})
        storage = r.get("storage_decomposition_point8", {})
        out = {f"F1[{k}]": x.get("f1") for k, x in comp.items() if isinstance(x, dict)}
        footprints = storage.get("footprints_mb", {}) if isinstance(storage, dict) else {}
        for k, v in footprints.items():
            out[f"fp[{k}]"] = v
        if isinstance(storage, dict) and storage.get("total_advantage_x") is not None:
            out["total_advantage_x"] = storage["total_advantage_x"]
        return out

    if short == "exp13":
        strategies = r.get("strategies", {})
        return {
            f"F1[{k}]": x.get("f1")
            for k, x in strategies.items()
            if isinstance(x, dict)
        }

    if short == "exp14":
        models = r.get("models", {})
        return {
            f"F1[{k}]": x.get("f1")
            for k, x in models.items()
            if isinstance(x, dict) and x.get("f1") is not None
        }

    if "f1" in r:
        return {"F1": r["f1"]}

    return {}
