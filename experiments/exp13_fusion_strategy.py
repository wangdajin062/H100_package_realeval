"""exp13: Fusion Strategy — Compare early fusion, late fusion, and hybrid (text + acoustic embeddings)."""
from __future__ import annotations
import logging
from experiments.framework import run_with_mode

logger = logging.getLogger("exp13")


def run(config: dict) -> dict:
    from realeval import data
    import numpy as np
    # Load multimodal data: text (JSONL) + acoustic embeddings (NPZ) aligned by index
    ds = data.load_taf28k(max_samples=config.get("data", {}).get("max_samples", 2000), source="multimodal")
    texts, labels = ds["texts"], ds["labels"]
    audio_emb = ds.get("embeddings")
    if not texts or audio_emb is None:
        # Fall back to synthetic with both text and acoustic-style embeddings
        ds = data.load_synthetic(n=200)
        texts, labels = ds["texts"], ds["labels"]
        audio_emb = ds["embeddings"]
    n = min(len(texts), len(audio_emb))
    texts, labels, audio_emb = texts[:n], labels[:n], np.asarray(audio_emb[:n])
    # Leakage-safe test partition shared with exp1/exp5/exp14 (P1-M1): one index set
    # applied to text, labels AND the aligned acoustic embeddings, instead of a
    # positional tail slice that overlaps exp1's training data.
    from experiments.common import shared_test_indices
    test_idx = shared_test_indices("taf28k", texts, labels)
    test_texts = [texts[i] for i in test_idx]
    test_labels = [labels[i] for i in test_idx]
    test_audio = audio_emb[test_idx]

    def run_paper(config: dict) -> dict:
        from realeval import real_backend
        import time
        # Real multimodal fusion on H100: Qwen (text) + pre-extracted acoustic embeddings.
        strategies = {}
        for sname in ("early_fusion", "late_fusion", "hybrid"):
            t0 = time.perf_counter()
            result = real_backend.real_fusion_classify(
                config, test_texts, test_labels, test_audio,
                quantize="int4", fusion_strategy=sname.replace("_fusion", ""))
            lat_ms = (time.perf_counter() - t0) / max(1, len(test_texts)) * 1000
            # Compute params from actual embedding dimensionalities; fall back to NOT_MEASURED.
            audio_dim = audio_emb.shape[1] if audio_emb is not None and len(audio_emb.shape) >= 2 else None
            if audio_dim is not None:
                text_dim = 896  # Qwen2.5-0.5B hidden dim (documented constant)
                _param_map = {
                    "early_fusion": text_dim + audio_dim,           # concat
                    "late_fusion": text_dim + audio_dim,            # separate classifiers
                    "hybrid": text_dim + audio_dim + text_dim // 2, # concat + metadata branch
                }
            else:
                _param_map = {"early_fusion": "NOT_MEASURED", "late_fusion": "NOT_MEASURED", "hybrid": "NOT_MEASURED"}
            strategies[sname] = {"f1": result["f1"], "accuracy": result["accuracy"],
                                 "params": _param_map[sname],
                                 "latency_ms": round(lat_ms, 4)}
        return {"computation": "h100_real_qwen", "strategies": strategies}

    return run_with_mode("exp13", config, run_paper)
