"""exp12: FraudFusion Baseline — Compare against FraudFusion multi-modal baseline."""
from __future__ import annotations
import logging
from experiments.framework import leakage_safe_split, load_first_nonempty, run_with_mode

logger = logging.getLogger("exp12")


def run(config: dict) -> dict:
    from realeval import data
    # Anchor to TAF-28k, the paper's main evaluation corpus.
    ds = load_first_nonempty(
        loaders=[lambda: data.load_taf28k(max_samples=config.get("data", {}).get("max_samples", 2000))],
        synthetic_loader=lambda: data.load_synthetic(n=100),
    )
    split = leakage_safe_split(ds, test_ratio=0.1, seed=42)

    def run_paper(config: dict) -> dict:
        from realeval import real_backend
        from experiments.common import resolve_qad_path

        qad_path = resolve_qad_path()
        finetuned_path = str(qad_path) if qad_path.exists() else None
        qad = real_backend.real_llm_classify(
            config, split.test_texts, split.test_labels, quantize="nvfp4",
            finetuned_path=finetuned_path,
        )
        # Storage footprints measured from actual model files on disk.
        import os as _os_12
        def _model_size_mb(model_path_key: str) -> float | None:
            """Measure actual model file size from disk. Returns None if not found."""
            path = config.get("models", {}).get(model_path_key, "")
            if not path:
                return None
            # Try to resolve via models_root
            from realeval.paths import models_root
            root = models_root()
            candidate = root / path
            total = 0
            if candidate.is_dir():
                for f in candidate.rglob("*.safetensors"):
                    total += f.stat().st_size if f.exists() else 0
                for f in candidate.rglob("*.bin"):
                    total += f.stat().st_size if f.exists() else 0
                for f in candidate.rglob("*.gguf"):
                    total += f.stat().st_size if f.exists() else 0
            if total > 0:
                return round(total / 1e6, 1)
            return None
        fp = {}
        for key, label in (("teacher_7b", "7B_BF16_SAFE_QAQ"),
                           ("student", "0.5B_BF16"),
                           ("student_gguf", "0.5B_Q4_K_M")):
            sz = _model_size_mb(key)
            if sz is not None:
                fp[label] = sz
        # Compute advantage factors from measured footprints (not hardcoded).
        bf16_7b = fp.get("7B_BF16_SAFE_QAQ")
        bf16_05 = fp.get("0.5B_BF16")
        q4_05 = fp.get("0.5B_Q4_K_M")
        quant_x = round(bf16_05 / q4_05, 1) if (bf16_05 and q4_05) else None
        param_x = round(bf16_7b / bf16_05, 1) if (bf16_7b and bf16_05) else None
        total_x = round(quant_x * param_x, 1) if (quant_x and param_x) else None
        return {"computation": "h100_real_qwen",
                "competitor_comparison_real": {
                    "QAD_MultiGuard_NVFP4": {"f1": qad["f1"], "source": "ours"},
                    # FraudFusion has no released weights; marked as cite-only (no F1 compared).
                    "FraudFusion_pruned_INT4": {"f1": None, "source": "cited (no released weights)"},
                },
                "storage_decomposition_point8": {
                    "footprints_mb": fp,
                    "quantization_alone_x": quant_x,
                    "param_scale_alone_x": param_x,
                    "total_advantage_x": total_x,
                }}


    return run_with_mode("exp12", config, run_paper)
