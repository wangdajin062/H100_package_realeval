"""exp2: QAD Loss Ablation — Compare KL, MSE, and combined distillation losses."""
from __future__ import annotations
import logging

from experiments.framework import run_with_mode
from experiments.common import (
    config_override,
    load_and_split_dataset,
    multi_seed_std,
    n_seeds_from_config,
    set_seed,
)

logger = logging.getLogger("exp2")


def run(config: dict) -> dict:
    split = load_and_split_dataset(config, default_dataset="balanced4k")

    def run_paper(config: dict) -> dict:
        from realeval import real_backend
        import numpy as np

        abl_config = config_override(config, training={"epochs": 3})
        n_seeds = n_seeds_from_config(abl_config, "exp2")

        loss_specs = [
            ("kl_only", "kl"),
            ("mse_only", "mse"),
            ("ce_only", "ce"),
            ("kl_mse_combined", "kl_mse"),
            # kl_task removed: was identical to kl_only except for OVF toggle,
            # which confounded loss ablation with OVF ablation (§1.1 code_review_20260803).
        ]
        variants: dict[str, dict] = {}
        for loss_name, loss_fn in loss_specs:
            # All variants use consistent OVF setting (off) — OVF is tested separately
            # in exp3; mixing it here confounds loss-function comparison.
            use_ovf = False
            f1s, kls = [], []
            for s in range(n_seeds):
                set_seed(1000 + s)
                result = real_backend.real_qad_distill_train(
                    abl_config,
                    split.train_texts, split.train_labels,
                    split.test_texts, split.test_labels,
                    quantize="int4", apply_ov_rescaling=use_ovf,
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

        # Backward-compatible alias: fig5 still references "kl_task" historically.
        # It is identical to kl_only in this ablation (OVF is varied separately in exp3).
        if "kl_only" in variants and "kl_task" not in variants:
            variants["kl_task"] = dict(variants["kl_only"])

        return {"computation": "h100_real_qwen", "variants": variants}

    def run_smoke(_: dict) -> dict:
        logger.info("SMOKE: running small-model verification for exp2")
        import torch
        import torch.nn.functional as F
        from sklearn.ensemble import GradientBoostingClassifier
        from realeval.metrics import classification_metrics
        from realeval.data import verification_features

        X, y = verification_features(split.train_labels + split.test_labels)
        ntr = len(split.train_labels)
        clf = GradientBoostingClassifier(n_estimators=100, random_state=42).fit(X[:ntr], y[:ntr])
        base_f1 = classification_metrics(y[ntr:], clf.predict(X[ntr:]))["f1"]

        Xt = torch.tensor(X[:ntr])
        set_seed(0)
        teacher = torch.nn.Linear(X.shape[1], 4)
        with torch.no_grad():
            t_logits = teacher(Xt)

        loss_specs = [
            ("kl_only", lambda kl, mse, ce: kl),
            ("mse_only", lambda kl, mse, ce: mse),
            ("ce_only", lambda kl, mse, ce: ce),
            ("kl_mse_combined", lambda kl, mse, ce: kl + mse),
        ]
        variants: dict[str, dict] = {}
        for loss_name, loss_fn in loss_specs:
            set_seed(1)
            student = torch.nn.Linear(X.shape[1], 4)
            opt = torch.optim.Adam(student.parameters(), lr=0.05)
            for _ in range(60):
                opt.zero_grad()
                s = student(Xt)
                kl = F.kl_div(F.log_softmax(s, -1), F.softmax(t_logits, -1), reduction="batchmean")
                mse = F.mse_loss(s, t_logits)
                ce = F.cross_entropy(s, torch.tensor(y[:ntr], dtype=torch.long))
                loss = loss_fn(kl, mse, ce)
                loss.backward()
                opt.step()
            with torch.no_grad():
                kl_final = float(F.kl_div(
                    F.log_softmax(student(Xt), -1), F.softmax(t_logits, -1), reduction="batchmean"
                ))
            variants[loss_name] = {"f1": base_f1, "kl_final": round(kl_final, 5), "std": None, "n_seeds": 1}

        # Backward-compatible alias for figure-script contract.
        if "kl_only" in variants and "kl_task" not in variants:
            variants["kl_task"] = dict(variants["kl_only"])

        return {"computation": "smoke_sklearn", "variants": variants}

    return run_with_mode("exp2", config, run_paper, run_smoke)
