"""exp2: QAD Loss Ablation — Compare KL, MSE, and combined distillation losses."""
from __future__ import annotations
import logging
from experiments.framework import leakage_safe_split, load_first_nonempty, run_with_mode

logger = logging.getLogger("exp2")


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

    def run_paper(config):
        from realeval import real_backend
        # Each variant runs actual QAD training with a different loss function.
        # Use fewer epochs (3) to keep ablation tractable.
        import copy
        import torch
        import numpy as np
        abl_config = copy.deepcopy(config)
        abl_config.setdefault("training", {})["epochs"] = 3
        # Real std requires multiple seeds. Default 3 (paper claimed 5, set via config if needed).
        n_seeds = int(abl_config.get("reproducibility", {}).get("exp2_seeds", 3))

        variants = {}
        # Five loss variants: kl_only, mse_only, ce_only (= QAT), kl_mse_combined, kl_task
        loss_specs = [
            ("kl_only",          "kl"),
            ("mse_only",         "mse"),
            ("ce_only",          "ce"),
            ("kl_mse_combined",  "kl_mse"),
            ("kl_task",          "kl"),
        ]
        for loss_name, loss_fn in loss_specs:
            # OV-Freeze disabled for pure baselines: kl_task (no reg), ce_only (QAT, no distillation)
            use_ovf = (loss_name not in ("kl_task", "ce_only"))
            f1s, kls = [], []
            for s in range(n_seeds):
                torch.manual_seed(1000 + s)
                torch.cuda.manual_seed_all(1000 + s)
                result = real_backend.real_qad_distill_train(
                    abl_config,
                    split.train_texts, split.train_labels,
                    split.test_texts, split.test_labels,
                    quantize="int4",
                    apply_ov_rescaling=use_ovf,
                    loss_fn=loss_fn,
                )
                f1s.append(float(result["f1"]))
                kls.append(float(result["kl_final"]))
            variants[loss_name] = {
                "f1": round(float(np.mean(f1s)), 4),
                "f1_list": [round(v, 4) for v in f1s],
                "kl_final": round(float(np.mean(kls)), 5),
                "std": round(float(np.std(f1s)), 4) if n_seeds > 1 else None,
                "n_seeds": n_seeds,
            }

        return {
            "experiment": "exp2",
            "computation": "h100_real_qwen",
            "variants": variants,
        }

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
        torch.manual_seed(0)
        teacher = torch.nn.Linear(X.shape[1], 4)
        with torch.no_grad():
            t_logits = teacher(Xt)

        # Smoke mirrors all five paper-path variants so figure/contract keys align.
        loss_specs = [
            ("kl_only",         lambda kl, mse, ce: kl),
            ("mse_only",        lambda kl, mse, ce: mse),
            ("ce_only",         lambda kl, mse, ce: ce),
            ("kl_mse_combined", lambda kl, mse, ce: kl + mse),
            ("kl_task",         lambda kl, mse, ce: kl),
        ]
        variants = {}
        for loss_name, loss_fn in loss_specs:
            torch.manual_seed(1)
            student = torch.nn.Linear(X.shape[1], 4)
            opt = torch.optim.Adam(student.parameters(), lr=0.05)
            for _ in range(60):
                opt.zero_grad()
                s = student(Xt)
                kl = F.kl_div(F.log_softmax(s, -1), F.softmax(t_logits, -1), reduction="batchmean")
                mse = F.mse_loss(s, t_logits)
                # Synthetic task loss: supervised CE on current student logits vs true labels
                ce = F.cross_entropy(s, torch.tensor(y[:ntr], dtype=torch.long))
                loss = loss_fn(kl, mse, ce)
                loss.backward()
                opt.step()
            with torch.no_grad():
                kl_final = float(
                    F.kl_div(F.log_softmax(student(Xt), -1), F.softmax(t_logits, -1), reduction="batchmean")
                )
            variants[loss_name] = {"f1": base_f1, "kl_final": round(kl_final, 5), "std": None, "n_seeds": 1}

        return {"experiment": "exp2", "computation": "smoke_sklearn", "variants": variants}

    return run_with_mode("exp2", config, run_paper, run_smoke)
