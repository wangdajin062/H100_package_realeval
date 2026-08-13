"""exp1: QAD Production Distillation — Real H100 training."""
from __future__ import annotations
import logging

from experiments.framework import run_with_mode
from experiments.common import (
    load_and_split_dataset,
    multi_seed_std,
    n_seeds_from_config,
    seed_base_from_config,
    set_seed,
)

logger = logging.getLogger("exp1")


def run(config: dict) -> dict:
    split = load_and_split_dataset(config, default_dataset="balanced4k")

    def run_paper(config: dict) -> dict:
        from realeval import real_backend
        import numpy as np

        quantize = config.get("training", {}).get("quantize", "int4")
        apply_ov = config.get("training", {}).get("apply_ov_rescaling", True)
        n_seeds = n_seeds_from_config(config, "exp1")

        f1s: list[float] = []
        accs: list[float] = []
        kls: list[float] = []
        drifts: list[float] = []
        snr_mins: list[float] = []
        snr_maxs: list[float] = []
        trajectory = None
        for s in range(n_seeds):
            set_seed(seed_base_from_config(config) + s)
            result = real_backend.real_qad_distill_train(
                config,
                split.train_texts, split.train_labels,
                split.test_texts, split.test_labels,
                quantize=quantize,
                apply_ov_rescaling=apply_ov,
                save_name="exp1_qad" if s == 0 else None,
            )
            f1s.append(result["f1"])
            accs.append(result["accuracy"])
            kls.append(result["kl_final"])
            drifts.append(result["drift_pct_final"])
            snr_mins.append(result["snr_min"])
            snr_maxs.append(result["snr_max"])
            # trajectory: keep last seed's (per-step sequence not averaged)
            trajectory = result["trajectory"]

        return {
            "computation": "h100_real_qwen",
            "trajectory": trajectory,
            "trajectory_note": "single-seed (last of n_seeds); cross-seed avg not meaningful for per-step curves",
            "f1": round(float(np.mean(f1s)), 4),
            "accuracy": round(float(np.mean(accs)), 4),
            "n_train": result["n_train"],
            "n_test": result["n_test"],
            "kl_final": round(float(np.mean(kls)), 5),
            "kl_final_list": [round(v, 5) for v in kls],
            "drift_pct_final": round(float(np.mean(drifts)), 1),
            "drift_pct_list": [round(v, 1) for v in drifts],
            "kl_plateau": result["kl_plateau"],
            "kl_converged": result["kl_converged"],
            "total_steps": result["total_steps"],
            "ovf_activation_step": result["ovf_activation_step"],
            "snr_min": round(float(np.mean(snr_mins)), 2),
            "snr_max": round(float(np.mean(snr_maxs)), 2),
            "snr_note": "cross-seed mean; single-seed listed in *_list fields",
            "quantize": quantize,
            "is_synthetic": False,
            "std": multi_seed_std(f1s),
            "n_seeds": n_seeds,
            "save_note": "seed-0 checkpoint saved (save_name='exp1_qad'); downstream loads this single weight" if n_seeds > 1 else None,
        }

    return run_with_mode("exp1", config, run_paper)
