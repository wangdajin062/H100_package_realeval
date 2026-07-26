"""exp10: Teacher Scale — Compare Qwen-7B vs Qwen-14B vs Qwen-72B teacher."""
from __future__ import annotations
import logging
from experiments.framework import leakage_safe_split, load_first_nonempty, run_with_mode

logger = logging.getLogger("exp10")


def run(config: dict) -> dict:
    from realeval import data
    ds = load_first_nonempty(
        loaders=[lambda: data.load_dataset(config.get("data", {}).get("dataset", "balanced4k"),
                                           max_samples=config.get("data", {}).get("max_samples", 2000))],
        synthetic_loader=lambda: data.load_synthetic(n=100),
    )
    split = leakage_safe_split(ds, test_ratio=0.2, seed=42)

    def run_paper(config):
        from realeval import real_backend
        scales = {}
        for teacher_key in ("teacher", "teacher_1.5b", "teacher_7b"):
            if teacher_key not in config.get("models", {}):
                continue
            cfg = dict(config)
            cfg["models"] = dict(config.get("models", {}))
            cfg["models"]["teacher"] = config["models"][teacher_key]
            result = real_backend.real_llm_classify(cfg, split.test_texts, split.test_labels, quantize="int4")
            scales[teacher_key] = {"f1": result["f1"], "accuracy": result["accuracy"]}
        return {"experiment": "exp10", "computation": "h100_real_qwen", "scales": scales}


    def run_smoke(_: dict) -> dict:
        logger.info("SMOKE: running small-model verification for exp10")
        from sklearn.ensemble import GradientBoostingClassifier
        from realeval.metrics import classification_metrics
        from realeval.data import verification_features

        synthetic_overlaps = (
            ("teacher", 0.95),
            ("teacher_1.5b", 0.88),
            ("teacher_7b", 0.82),
        )
        scales = {}
        for teacher, overlap in synthetic_overlaps:
            X, y = verification_features(split.train_labels + split.test_labels, overlap=overlap)
            ntr = len(split.train_labels)
            clf = GradientBoostingClassifier(n_estimators=100, random_state=42).fit(X[:ntr], y[:ntr])
            m = classification_metrics(y[ntr:], clf.predict(X[ntr:]))
            scales[teacher] = {"f1": m["f1"], "accuracy": m["accuracy"]}
        return {"experiment": "exp10", "computation": "smoke_sklearn", "scales": scales}

    return run_with_mode("exp10", config, run_paper, run_smoke)
