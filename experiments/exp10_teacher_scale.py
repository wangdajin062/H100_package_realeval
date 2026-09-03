"""exp10: Teacher Scale — Compare 0.5B / 1.5B / 3B / 7B teachers."""
from __future__ import annotations
import logging
from experiments.framework import leakage_safe_split, load_first_nonempty, run_with_mode

logger = logging.getLogger("exp10")


def run(config: dict) -> dict:
    from realeval import data
    ds = load_first_nonempty(
        loaders=[lambda: data.load_taf28k()],
        synthetic_loader=lambda: data.load_synthetic(n=200),
    )
    split = leakage_safe_split(ds, test_ratio=0.1, seed=42)

    def run_paper(config: dict) -> dict:
        from realeval import real_backend
        import numpy as np
        from experiments.common import config_override, multi_seed_std, n_seeds_from_config, seed_base_from_config, set_seed
        models_cfg = config.get("models", {})

        n_seeds = n_seeds_from_config(config, "exp10")

        # Teacher-scale ablation: each teacher trains the same student.
        # Two scenarios per teacher:
        #   f1_fixed: limited training (fixed token budget, 1 epoch)
        #   f1_conv:  full training to convergence (5 epochs)
        teacher_keys = [
            ("teacher",        models_cfg.get("teacher")),
            ("teacher_1.5b",   models_cfg.get("teacher_1.5b")),
            ("teacher_3b",     models_cfg.get("teacher_3b")),
            ("teacher_7b",     models_cfg.get("teacher_7b")),
        ]

        # Fixed token budget (paper Fig5b "Fixed 0.5B tokens"): the fixed arm trains each
        # teacher for a fixed 0.5B-token budget (audit P1-6 — was 1 epoch ≈ tens of M
        # tokens, two orders of magnitude short). epochs is set high as a safety ceiling;
        # the token budget (max_train_tokens below), not the epoch count, terminates
        # training.
        fixed_config = config_override(config, training={"epochs": 1000})
        conv_config = config_override(config, training={"epochs": 5})

        scales = {}
        for key, model_id in teacher_keys:
            if not model_id:
                continue
            try:
                fixed_f1s, conv_f1s, conv_accs = [], [], []
                fixed_tokens = conv_tokens = None
                for s in range(n_seeds):
                    set_seed(seed_base_from_config(config) + s)
                    # Fixed token budget (0.5B tokens, paper Fig5b)
                    fixed_result = real_backend.real_qad_distill_train(
                        fixed_config,
                        split.train_texts, split.train_labels,
                        split.test_texts, split.test_labels,
                        quantize="nvfp4",
                        teacher_model=model_id,
                        max_train_tokens=500_000_000,
                    )
                    fixed_f1s.append(fixed_result["f1"])
                    fixed_tokens = fixed_result.get("train_tokens")
                    # To convergence (5 epochs)
                    conv_result = real_backend.real_qad_distill_train(
                        conv_config,
                        split.train_texts, split.train_labels,
                        split.test_texts, split.test_labels,
                        quantize="nvfp4",
                        teacher_model=model_id,
                    )
                    conv_f1s.append(conv_result["f1"])
                    conv_accs.append(conv_result["accuracy"])
                    conv_tokens = conv_result.get("train_tokens")
                scales[key] = {
                    "f1_fixed": round(float(np.mean(fixed_f1s)), 4),
                    "f1_conv": round(float(np.mean(conv_f1s)), 4),
                    "accuracy": round(float(np.mean(conv_accs)), 4),
                    "std": multi_seed_std(conv_f1s),
                    "n_seeds": n_seeds,
                    "teacher_model": model_id,
                    "train_tokens_fixed": fixed_tokens,
                    "train_tokens_conv": conv_tokens,
                }
            except Exception as e:
                logger.warning("Teacher scale %s (%s) failed: %s", key, model_id, e)
                scales[key] = {"f1_fixed": None, "f1_conv": None, "error": str(e)}

        return {
            "computation": "h100_real_qwen",
            "scales": scales,
        }


    return run_with_mode("exp10", config, run_paper)
