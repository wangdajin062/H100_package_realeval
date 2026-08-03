"""exp4: Baseline Comparison — Compare QAD against standard baselines (LogReg, XGBoost, MLP)."""
from __future__ import annotations
import logging

from experiments.framework import leakage_safe_split, load_first_nonempty, run_with_mode

logger = logging.getLogger("exp4")


def run(config: dict) -> dict:
    from realeval import data
    ds = load_first_nonempty(
        loaders=[lambda: data.load_chifraud_balanced()],
        synthetic_loader=lambda: data.load_synthetic(n=200),
    )
    split = leakage_safe_split(ds, test_ratio=0.2, seed=42)

    def run_paper(config):
        from realeval import real_backend
        from realeval.metrics import classification_metrics
        from sklearn.linear_model import LogisticRegression
        from sklearn.neural_network import MLPClassifier
        from sklearn.ensemble import GradientBoostingClassifier
        from sklearn.feature_extraction.text import HashingVectorizer
        baselines = {}
        vec = HashingVectorizer(n_features=512, alternate_sign=False, norm="l2")
        Xtr = vec.transform(split.train_texts); Xte = vec.transform(split.test_texts)
        algos = {"logreg": LogisticRegression(max_iter=1000),
                 "xgb": GradientBoostingClassifier(n_estimators=100, random_state=42),
                 "mlp": MLPClassifier(hidden_layer_sizes=(64,), max_iter=300, random_state=42)}
        for name, algo in algos.items():
            algo.fit(Xtr, split.train_labels)
            m = classification_metrics(split.test_labels, algo.predict(Xte))
            baselines[name] = {"f1": m["f1"], "accuracy": m["accuracy"]}
        q = real_backend.real_llm_classify(config, split.test_texts, split.test_labels, quantize="int4")
        baselines["qwen_base"] = {"f1": q["f1"], "accuracy": q["accuracy"]}
        return {"computation": "h100_real_qwen", "classifiers": baselines}

    def run_smoke(_: dict) -> dict:
        logger.info("SMOKE: running small-model verification for exp4")
        from sklearn.linear_model import LogisticRegression
        from sklearn.ensemble import GradientBoostingClassifier
        from sklearn.neural_network import MLPClassifier
        from realeval.metrics import classification_metrics
        from realeval.data import verification_features

        X, y = verification_features(split.train_labels + split.test_labels)
        ntr = len(split.train_labels)
        Xtr, Xte = X[:ntr], X[ntr:]
        baselines = {}
        for bl_name, clf in [
            ("logreg", LogisticRegression(max_iter=1000, random_state=42)),
            ("xgb", GradientBoostingClassifier(n_estimators=50, random_state=42)),
            ("mlp", MLPClassifier(hidden_layer_sizes=(64,), max_iter=500, random_state=42)),
            ("qwen_base", LogisticRegression(max_iter=1000, random_state=42)),
        ]:
            clf.fit(Xtr, split.train_labels)
            m = classification_metrics(split.test_labels, clf.predict(Xte))
            baselines[bl_name] = {"f1": m["f1"], "accuracy": m["accuracy"]}
        return {"computation": "smoke_sklearn", "classifiers": baselines}

    return run_with_mode("exp4", config, run_paper, run_smoke)
