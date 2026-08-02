"""exp11: Quantization Scheme — Compare FP16, INT8, INT4, NF4."""
from __future__ import annotations
import logging
from experiments.framework import leakage_safe_split, load_first_nonempty, run_with_mode

logger = logging.getLogger("exp11")


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
        from realeval import models
        from pathlib import Path
        import torch
        schemes = {}

        # Prefer QAD-trained model from exp1, otherwise fall back to base Qwen
        qad_path = Path(__file__).resolve().parent.parent / "outputs" / "models" / "exp1_qad"

        # Test each quantisation scheme by loading with real bitsandbytes quantisation
        quant_schemes = [
            ("fp16", "fp16"),
            ("int8", "int8"),
            ("int4", "int4"),
            ("nf4", "nf4"),
        ]
        for scheme_name, quant_arg in quant_schemes:
            try:
                result = real_backend.real_llm_classify(
                    config, split.test_texts, split.test_labels,
                    quantize=quant_arg,
                    finetuned_path=str(qad_path) if qad_path.exists() else None,
                )
                schemes[scheme_name] = {"f1": result["f1"], "accuracy": result["accuracy"]}
            except Exception as e:
                logger.warning("Quantisation scheme %s failed: %s", scheme_name, e)
                schemes[scheme_name] = {"f1": None, "accuracy": None, "error": str(e)}

        return {
            "experiment": "exp11",
            "computation": "h100_real_qwen",
            "schemes": schemes,
            "model_source": "exp1_qad" if qad_path.exists() else "base_qwen",
        }

    def run_smoke(_: dict) -> dict:
        logger.info("SMOKE: running small-model verification for exp11")
        import numpy as np
        from sklearn.ensemble import GradientBoostingClassifier
        from realeval.metrics import classification_metrics

        y = np.asarray(ds.labels)
        rng = np.random.RandomState(42)
        d = 128
        centres = rng.randn(2, d) * 0.6
        X = np.stack([centres[int(t)] + rng.randn(d) * 0.9 for t in y]).astype(np.float32)
        ntr = len(split.train_labels)
        Xtr, Xte, ytr, yte = X[:ntr], X[ntr:], y[:ntr], y[ntr:]
        clf = GradientBoostingClassifier(n_estimators=100, random_state=42).fit(Xtr, ytr)

        def _quantize(arr: np.ndarray, bits: int) -> np.ndarray:
            if bits >= 16:
                return arr
            lo, hi = float(arr.min()), float(arr.max())
            if hi <= lo:
                return arr
            levels = (1 << bits) - 1
            q = np.round((arr - lo) / (hi - lo) * levels)
            return (q / levels) * (hi - lo) + lo

        quant_bitmap = {
            "fp16": {"bits": 16, "note": "full precision"},
            "int8": {"bits": 8, "note": "uniform 8-bit"},
            "int4": {"bits": 4, "note": "uniform 4-bit"},
            "nf4": {"bits": 4, "note": "APPROXIMATION -- NF4 is non-uniform; real hardware required"},
        }
        schemes = {}
        for quant, info in quant_bitmap.items():
            m = classification_metrics(yte, clf.predict(_quantize(Xte, int(info["bits"]))))
            schemes[quant] = {"f1": m["f1"], "accuracy": m["accuracy"], "quant_note": info["note"]}
        if "int4" not in schemes:
            schemes["int4"] = dict(schemes["fp16"])
        return {"experiment": "exp11", "computation": "smoke_sklearn", "schemes": schemes,
                "model_source": "smoke_sklearn"}

    return run_with_mode("exp11", config, run_paper, run_smoke)
