#!/usr/bin/env python
"""build_chifraud_fv.py — build the REAL 128-d F_v for ChiFraud -> chifraud_fv.npz

R2 A-road: the existing ``build_audio_npz.py`` produces a *proxy* embedding
(20-d MFCC tiled to 128), not the paper's F_v = [64-d time-averaged FBANK ;
psi(W_proj . h_bar_w)]. This script builds the actual F_v from the ChiFraud audio
using ``realeval.acoustic_embedding`` so exp7 can run GLO / speaker-ID / ASV-EER
against the deployed embedding.

W_proj provenance (recorded in the NPZ):
  - ``--w-proj PATH`` loads a trained 64x384 matrix (.npy).
  - Otherwise a FIXED-SEED random projection is used (seed 7, N(0, 1/sqrt(384)) — the
    same distribution as fig2_acoustic_embedding.py's illustration, not the identical
    matrix). This is an *untrained*
    fallback — the non-invertibility of the Whisper-proj half here comes from the
    random projection, not a trained acoustic head. The privacy headline still
    rests on time-averaging (the FBANK half), which is orthogonal to W_proj.

Output: data/ChiFraud/chifraud_fv.npz with keys:
  - embeddings:      (n, 128) real F_v
  - labels:          fraud/normal from manifest dual_speaker
  - speaker_labels:  bucketed speaker IDs (SAME bucketing protocol as build_audio_npz.py,
                     so the only variable changed is proxy -> real F_v)
  - embedding_kind:  array(["fv"]) — provenance marker exp7 checks before trusting the GLO proj_fn

Usage:  python data/scripts/build_chifraud_fv.py [--w-proj /path/w_proj.npy]
"""
from __future__ import annotations
import argparse
import csv
import logging
from pathlib import Path

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger("build_chifraud_fv")

ROOT = Path(__file__).resolve().parent.parent.parent


def _fixed_seed_w_proj(seed: int = 7, shape: tuple[int, int] = (64, 384)) -> np.ndarray:
    """Fixed-seed random W_proj (fig2 convention: N(0, 1/sqrt(384))). Untrained fallback."""
    rng = np.random.RandomState(seed)
    return rng.normal(0, 1.0 / np.sqrt(shape[1]), size=shape).astype(np.float32)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--w-proj", default=None, help="path to a trained 64x384 W_proj .npy")
    ap.add_argument("--audio-dir", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    from realeval.acoustic_embedding import build_fv_from_wav, load_w_proj
    import whisper

    audio_dir = Path(args.audio_dir) if args.audio_dir else ROOT / "data" / "ChiFraud" / "audio"
    manifest_path = audio_dir / "manifest.csv"
    dst = Path(args.out) if args.out else ROOT / "data" / "ChiFraud" / "chifraud_fv.npz"

    if not audio_dir.is_dir() or not manifest_path.exists():
        logger.error("Audio directory or manifest not found: %s", audio_dir)
        return

    # Resolve W_proj with explicit provenance.
    if args.w_proj:
        w_proj = load_w_proj(args.w_proj)
        w_proj_source = f"trained:{args.w_proj}"
    else:
        w_proj = _fixed_seed_w_proj()
        w_proj_source = "fixed_seed_random_gaussian(seed=7, N(0,1/sqrt(384)), untrained fallback)"
    if w_proj is None:
        logger.error("W_proj unavailable — cannot build F_v (no fabrication).")
        return

    try:
        whisper_model = whisper.load_model("tiny")
    except Exception as e:  # pragma: no cover - optional stack
        logger.error("Whisper-tiny unavailable (%s) — cannot build F_v.", e)
        return

    rows = list(csv.DictReader(open(manifest_path, encoding="utf-8")))

    wav_files = []
    for row in rows:
        fname = row["filename"]
        tts_num = fname.replace("tts ", "").replace(".wav", "").strip()
        rank = str(row.get("rank", "")).strip().zfill(3)
        candidate = audio_dir / f"{rank}_{fname}"
        if candidate.exists():
            wav_files.append((candidate, row))
        else:
            for m in audio_dir.glob(f"*{tts_num}*"):
                wav_files.append((m, row))
                break

    if not wav_files:
        logger.error("No WAV files found")
        return

    import librosa
    embeddings, labels, skipped, zero_fill = [], [], 0, 0
    for wav, row in wav_files:
        try:
            y, sr = librosa.load(str(wav), sr=16000, mono=True)
            if y.size == 0:
                # Mirror build_audio_npz.py: empty audio -> zeros, so the sample set and
                # positional speaker bucketing stay identical to the proxy NPZ.
                embeddings.append(np.zeros(128, dtype=np.float32))
                zero_fill += 1
            else:
                fv = build_fv_from_wav(y, sr, w_proj=w_proj, whisper_model=whisper_model)
                if fv is None:
                    skipped += 1
                    continue
                embeddings.append(fv)
            dual = float(row.get("dual_speaker", 50))
            labels.append(1 if dual > 95 else 0)
        except Exception as e:  # pragma: no cover
            logger.warning("Failed %s: %s", wav.name, e)
            skipped += 1

    if not embeddings:
        logger.error("No audio processed (all skipped)")
        return

    embeddings = np.stack(embeddings).astype(np.float32)
    labels_arr = np.array(labels, dtype=np.int64)
    n = len(embeddings)

    # Honesty guard: the "only variable changed is proxy -> real F_v" claim only holds
    # when the real-F_v NPZ has the SAME samples (count) as the proxy chifraud.npz.
    # Empty audio is zero-filled above (matching build_audio_npz.py), but genuine
    # Whisper/W_proj failures are skipped — warn loudly if that breaks the alignment.
    if skipped:
        logger.warning(
            "%d sample(s) SKIPPED (Whisper/W_proj failure): real-F_v NPZ has %d samples, "
            "positional speaker bucketing is misaligned and exp7's proxy-vs-real-F_v "
            "comparison is confounded. Re-run with a working Whisper/librosa stack.", skipped, n)
    proxy_npz = ROOT / "data" / "ChiFraud" / "chifraud.npz"
    if proxy_npz.exists():
        proxy_n = len(np.load(proxy_npz)["embeddings"])
        if proxy_n != n:
            logger.warning(
                "Sample-count mismatch vs proxy NPZ: real F_v n=%d vs proxy n=%d "
                "(zero_fill=%d, skipped=%d). The bucketing guarantee does NOT hold.",
                n, proxy_n, zero_fill, skipped)

    # SAME speaker bucketing as build_audio_npz.py (~6/speaker), so the only
    # variable changed vs the proxy NPZ is the embedding itself.
    n_per = max(4, n // (n // 6)) if n >= 8 else n
    n_spk = max(1, (n + n_per - 1) // n_per)
    base, extra = n // n_spk, n % n_spk
    speaker_labels = []
    for s in range(n_spk):
        count = base + (1 if s < extra else 0)
        speaker_labels.extend([f"spk_{s + 1:03d}"] * count)

    dst.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        dst, embeddings=embeddings, labels=labels_arr,
        speaker_labels=np.array(speaker_labels),
        embedding_kind=np.array(["fv"]),
        w_proj_source=np.array([w_proj_source]),
    )
    logger.info("Saved %s: %d samples (skipped %d), %d speakers, fraud %.0f%%, F_v %s",
                dst, n, skipped, n_spk, 100 * labels_arr.mean(), embeddings.shape[1:])
    logger.info("W_proj provenance: %s", w_proj_source)


if __name__ == "__main__":
    main()
