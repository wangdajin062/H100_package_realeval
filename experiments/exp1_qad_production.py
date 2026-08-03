"""exp1: QAD Production Distillation — Real H100 training or small-model smoke verification."""
from __future__ import annotations
import logging

from experiments.framework import run_with_mode
from experiments.common import (
    load_and_split_dataset,
    multi_seed_std,
    n_seeds_from_config,
    set_seed,
)

logger = logging.getLogger("exp1")


def run(config: dict) -> dict:
    split = load_and_split_dataset(config, default_dataset="balanced4k")

    def run_paper(config: dict) -> dict:
        from realeval import real_backend

        quantize = config.get("training", {}).get("quantize", "int4")
        apply_ov = config.get("training", {}).get("apply_ov_rescaling", True)
        n_seeds = n_seeds_from_config(config, "exp1")

        f1s: list[float] = []
        result = None
        for s in range(n_seeds):
            set_seed(1000 + s)
            result = real_backend.real_qad_distill_train(
                config,
                split.train_texts, split.train_labels,
                split.test_texts, split.test_labels,
                quantize=quantize,
                apply_ov_rescaling=apply_ov,
                save_name="exp1_qad" if s == 0 else None,
            )
            f1s.append(result["f1"])

        return {
            "computation": "h100_real_qwen",
            "trajectory": result["trajectory"],
            "f1": result["f1"],
            "accuracy": result["accuracy"],
            "n_train": result["n_train"],
            "n_test": result["n_test"],
            "kl_final": result["kl_final"],
            "drift_pct_final": result["drift_pct_final"],
            "kl_plateau": result["kl_plateau"],
            "kl_converged": result["kl_converged"],
            "total_steps": result["total_steps"],
            "ovf_activation_step": result["ovf_activation_step"],
            "snr_min": result["snr_min"],
            "snr_max": result["snr_max"],
            "quantize": quantize,
            "is_synthetic": False,
            "std": multi_seed_std(f1s),
            "n_seeds": n_seeds,
        }

    def run_smoke(_: dict) -> dict:
        logger.info("SMOKE: running small-model verification for exp1")
        from sklearn.ensemble import GradientBoostingClassifier
        from realeval.metrics import classification_metrics
        from realeval.data import verification_features
        from experiments.smoke import toy_kl_distill

        X, y = verification_features(split.train_labels + split.test_labels)
        ntr = len(split.train_labels)
        clf = GradientBoostingClassifier(n_estimators=100, random_state=42).fit(X[:ntr], y[:ntr])
        f1 = classification_metrics(y[ntr:], clf.predict(X[ntr:]))["f1"]

        kl_result = toy_kl_distill(X, y, ntr)

        return {
            "computation": "smoke_sklearn",
            "path": "small_model_verification",
            "f1": f1,
            "accuracy": f1,
            "n_train": ntr,
            "n_test": len(y) - ntr,
            "is_synthetic": True,
            "std": None,
            **kl_result,
        }

    return run_with_mode("exp1", config, run_paper, run_smoke)
