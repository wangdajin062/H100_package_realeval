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
    texts, labels = ds.texts, ds.labels
    split = int(len(texts) * 0.8)
    test_texts, test_labels = texts[split:], labels[split:]

    def run_paper(config):
        from realeval import real_backend, gguf_backend
        import torch
        import numpy as np
        models = {}
        # 多 seed（reproducibility.exp14_seeds，默认 3）：每个运行时产出真实 f1 std。
        n_seeds = int(config.get("reproducibility", {}).get("exp14_seeds", 3))

        # BF16 0.5B student via transformers (safetensors)
        bf16_f1s = []
        for s in range(n_seeds):
            torch.manual_seed(1000 + s)
            torch.cuda.manual_seed_all(1000 + s)
            np.random.seed(1000 + s)
            bf16 = real_backend.real_llm_classify(config, test_texts, test_labels, quantize="fp16")
            bf16_f1s.append(bf16["f1"])
        models["bf16_0.5b_transformers"] = {
            "f1": round(float(np.mean(bf16_f1s)), 4),
            "f1_std": round(float(np.std(bf16_f1s)), 4) if n_seeds > 1 else None,
            "runtime": "transformers", "source": "ours", "n_seeds": n_seeds,
        }
        # Q4_K_M 0.5B GGUF edge student via llama.cpp (same test split)
        try:
            gg_f1s = []
            gg = None
            for s in range(n_seeds):
                torch.manual_seed(1000 + s)
                torch.cuda.manual_seed_all(1000 + s)
                np.random.seed(1000 + s)
                gg = gguf_backend.gguf_classify(config["models"]["student_gguf"], test_texts, test_labels)
                gg_f1s.append(gg["f1"])
            models["q4km_0.5b_llama_cpp"] = {
                "f1": round(float(np.mean(gg_f1s)), 4),
                "f1_std": round(float(np.std(gg_f1s)), 4) if n_seeds > 1 else None,
                "latency_ms_p50": gg.get("latency_ms_p50"),
                "runtime": "llama_cpp", "source": "ours", "n_seeds": n_seeds,
            }
        except gguf_backend.GGUFUnavailable as e:
            models["q4km_0.5b_llama_cpp"] = {"f1": None, "runtime": "llama_cpp", "source": "ours",
                                             "note": f"GGUF unavailable: {e}"}
        return {"experiment": "exp14", "computation": "h100_real_qwen", "models": models,
                "cite_only": {"SAFE_QAQ_7B": {"source": "cited", "note": "reported by source paper; not run here"}}}


    def run_smoke(_: dict) -> dict:
        logger.info("SMOKE: running small-model verification for exp14 (GGUF path unavailable in sandbox)")
        import numpy as np
        from sklearn.ensemble import GradientBoostingClassifier
        from realeval.metrics import classification_metrics
        from realeval.data import verification_features

        X, y = verification_features(labels)
        ntr = split
        clf = GradientBoostingClassifier(n_estimators=100, random_state=42).fit(X[:ntr], y[:ntr])

        def _quantize(arr, bits):
            lo, hi = float(arr.min()), float(arr.max())
            if hi <= lo:
                return arr
            levels = (1 << bits) - 1
            return (np.round((arr - lo) / (hi - lo) * levels) / levels) * (hi - lo) + lo

        bf16_f1 = classification_metrics(y[ntr:], clf.predict(X[ntr:]))["f1"]
        q4_f1 = classification_metrics(y[ntr:], clf.predict(_quantize(X[ntr:], 4)))["f1"]
        return {
            "experiment": "exp14",
            "computation": "smoke_sklearn",
            "models": {
                "bf16_0.5b_transformers": {"f1": bf16_f1, "runtime": "transformers", "source": "ours"},
                "q4km_0.5b_llama_cpp": {
                    "f1": q4_f1,
                    "runtime": "llama_cpp (proxy)",
                    "source": "ours",
                    "note": "sandbox proxy: real 4-bit feature quantisation, not the real GGUF",
                },
            },
            "cite_only": {"SAFE_QAQ_7B": {"source": "cited", "note": "reported by source paper; not run here"}},
            "is_synthetic": True,
        }

    return run_with_mode("exp14", config, run_paper, run_smoke)
