"""exp7: Privacy Verification — Check for PII leakage in model outputs."""
from __future__ import annotations
import logging
from experiments.framework import load_first_nonempty, run_with_mode

logger = logging.getLogger("exp7")


def _load_reconstruction_assets(log):
    """Load reference + reconstructed waveform assets for the audio-reconstruction attack, if
    present, so the WER/PESQ/STOI/MOS harness can backfill real values. Expected optional file:
    ``<data_root>/privacy/reconstruction.npz`` with arrays ``ref_wavs``, ``recon_wavs`` (object
    arrays of 1-D float waveforms) and ``ref_texts`` (str array), plus optional scalar
    ``sample_rate``. Returns None when the assets are absent (the honest sandbox state)."""
    try:
        import numpy as np
        from realeval.data import _data_root
        path = _data_root() / "privacy" / "reconstruction.npz"
        if not path.exists():
            return None
        z = np.load(path, allow_pickle=True)
        return {"ref_wavs": list(z["ref_wavs"]), "recon_wavs": list(z["recon_wavs"]),
                "ref_texts": [str(t) for t in z["ref_texts"]],
                "sample_rate": int(z["sample_rate"]) if "sample_rate" in z else 16000}
    except Exception as e:  # pragma: no cover - optional asset path
        log.info("No audio-reconstruction assets (%s); WER/PESQ/STOI/MOS remain pending.", e)
        return None


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
        # Resolve F_v embeddings. R2 A-road: prefer the REAL F_v NPZ (built by
        # data/scripts/build_chifraud_fv.py, provenance marker ``embedding_kind=="fv"``),
        # then the TAF-28k real-F_v NPZ, then the legacy proxy chifraud.npz. Only the
        # real-F_v source is eligible for the non-demo GLO reconstruction below.
        emb = ds.get("embeddings")
        spk_labels = ds.get("speaker_labels")
        embedding_source = "taf28k_fv"
        fv_kind = None

        def _load_npz_candidate(path):
            from realeval.data import _data_root
            import numpy as _np
            z = _np.load(_data_root() / path)
            kind = None
            if "embedding_kind" in z:
                kind = str(z["embedding_kind"][0])
            return z["embeddings"], z["speaker_labels"].tolist(), kind

        if emb is None or spk_labels is None:
            for candidate, tag in (
                ("ChiFraud/chifraud_fv.npz", "chifraud_fv"),
                ("TAF28k/taf28k_fv.npz", "taf28k_fv"),
                ("ChiFraud/chifraud.npz", "chifraud_proxy"),
            ):
                try:
                    emb, spk_labels, fv_kind = _load_npz_candidate(candidate)
                    embedding_source = tag
                    logger.info("Loaded %s (%d samples, kind=%s)", candidate, len(emb), fv_kind)
                    break
                except (FileNotFoundError, KeyError, OSError) as e:
                    logger.info("Candidate %s unavailable: %s", candidate, e)

        real_backend.require_assets(
            emb is not None and spk_labels is not None and len(spk_labels) == len(emb),
            "Real F_v embeddings unavailable (need NPZ embeddings from real audio, not synthetic fallback)")
        emb = np.asarray(emb)
        asv = privacy.asv_eer_open_set(emb, spk_labels, n_enroll_utt=3, seed=42)
        sid = privacy.speaker_identification(emb, spk_labels, seed=42)

        # GLO reconstruction. R2 A-road: only the real F_v (embedding_kind=="fv") gets the
        # honest proj_fn — the FBANK half (F_v[:, :64]) is stored in the clear (identity),
        # the Whisper-proj half (F_v[:, 64:]) is a fixed per-sample constant, so the attack
        # reconstructs the FBANK half exactly (corr -> ~1.0 by construction). The proxy NPZ
        # keeps the random-orthogonal sandbox (demo) flag.
        if emb.shape[1] >= 128 and fv_kind == "fv":
            from realeval.acoustic_embedding import fbank_identity_proj_fn
            glo = privacy.glo_reconstruction_attack(
                emb, emb[:, :64], steps=50, seed=42,
                proj_fn=fbank_identity_proj_fn(emb))
        else:
            glo = privacy.glo_reconstruction_attack(
                emb, emb[:, :64] if emb.shape[1] >= 64 else emb, steps=50, seed=42)
        # Measurement-coverage ledger: marks which paper privacy claims are backed by real
        # measurements here vs. which require the audio-reconstruction scoring harness.
        # WER / PESQ / STOI / MOS are scored by realeval.privacy.reconstruction_quality_metrics
        # from reference + reconstructed waveforms; when those assets (and the audio stack:
        # jiwer/Whisper, pesq, pystoi, SQUIM/NISQA) are present the harness backfills real
        # values, otherwise it records exactly which metric is still pending — it never fabricates.
        # GLO reconstruction: with no real embedding function passed as proj_fn, the attack
        # runs against a RANDOM orthogonal projection — a sandbox DEMO number, not a real
        # reconstruction measurement (P1-M4). Report it honestly: keep the source note and a
        # demo flag, and don't list it among the real measurements when it is demo-only.
        glo_is_demo = str(glo.get("note", "")).startswith("Sandbox")
        measured_fields = ["pii_scan", "asv_eer", "speaker_id_acc", "n_speakers"]
        if not glo_is_demo:
            measured_fields.append("glo_reconstruction_corr")

        # Audio-reconstruction scoring: run the real harness if aligned waveform assets exist.
        recon = _load_reconstruction_assets(logger)
        if recon is not None:
            rq = privacy.reconstruction_quality_metrics(
                recon["ref_wavs"], recon["recon_wavs"], recon["ref_texts"],
                sample_rate=recon.get("sample_rate", 16000))
            measured_fields += [k for k in rq["measured"]]
            recon_measured = rq["measured"]
            recon_pending = rq["not_measured"]
        else:
            recon_measured = {}
            recon_pending = {
                "wer_reconstruction": "requires reference+reconstructed waveform assets (harness ready: reconstruction_quality_metrics)",
                "pesq_reconstruction": "requires reference+reconstructed waveform assets (harness ready)",
                "stoi_reconstruction": "requires reference+reconstructed waveform assets (harness ready)",
                "mos_reconstruction": "requires reference+reconstructed waveform assets + SQUIM/NISQA (harness ready)",
            }
        coverage = {"measured": measured_fields, "not_measured": recon_pending}
        if glo_is_demo:
            coverage["demo_only"] = {"glo_reconstruction_corr": glo.get("note")}
        result = {"computation": "h100_real_qwen", "embedding_source": embedding_source,
                  "embedding_kind": fv_kind,
                  "pii_report": pii_report,
                  "asv_eer_pct": asv["asv_eer_pct"], "min_dcf": asv.get("min_dcf"),
                  "speaker_id_accuracy": sid["accuracy"],
                  "glo_reconstruction_corr": glo["mean_reconstruction_corr"],
                  "glo_reconstruction_note": glo.get("note"),
                  "glo_reconstruction_is_demo": glo_is_demo,
                  "n_speakers": sid["n_speakers"],
                  "coverage": coverage}
        result.update(recon_measured)
        return result


    return run_with_mode("exp7", config, run_paper, required_datasets=["balanced4k"])
