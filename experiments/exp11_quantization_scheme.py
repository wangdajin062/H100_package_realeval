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
        import numpy as np
        from experiments.common import (
            multi_seed_std, n_seeds_from_config, resolve_qad_path, set_seed,
        )

        qad_path = resolve_qad_path()
        n_seeds = n_seeds_from_config(config, "exp11")
        schemes = {}
        quant_schemes = [
            ("bf16", "bf16"),
            ("fp16", "fp16"),
            ("int8", "int8"),
            ("int4", "int4"),
            ("nf4", "nf4"),
        ]
        for scheme_name, quant_arg in quant_schemes:
            try:
                f1s, accs = [], []
                for s in range(n_seeds):
                    set_seed(1000 + s)
                    result = real_backend.real_llm_classify(
                        config, split.test_texts, split.test_labels,
                        quantize=quant_arg,
                        finetuned_path=str(qad_path) if qad_path.exists() else None,
                    )
                    f1s.append(result["f1"])
                    accs.append(result["accuracy"])
                schemes[scheme_name] = {
                    "f1": round(float(np.mean(f1s)), 4),
                    "std": multi_seed_std(f1s),
                    "accuracy": round(float(np.mean(accs)), 4),
                    "n_seeds": n_seeds,
                }
            except Exception as e:
                logger.warning("Quantisation scheme %s failed: %s", scheme_name, e)
                schemes[scheme_name] = {"f1": 0.0, "std": None, "error": str(e)}

        return {
            "computation": "h100_real_qwen",
            "schemes": schemes,
            "model_source": str(qad_path) if qad_path.exists() else "not_found",
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
            "bf16": {"bits": 16, "note": "native bf16 reference (no quantization)"},
            "fp16": {"bits": 16, "note": "fp16 — note: bf16-trained model may degrade in fp16"},
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
        return {"computation": "smoke_sklearn", "schemes": schemes,
                "model_source": "smoke_sklearn"}

    return run_with_mode("exp11", config, run_paper, run_smoke)
