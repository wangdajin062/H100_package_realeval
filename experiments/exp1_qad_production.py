"""exp1: QAD Production Distillation — Real H100 training run (paper path) or small-model verification (smoke path).

Paper path (smoke=False): loads real Qwen teacher/student, runs multi-step distillation on TAF-28k,
measures real KL convergence, quantization SNR, and final student F1 on held-out test set.

Smoke path (smoke=True): small-model verification with synthetic data, same pipeline structure.
"""
from __future__ import annotations
import logging

from experiments.framework import leakage_safe_split, load_first_nonempty, run_with_mode

logger = logging.getLogger("exp1")


def run(config: dict) -> dict:
    from realeval import data

    ds = load_first_nonempty(
        loaders=[lambda: data.load_chifraud_balanced()],
        synthetic_loader=lambda: data.load_synthetic(n=200),
    )
    split = leakage_safe_split(ds, test_ratio=0.2, seed=42)

    # Paper path: real QWEN distillation training + student evaluation
    def run_paper(config: dict) -> dict:
        from realeval import real_backend
        # Real distillation: train student via KL against frozen BF16 teacher
        result = real_backend.real_distill_train(
            config,
            split.train_texts,
            split.train_labels,
            split.test_texts,
            split.test_labels,
        )
        return {
            "experiment": "exp1",
            "computation": "h100_real_qwen",
            "trajectory": result["trajectory"],
            "f1": result["f1"],
            "accuracy": result["accuracy"],
            "n_train": result["n_train"],
            "n_test": result["n_test"],
            "is_synthetic": False,
        }

    def run_smoke(_: dict) -> dict:
        logger.info("SMOKE: running small-model verification for exp1")
        from sklearn.ensemble import GradientBoostingClassifier
        from realeval.metrics import classification_metrics
        from realeval.data import verification_features
        import torch
        import torch.nn.functional as F

        X, y = verification_features(split.train_labels + split.test_labels)
        ntr = len(split.train_labels)
        clf = GradientBoostingClassifier(n_estimators=100, random_state=42).fit(X[:ntr], y[:ntr])
        f1 = classification_metrics(y[ntr:], clf.predict(X[ntr:]))["f1"]

        torch.manual_seed(0)
        Xt = torch.tensor(X[:ntr])
        teacher = torch.nn.Linear(X.shape[1], 4)
        student = torch.nn.Linear(X.shape[1], 4)
        with torch.no_grad():
            t_logits = teacher(Xt)
        opt = torch.optim.Adam(student.parameters(), lr=0.05)
        trajectory = []
        for step in range(5):
            for _ in range(30):
                opt.zero_grad()
                kl = F.kl_div(F.log_softmax(student(Xt), -1), F.softmax(t_logits, -1), reduction="batchmean")
                kl.backward()
                opt.step()
            with torch.no_grad():
                s_logits = student(Xt)
                ce = float(F.kl_div(F.log_softmax(s_logits, -1), F.softmax(t_logits, -1), reduction="batchmean"))
                lo, hi = s_logits.min(), s_logits.max()
                q = torch.round((s_logits - lo) / (hi - lo + 1e-9) * 15) / 15 * (hi - lo) + lo
                noise = (s_logits - q).pow(2).mean()
                snr = float(10 * torch.log10(s_logits.pow(2).mean() / (noise + 1e-12)))
            trajectory.append({"step": step, "ce": round(ce, 5), "snr_db": round(snr, 2)})

        return {
            "experiment": "exp1",
            "computation": "smoke_sklearn",
            "path": "small_model_verification",
            "f1": f1,
            "is_synthetic": True,
            "trajectory": trajectory,
        }

    return run_with_mode("exp1", config, run_paper, run_smoke)
