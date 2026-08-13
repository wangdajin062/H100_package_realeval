"""exp11: Quantization Scheme — Compare FP16, INT8, INT4, NF4."""
from __future__ import annotations
import logging
from experiments.framework import leakage_safe_split, load_first_nonempty, run_with_mode

logger = logging.getLogger("exp11")


def run(config: dict) -> dict:
    from realeval import data
    # TAF-28k is audio-only (no per-sample text); text distillation uses the configured text corpus.
    dataset_name = config.get("data", {}).get("dataset", "balanced4k")
    max_samples = config.get("data", {}).get("max_samples")
    ds = load_first_nonempty(
        loaders=[lambda: data.load_dataset(dataset_name, max_samples=max_samples)],
        synthetic_loader=lambda: data.load_synthetic(n=200),
    )
    split = leakage_safe_split(ds, test_ratio=0.2, seed=42)

    def run_paper(config: dict) -> dict:
        from realeval import real_backend
        import numpy as np
        from experiments.common import (
            multi_seed_std, n_seeds_from_config, resolve_qad_path, seed_base_from_config, set_seed,
        )

        qad_path = resolve_qad_path()
        n_seeds = n_seeds_from_config(config, "exp11")
        schemes = {}
        quant_schemes = [
            ("bf16", "bf16"),
            ("fp16", "fp16"),
            ("int8", "int8"),
            ("int4", "int4"),
            ("nf4", "nf4"),
        ]
        for scheme_name, quant_arg in quant_schemes:
            try:
                f1s, accs = [], []
                for s in range(n_seeds):
                    set_seed(seed_base_from_config(config) + s)
                    result = real_backend.real_llm_classify(
                        config, split.test_texts, split.test_labels,
                        quantize=quant_arg,
                        finetuned_path=str(qad_path) if qad_path.exists() else None,
                    )
                    f1s.append(result["f1"])
                    accs.append(result["accuracy"])
                schemes[scheme_name] = {
                    "f1": round(float(np.mean(f1s)), 4),
                    "std": multi_seed_std(f1s),
                    "accuracy": round(float(np.mean(accs)), 4),
                    "n_seeds": n_seeds,
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
