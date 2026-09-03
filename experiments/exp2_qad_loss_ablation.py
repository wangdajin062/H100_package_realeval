"""exp2: QAD Loss Ablation — Compare KL, MSE, and combined distillation losses."""
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

logger = logging.getLogger("exp2")


def run(config: dict) -> dict:
    split = load_and_split_dataset(config, default_dataset="taf28k")

    def run_paper(config: dict) -> dict:
        from realeval import real_backend
        import numpy as np

        # Loss ablation keeps every training hyper-parameter identical to exp1
        # (paper §Loss Function Ablation: "all other training hyper-parameters remain
        # identical"), so epochs follows the config default (=5), matching exp1.
        abl_config = config
        n_seeds = n_seeds_from_config(abl_config, "exp2")

        loss_specs = [
            ("kl_only", "pure_kl"),          # 论文 "Pure KL (ours)"：纯 KL，无 CE 项
            ("kl_task", "kl"),               # 论文 "KL + task reg"：CE + KL
            ("mse_only", "mse"),             # 论文 "Logits MSE"
            ("ce_only", "ce"),               # 论文 "Cross-entropy (QAT)"
            ("kl_mse_combined", "kl_mse"),   # 论文 "Three-term mixture"
        ]
        variants: dict[str, dict] = {}
        for loss_name, loss_fn in loss_specs:
            # All variants use consistent OVF setting (off) — OVF is tested separately
            # in exp3; mixing it here confounds loss-function comparison.
            use_ovf = False
            f1s, kls = [], []
            for s in range(n_seeds):
                set_seed(seed_base_from_config(config) + s)
                result = real_backend.real_qad_distill_train(
                    abl_config,
                    split.train_texts, split.train_labels,
                    split.test_texts, split.test_labels,
                    quantize="nvfp4", apply_ov_rescaling=use_ovf,
                    loss_fn=loss_fn,
                )
                f1s.append(float(result["f1"]))
                kls.append(float(result["kl_final"]))
            variants[loss_name] = {
                "f1": round(float(np.mean(f1s)), 4),
                "f1_list": [round(v, 4) for v in f1s],
                "kl_final": round(float(np.mean(kls)), 5),
                "std": multi_seed_std(f1s),
                "n_seeds": n_seeds,
            }

        return {"computation": "h100_real_qwen", "variants": variants}

    return run_with_mode("exp2", config, run_paper)
