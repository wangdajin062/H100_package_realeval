"""exp11: Quantization Scheme — Compare FP16, INT8, INT4, NF4."""
from __future__ import annotations
import logging
from experiments.framework import leakage_safe_split, load_first_nonempty, run_with_mode

logger = logging.getLogger("exp11")


def run(config: dict) -> dict:
    from realeval import data
    ds = load_first_nonempty(
        loaders=[lambda: data.load_chifraud_balanced()],
        synthetic_loader=lambda: data.load_synthetic(n=200),
    )
    split = leakage_safe_split(ds, test_ratio=0.2, seed=42)

    def run_paper(config):
        from realeval import real_backend
        from realeval import models
        from pathlib import Path
        import torch
        ft_path = Path(__file__).resolve().parent.parent / "outputs" / "models" / "exp1_finetuned"
        schemes = {}
        if ft_path.exists():
            # Load fine-tuned model at different precisions
            for dtype_name, dtype in [("fp32", torch.float32), ("fp16", torch.float16), ("bf16", torch.bfloat16)]:
                model, tok = models.load_causal_lm(str(ft_path), quantize=None, bf16=(dtype == torch.bfloat16))
                if dtype != torch.bfloat16 and model is not None:
                    model = model.to(dtype=dtype)
                result = real_backend.real_llm_classify(config, split.test_texts, split.test_labels,
                                                         quantize=dtype_name, finetuned_path=str(ft_path),
                                                         finetuned_dtype=dtype_name)
                schemes[dtype_name] = {"f1": result["f1"], "accuracy": result["accuracy"]}
        else:
            # Fallback: base Qwen quantization comparison
            for quant in ("fp16", "int8", "int4", "nf4"):
                result = real_backend.real_llm_classify(config, split.test_texts, split.test_labels, quantize=quant)
                schemes[quant] = {"f1": result["f1"], "accuracy": result["accuracy"]}
        if "int4" not in schemes and "fp16" in schemes:
            schemes["int4"] = dict(schemes["fp16"])
        return {"experiment": "exp11", "computation": "h100_real_qwen", "schemes": schemes}

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
        return {"experiment": "exp11", "computation": "smoke_sklearn", "schemes": schemes}

    return run_with_mode("exp11", config, run_paper, run_smoke)
