"""exp14: Multi-model same-data comparison — BF16 (transformers) vs Q4_K_M GGUF (llama.cpp).

Runs the SAME TAF-28k test split through multiple runtimes and reports F1 side by side with an explicit
`runtime` and `source` label per entry, so the comparison is honest about what was actually executed:
  - the BF16 0.5B student (transformers / safetensors)     -> source=ours, runtime=transformers
  - the Q4_K_M 0.5B GGUF edge student (llama.cpp)           -> source=ours, runtime=llama_cpp
  - cite-only baselines (e.g. SAFE-QAQ 7B) are NOT run here; they are reported from their source papers.

In the sandbox (no GPU / no model files) the GGUF path degrades gracefully and a real
verification-features quantisation proxy is used instead, clearly labelled as such.
"""
from __future__ import annotations
import logging

from experiments.framework import load_first_nonempty, run_with_mode

logger = logging.getLogger("exp14")


def run(config: dict) -> dict:
    from realeval import data
    # The paper compares runtimes on the SAME TAF-28k test split.
    ds = load_first_nonempty(
        loaders=[lambda: data.load_taf28k(max_samples=config.get("data", {}).get("max_samples", 2000))],
        synthetic_loader=lambda: data.load_synthetic(n=200),
    )
    from experiments.common import shared_test_split
    texts, labels = ds.texts, ds.labels
    # Leakage-safe: evaluate on exp1's held-out TAF-28k test partition (persisted split
    # manifest), not a positional tail that overlaps exp1's training data (P1-M1). This
    # makes the docstring's "SAME TAF-28k test split" claim actually true.
    test_texts, test_labels = shared_test_split("taf28k", texts, labels)

    def run_paper(config: dict) -> dict:
        from realeval import real_backend, gguf_backend
        from experiments.common import multi_seed_std, resolve_qad_path, resolve_qad_gguf_path

        models = {}
        qad_path = resolve_qad_path()
        finetuned_path = str(qad_path) if qad_path.exists() else None

        # 推理确定性（eval + greedy/head.predict，temperature=0，无采样）：多 seed
        # 推理是空转——set_seed 不改变确定性前向输出，std 恒为 0.0。论文的 5-seed
        # ±std 属训练侧随机性（5 个不同 seed 训练出的模型各自评估），非推理侧多
        # seed。故此处单次推理并如实标 n_seeds=1、std=None（audit P2: 多 seed 空转）。
        # 单次推理也顺带消除了旧代码每次 seed 重复加载 GGUF 的问题。
        bf16 = real_backend.real_llm_classify(
            config, test_texts, test_labels, quantize=None,
            finetuned_path=finetuned_path, finetuned_dtype="bf16",
        )
        models["bf16_0.5b_transformers"] = {
            "f1": round(float(bf16["f1"]), 4),
            "f1_std": multi_seed_std([bf16["f1"]]),
            "std": multi_seed_std([bf16["f1"]]),
            "runtime": "transformers", "source": "ours", "n_seeds": 1,
        }
        # Q4_K_M 0.5B GGUF edge student via llama.cpp (same test split).
        # 论文 "Q4_K_M QAD + OV-Freeze" 行是 QAD 训练产物导出为 Q4_K_M GGUF
        # （scripts/export_to_gguf.py），而非 config.models.student_gguf 的 stock 官方
        # GGUF（那是 zero-shot、无蒸馏，语义错位，audit P1-11）。用导出的 QAD GGUF
        # 推理；导出产物缺失时诚实报缺（GGUFUnavailable），不静默退回 stock。
        # 残留：导出链默认源为 exp1_qad（无 OVF 的 QAD）；若论文行需 OVF 产物，须
        # 用 exp3 的 ov_freeze_full 产物另行导出（audit P1-15 统一）。
        qad_gguf = resolve_qad_gguf_path()
        try:
            gg = gguf_backend.gguf_classify(str(qad_gguf), test_texts, test_labels)
            models["q4km_0.5b_llama_cpp"] = {
                "f1": round(float(gg["f1"]), 4),
                "f1_std": multi_seed_std([gg["f1"]]),
                "std": multi_seed_std([gg["f1"]]),
                "latency_ms_p50": gg.get("latency_ms_p50"),
                "runtime": "llama_cpp", "source": "ours", "n_seeds": 1,
                "model_ref": qad_gguf.name,
            }
        except (gguf_backend.GGUFUnavailable, KeyError) as e:
            # KeyError = gguf_classify returned no "f1"; degrade the same way as an
            # unavailable backend instead of aborting the whole experiment.
            models["q4km_0.5b_llama_cpp"] = {"f1": None, "runtime": "llama_cpp", "source": "ours",
                                             "note": f"QAD GGUF unavailable: {e}"}
        return {"computation": "h100_real_qwen", "models": models,
                "model_source": "exp1_qad" if finetuned_path else "base_qwen",
                "cite_only": {"SAFE_QAQ_7B": {"source": "cited", "note": "reported by source paper; not run here"}}}


    return run_with_mode("exp14", config, run_paper)
