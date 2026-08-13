"""exp7: Privacy Verification — Check for PII leakage in model outputs."""
from __future__ import annotations
import logging
from experiments.framework import load_first_nonempty, run_with_mode

logger = logging.getLogger("exp7")


def run(config: dict) -> dict:
    from realeval import data
    dataset = load_first_nonempty(
        loaders=[lambda: data.load_chifraud_balanced()],
        synthetic_loader=lambda: data.load_synthetic(n=100),
    )
    ds = {"texts": dataset.texts, "labels": dataset.labels}
    texts = dataset.texts

    def run_paper(config: dict) -> dict:
        from realeval import privacy, real_backend
        import numpy as np
        pii_report = privacy.scan_texts(texts)
        # Resolve F_v embeddings: prefer TAF-28k NPZ, fall back to ChiFraud NPZ.
        emb = ds.get("embeddings")
        spk_labels = ds.get("speaker_labels")
        embedding_source = "taf28k_fv"

        if emb is None or spk_labels is None:
            try:
                from realeval.data import _data_root
                cf = np.load(_data_root() / "ChiFraud" / "chifraud.npz")
                emb, spk_labels = cf["embeddings"], cf["speaker_labels"].tolist()
                embedding_source = "chifraud_npz_fallback"
                logger.info("Falling back to ChiFraud NPZ (%d samples)", len(emb))
            except (FileNotFoundError, KeyError) as e:
                logger.warning("ChiFraud NPZ fallback also failed: %s", e)

        real_backend.require_assets(
            emb is not None and spk_labels is not None and len(spk_labels) == len(emb),
            "Real F_v embeddings unavailable (need NPZ embeddings from real audio, not synthetic fallback)")
        emb = np.asarray(emb)
        asv = privacy.asv_eer_open_set(emb, spk_labels, n_enroll_utt=3, seed=42)
        sid = privacy.speaker_identification(emb, spk_labels, seed=42)
        glo = privacy.glo_reconstruction_attack(emb, emb[:, :64] if emb.shape[1] >= 64 else emb, steps=50, seed=42)
        # Measurement-coverage ledger: marks which paper privacy claims are backed by real
        # measurements here vs. which require a separate audio-reconstruction pipeline.
        # WER / PESQ / STOI / MOS need a full TTS+ASR rebuild (obfuscated audio → decode →
        # score); they are NOT produced by this experiment, so the paper table must either
        # run them separately or label them "not measured / planned".
        coverage = {
            "measured": ["pii_scan", "asv_eer", "speaker_id_acc", "glo_reconstruction_corr", "n_speakers"],
            "not_measured": {
                "wer_reconstruction": "requires obfuscate→decode→WER pipeline (TODO/planned)",
                "pesq_reconstruction": "requires audio reconstruction scoring (TODO/planned)",
                "stoi_reconstruction": "requires audio reconstruction scoring (TODO/planned)",
                "mos_reconstruction": "requires subjective/neural MOS scoring (TODO/planned)",
            },
        }
        return {"computation": "h100_real_qwen", "embedding_source": embedding_source,
                "pii_report": pii_report,
                "asv_eer_pct": asv["asv_eer_pct"], "min_dcf": asv.get("min_dcf"),
                "speaker_id_accuracy": sid["accuracy"], "glo_reconstruction_corr": glo["mean_reconstruction_corr"],
                "n_speakers": sid["n_speakers"],
                "coverage": coverage}


    return run_with_mode("exp7", config, run_paper)
