"""exp11: Quantization Scheme — Compare FP16, INT8, INT4, NF4 (PTQ) vs NVFP4/NBE (QAT)."""
from __future__ import annotations
import logging
from experiments.framework import load_first_nonempty, run_with_mode

logger = logging.getLogger("exp11")


def run(config: dict) -> dict:
    from realeval import data
    # Paper main results are evaluated on TAF-28k (voice-text pairs, 28,511 samples).
    # Text distillation uses the TAF-28k text field (taf28k.jsonl), not a separate corpus.
    dataset_name = config.get("data", {}).get("dataset", "taf28k")
    max_samples = config.get("data", {}).get("max_samples")
    ds = load_first_nonempty(
        loaders=[lambda: data.load_dataset(dataset_name, max_samples=max_samples)],
        synthetic_loader=lambda: data.load_synthetic(n=200),
    )
    from experiments.common import shared_test_split
    texts, labels = ds.texts, ds.labels
    # Leakage-safe: reuse exp1's persisted TAF-28k held-out test partition (shared
    # manifest), not a fresh positional split — keeps eval from overlapping training
    # data and matches exp14/exp5 (audit P2: exp11 不走共享 manifest)。
    test_texts, test_labels = shared_test_split(dataset_name, texts, labels)
    # 独立 INT4 QAD 训练臂需要训练集（全集减去泄漏安全的 test 补集），audit P1-10。
    from experiments.common import shared_test_indices
    test_idx = shared_test_indices(dataset_name, texts, labels)
    _test_set = set(test_idx)
    train_idx = [i for i in range(len(texts)) if i not in _test_set]
    train_texts = [texts[i] for i in train_idx]
    train_labels = [labels[i] for i in train_idx]

    def run_paper(config: dict) -> dict:
        from realeval import real_backend
        from experiments.common import multi_seed_std, resolve_qad_path

        qad_path = resolve_qad_path()
        schemes = {}
        # 推理确定性（eval + greedy/head.predict，无采样）：多 seed 推理是空转——
        # set_seed 不改变确定性前向输出，std 恒为 0.0。论文的 5-seed ±std 由
        # claim_engine 在训练侧多 seed 实现（_run_experiment_seeds 每次跑完整实验），
        # 非本处推理侧多 seed。故单次推理并如实标 n_seeds=1、std=None（audit P2）。

        # ── 同质 INT4 QAD（独立训练臂，audit P1-10）────────────────────────────
        # 论文 Fig4a 的「Homogeneous INT4」是端到端用 quantize="int4"（bitsandbytes
        # PTQ + LoRA adapter）独立训练的 QAD 学生，而非用 NVFP4-QAD 产物在推理侧
        # 再量化为 int4（那会得到「异构」语义，也是旧 0.6172 陈旧值的来源）。
        try:
            int4_result = real_backend.real_qad_distill_train(
                config, train_texts, train_labels, test_texts, test_labels,
                quantize="int4", save_name="exp11_int4_qad",
            )
            schemes["int4"] = {
                "f1": round(float(int4_result["f1"]), 4),
                "std": multi_seed_std([int4_result["f1"]]),
                "accuracy": round(float(int4_result["accuracy"]), 4),
                "n_seeds": 1,
                "trained_scheme": "int4",
            }
        except Exception as e:
            logger.warning("Homogeneous INT4 QAD training failed: %s", e)
            schemes["int4"] = {"f1": None, "std": None, "error": str(e)}

        # ── 推理侧量化诊断（同一 NVFP4-QAD 学生在不同推理精度下的鲁棒性）──────
        # bf16/fp16/int8/nf4/nvfp4 不是独立训练的量化方案，而是 exp1 的 NVFP4-QAD
        # 产物（qad_path）在不同推理 dtype / bitsandbytes 量化下的确定性诊断
        # （audit P1-10）。诚实标注 trained_scheme="nvfp4_qad"。
        quant_schemes = [
            ("bf16", "bf16"),
            ("fp16", "fp16"),
            ("int8", "int8"),
            ("nf4", "nf4"),
            ("nvfp4", "nvfp4"),
        ]
        for scheme_name, quant_arg in quant_schemes:
            try:
                result = real_backend.real_llm_classify(
                    config, test_texts, test_labels,
                    quantize=quant_arg,
                    finetuned_path=str(qad_path) if qad_path.exists() else None,
                )
                schemes[scheme_name] = {
                    "f1": round(float(result["f1"]), 4),
                    "std": multi_seed_std([result["f1"]]),
                    "accuracy": round(float(result["accuracy"]), 4),
                    "n_seeds": 1,
                    "trained_scheme": "nvfp4_qad",
                }
            except Exception as e:
                logger.warning("Quantisation scheme %s failed: %s", scheme_name, e)
                schemes[scheme_name] = {"f1": None, "std": None, "error": str(e)}

        return {
            "computation": "h100_real_qwen",
            "schemes": schemes,
            "model_source": str(qad_path) if qad_path.exists() else "not_found",
        }

    return run_with_mode("exp11", config, run_paper)
