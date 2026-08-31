"""exp5: Cross-Dataset — Evaluate on TAF-28k, ChiFraud, AdvFraud-3k."""
from __future__ import annotations
import logging

from experiments.framework import load_first_nonempty, run_with_mode
from experiments.common import resolve_qad_path

logger = logging.getLogger("exp5")


def run(config: dict) -> dict:
    from realeval import data
    max_samples = config.get("data", {}).get("max_samples", 2000)
    taf_ds = data.load_taf28k(max_samples=max_samples)
    chi_ds = data.load_chifraud(max_samples=max_samples)
    if not chi_ds["texts"]:
        logger.warning("ChiFraud text JSONL missing; using balanced4k as Chinese-fraud proxy for exp5")
        chi_ds = data.load_chifraud_balanced(max_samples=max_samples)
    datasets = {
        "taf28k": taf_ds,
        "chifraud": chi_ds,
        "advfraud3k": data.load_advfraud3k(max_samples=max_samples),
    }

    def run_paper(config: dict) -> dict:
        from realeval import real_backend, models
        from experiments.common import seed_base_from_config, set_seed, shared_test_split
        real_backend.require_assets(models.models_available(config), "Real Qwen weights unavailable")

        # Seed the global RNG so the LDP calibrated-noise measurement (and any other
        # stochastic backend path) is reproducible whether exp5 runs standalone or in
        # the pipeline. Without this the ldp_tradeoff curve varied run-to-run.
        set_seed(seed_base_from_config(config))

        qad_path = resolve_qad_path()
        finetuned_path = str(qad_path) if qad_path.exists() else None

        # Leakage-safe TAF-28k test partition (P1-M1): the exp1-trained nvfp4 model is
        # evaluated only on exp1's held-out set, never on its training data. Reused for
        # the AdvFraud normal-sample pool, the cross-dataset eval, and the LDP sweep.
        taf_ds_all = datasets.get("taf28k", {})
        taf_test_texts, taf_test_labels = [], []
        if taf_ds_all.get("texts"):
            taf_test_texts, taf_test_labels = shared_test_split(
                "taf28k", taf_ds_all["texts"], taf_ds_all["labels"])

        results = {}
        for dname, ds in datasets.items():
            if not ds["texts"]:
                continue

            if dname == "advfraud3k" and taf_test_texts:
                n_adv = len(ds["texts"])
                # Normal (label 0) samples drawn from TAF's held-out TEST set, so they
                # are never part of exp1's training data (previous code took a positional
                # tail of ALL taf, ~80% of which sat in exp1's train split).
                normal_texts = [t for t, l in zip(taf_test_texts, taf_test_labels) if l == 0][:n_adv]
                # AdvFraud is not a training set, so a stratified group_split test slice
                # is a clean held-out sample of it.
                adv_test_texts, adv_test_labels = shared_test_split("advfraud3k", ds["texts"], ds["labels"])
                if normal_texts:
                    mixed_texts = adv_test_texts + normal_texts
                    mixed_labels = list(adv_test_labels) + [0] * len(normal_texts)
                    result = real_backend.real_llm_classify(
                        config, mixed_texts, mixed_labels, quantize="nvfp4",
                        finetuned_path=finetuned_path,
                    )
                    results[dname] = {"f1": result["f1"], "accuracy": result["accuracy"],
                                      "n_samples": n_adv,
                                      "note": f"本地 AdvFraud 总样本 {n_adv} 条（非论文声称 3,000）"}

                    # 注意（audit P1-1）：本地 AdvFraud 数据为 2,119 条（119 S1–S8 对抗改写 +
                    # 2,000 novel_template），非论文声称的 3,000 条；且 review_status 全为
                    # pending、无人工过滤标注。「curated 517」取前 517 条作占位近似，并非
                    # 论文所述「人工过滤排除语法损坏/生成痕迹」的高质量子集——待数据补齐
                    # 并人工复核后再回填真实 curated 子集。
                    curated_n = min(517, n_adv)
                    curated_texts = ds["texts"][:curated_n] + normal_texts[:curated_n]
                    curated_labels = ds["labels"][:curated_n] + [0] * min(curated_n, len(normal_texts))
                    curated_result = real_backend.real_llm_classify(
                        config, curated_texts, curated_labels, quantize="nvfp4",
                        finetuned_path=finetuned_path,
                    )
                    results["advfraud_curated"] = {
                        "f1": curated_result["f1"], "accuracy": curated_result["accuracy"],
                        "note": "占位近似：本地数据无人工过滤标注（review_status 全 pending），"
                                "前 517 条非论文所述人工过滤子集。",
                    }
                else:
                    adv_test_texts, adv_test_labels = shared_test_split("advfraud3k", ds["texts"], ds["labels"])
                    result = real_backend.real_llm_classify(
                        config, adv_test_texts, adv_test_labels, quantize="nvfp4",
                        finetuned_path=finetuned_path,
                    )
                    results[dname] = {"f1": result["f1"], "accuracy": result["accuracy"], "note": "fraud-only"}
            else:
                test_texts, test_labels = shared_test_split(dname, ds["texts"], ds["labels"])
                result = real_backend.real_llm_classify(
                    config, test_texts, test_labels, quantize="nvfp4",
                    finetuned_path=finetuned_path,
                )
                results[dname] = {"f1": result["f1"], "accuracy": result["accuracy"]}

        out = {"computation": "h100_real_qwen",
               "model_source": "exp1_qad" if finetuned_path else "base_qwen"}
        if "taf28k" in results:
            out["taf28k"] = results["taf28k"]
        if "chifraud" in results:
            out["chifraud"] = results["chifraud"]
        if "advfraud3k" in results:
            out["advfraud"] = {"full_pool": results["advfraud3k"]}
        if "advfraud_curated" in results:
            out.setdefault("advfraud", {})["curated"] = results["advfraud_curated"]
        if "taf28k" in results and "chifraud" in results:
            cross_tc = real_backend.real_llm_classify(
                config, datasets["chifraud"]["texts"], datasets["chifraud"]["labels"],
                quantize="nvfp4", finetuned_path=finetuned_path,
            )
            # Evaluate the taf-trained model on TAF's held-out test set (not the full
            # corpus, which is ~80% training data) — cross_tc stays on all of ChiFraud,
            # which the model never trained on, so no leakage there.
            cross_ct = real_backend.real_llm_classify(
                config, taf_test_texts, taf_test_labels,
                quantize="nvfp4", finetuned_path=finetuned_path,
            )
            out["cross_taf_on_chifraud"] = {"f1": cross_tc["f1"]}
            out["cross_chifraud_on_taf"] = {"f1": cross_ct["f1"]}

        # CITED (not measured): paper-claimed BF16 baseline on the AdvFraud curated subset.
        # No full BF16 run on that subset exists in this suite, so this is a self-citation
        # constant, mirrored in docs/figure_scripts/paper_data.py::_FIG8_REF and classified
        # CITED in metrics/contract.py. Emitted here only so consistency_check flags it as a
        # cited value; it must NEVER be presented as an independent measurement.
        out["bf16_matched_advfraud"] = 0.882
        # ── LDP trade-off (paper Fig4c) ──
        # Paper Sec. discussion defines the edge-side Gaussian mechanism DIRECTLY by its
        # noise standard deviation σ = 1.0 (applied once to the 128-d acoustic embedding),
        # and reports ε = 1.5 / δ = 1e-5 as an ENGINEERING ESTIMATE under a fixed
        # sensitivity-and-clipping convention — explicitly "not a full differential-privacy
        # analysis". σ is the primary knob; ε is a derived label. We therefore set σ
        # directly, instead of inverting ε → σ via the Gaussian-DP formula
        # (σ = Δf·√(2·ln(1.25/δ))/ε with an assumed Δf=10 produced σ≈32.3 for ε=1.5,
        # contradicting the paper's σ=1.0 by ~32×).
        if taf_test_texts:
            # LDP runs on TAF's held-out test partition (leakage-safe), same set used for
            # the taf28k headline and cross-eval above.
            ttx, tly = taf_test_texts, taf_test_labels
            ldp_out = {}
            # σ=0.0 = LDP disabled (the main-results configuration); σ=1.0 = the paper's
            # single LDP operating point (ε=1.5 is its engineering estimate, δ=1e-5).
            # Noise is added to the hidden states before the classification head — a
            # text-branch approximation of the paper's edge-side embedding perturbation.
            for sigma in (0.0, 1.0):
                r = real_backend.real_llm_classify(
                    config, ttx, tly, quantize="nvfp4",
                    finetuned_path=finetuned_path, noise_sigma=sigma,
                )
                key = "no_ldp" if sigma == 0.0 else "eps_1.5"
                entry = {"sigma": sigma, "f1": r["f1"]}
                if sigma > 0.0:
                    entry.update({"epsilon_est": 1.5, "delta": 1e-5})
                ldp_out[key] = entry
            out["ldp_tradeoff"] = ldp_out
            out["ldp_note"] = (
                "Gaussian noise σ applied to UNCLIPPED hidden states before the "
                "classification head; σ=1.0 is the paper's single LDP operating point. "
                "Since the hidden states are not clipped, the sensitivity is unbounded, "
                "so ε=1.5 / δ=1e-5 is an engineering estimate under an assumed "
                "sensitivity/clipping convention, NOT a certified (ε,δ)-DP guarantee "
                "(audit P2-9).")
        else:
            out["ldp_tradeoff"] = {"note": "TAF-28k unavailable; LDP not measured"}

        return out

    return run_with_mode("exp5", config, run_paper)
