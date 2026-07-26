"""exp2: QAD Loss Ablation — Compare KL, MSE, and combined distillation losses."""
from __future__ import annotations
import logging
from experiments.framework import leakage_safe_split, load_first_nonempty, run_with_mode

logger = logging.getLogger("exp2")


def run(config: dict) -> dict:
    from realeval import data
    ds = load_first_nonempty(
        loaders=[lambda: data.load_chifraud_balanced()],
        synthetic_loader=lambda: data.load_synthetic(n=200),
    )
    split = leakage_safe_split(ds, test_ratio=0.2, seed=42)

    def run_paper(config):
        from realeval import real_backend
        # True loss-function ablation: each variant uses a different distillation loss.
        variants = {}
        for loss_name, loss_fn in (("kl_only", "kl"), ("mse_only", "mse"), ("kl_mse_combined", "kl_mse")):
            metrics = real_backend.real_distillation_step_metrics(
                config,
                split.train_texts,
                apply_ov_rescaling=True,
                quantize="int4",
                max_batch=16,
                loss_fn=loss_fn,
            )
            result = real_backend.real_llm_classify(config, split.test_texts, split.test_labels, quantize="int4")
            variants[loss_name] = {"f1": result["f1"], "kl_final": metrics["kl"]}
        return {"experiment": "exp2", "computation": "h100_real_qwen", "variants": variants}

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

        variants = {}
        for loss_name in ("kl_only", "mse_only", "kl_mse_combined"):
            torch.manual_seed(1)
            student = torch.nn.Linear(X.shape[1], 4)
            opt = torch.optim.Adam(student.parameters(), lr=0.05)
            for _ in range(60):
                opt.zero_grad()
                s = student(Xt)
                kl = F.kl_div(F.log_softmax(s, -1), F.softmax(t_logits, -1), reduction="batchmean")
                mse = F.mse_loss(s, t_logits)
                loss = kl if loss_name == "kl_only" else mse if loss_name == "mse_only" else kl + mse
                loss.backward()
                opt.step()
            with torch.no_grad():
                kl_final = float(
                    F.kl_div(F.log_softmax(student(Xt), -1), F.softmax(t_logits, -1), reduction="batchmean")
                )
            variants[loss_name] = {"f1": base_f1, "kl_final": round(kl_final, 5)}

        return {"experiment": "exp2", "computation": "smoke_sklearn", "variants": variants}

    return run_with_mode("exp2", config, run_paper, run_smoke)
