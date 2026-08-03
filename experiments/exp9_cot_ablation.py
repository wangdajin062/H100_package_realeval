"""exp9: CoT Ablation — Compare chain-of-thought vs direct classification."""
from __future__ import annotations
import logging
from experiments.framework import leakage_safe_split, load_first_nonempty, run_with_mode

logger = logging.getLogger("exp9")


def run(config: dict) -> dict:
    from realeval import data
    ds = load_first_nonempty(
        loaders=[lambda: data.load_dataset(config.get("data", {}).get("dataset", "taf28k"),
                                           max_samples=config.get("data", {}).get("max_samples", 1000))],
        synthetic_loader=lambda: data.load_synthetic(n=100),
    )
    split = leakage_safe_split(ds, test_ratio=0.2, seed=42)

    def run_paper(config):
        from realeval import real_backend
        from experiments.common import resolve_qad_path

        qad_path = resolve_qad_path()
        finetuned_path = str(qad_path) if qad_path.exists() else None

        # no-CoT: uses fine-tuned head (head(last_hidden).argmax(1)).
        # real_backend.real_llm_classify with finetuned_path returns at :644 via head path,
        # BEFORE reaching the token-probability scoring code at :700-718.
        direct = real_backend.real_llm_classify(
            config, split.test_texts, split.test_labels, quantize="int4", use_cot=False,
            finetuned_path=finetuned_path,
        )
        # CoT: generate+parse on base Qwen (no finetuned_path).
        # finetuned_path CANNOT be added here — it would trigger the head-only return
        # at :644, bypassing generate entirely. CoT inherently requires generate(+parse),
        # which is fundamentally unreliable for 0.5B models (F1≈0.035).
        # This branch is kept as a diagnostic reference only.
        cot = real_backend.real_llm_classify(
            config, split.test_texts, split.test_labels, quantize="int4", use_cot=True,
        )
        return {"computation": "h100_real_qwen",
                "with_cot": {"f1": cot["f1"], "fpr": cot.get("fpr"),
                             "note": "base Qwen generate+parse — unreliable for 0.5B; "
                                     "finetuned_path NOT applicable (would bypass generate)"},
                "without_cot": {"f1": direct["f1"], "fpr": direct.get("fpr"),
                                "note": "fine-tuned head path — head(last_hidden).argmax(1), "
                                        "matched to training paradigm"}}

    def run_smoke(_: dict) -> dict:
        logger.info("SMOKE: running small-model verification for exp9")
        from sklearn.ensemble import GradientBoostingClassifier
        from realeval.metrics import classification_metrics
        from realeval.data import verification_features
        import numpy as np

        X, y = verification_features(split.train_labels + split.test_labels)
        ntr = len(split.train_labels)
        clf_d = GradientBoostingClassifier(n_estimators=100, random_state=42).fit(X[:ntr], y[:ntr])
        m_direct = classification_metrics(y[ntr:], clf_d.predict(X[ntr:]))
        inter = np.hstack([X, (X[:, :8] * X[:, 8:16])])
        clf_c = GradientBoostingClassifier(n_estimators=100, random_state=42).fit(inter[:ntr], y[:ntr])
        m_cot = classification_metrics(y[ntr:], clf_c.predict(inter[ntr:]))
        return {
            "computation": "smoke_sklearn",
            "with_cot": {"f1": m_cot["f1"], "fpr": m_cot["fpr"]},
            "without_cot": {"f1": m_direct["f1"], "fpr": m_direct["fpr"]},
        }

    return run_with_mode("exp9", config, run_paper, run_smoke)
