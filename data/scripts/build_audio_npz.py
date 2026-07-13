#!/usr/bin/env python
"""build_audio_npz.py — Extract MFCC embeddings from ChiFraud audio -> chifraud.npz

Usage:  python data/scripts/build_audio_npz.py

Output: data/ChiFraud/chifraud.npz with keys:
  - embeddings:      MFCC-based audio embeddings (n_samples, 128)
  - labels:          fraud/normal labels from manifest dual_speaker
  - speaker_labels:  speaker IDs (bucketed for ASV)
"""
from __future__ import annotations
import csv
import logging
import numpy as np
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger("build_audio_npz")

ROOT = Path(__file__).resolve().parent.parent.parent


def extract_mfcc(wav_path: Path, n_mfcc: int = 20) -> np.ndarray:
    import librosa
    y, sr = librosa.load(str(wav_path), sr=16000, mono=True)
    if len(y) == 0:
        return np.zeros(n_mfcc)
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=n_mfcc)
    return mfcc.mean(axis=1)


def make_embedding(mfcc: np.ndarray, target_dim: int = 128) -> np.ndarray:
    if len(mfcc) >= target_dim:
        return mfcc[:target_dim]
    repeats = target_dim // len(mfcc) + 1
    return np.tile(mfcc, repeats)[:target_dim]


def main():
    audio_dir = ROOT / "data" / "ChiFraud" / "audio"
    manifest_path = audio_dir / "manifest.csv"
    dst = ROOT / "data" / "ChiFraud" / "chifraud.npz"

    if not audio_dir.is_dir() or not manifest_path.exists():
        logger.error("Audio directory or manifest not found")
        return

    rows = list(csv.DictReader(open(manifest_path, encoding="utf-8")))

    # Match manifest to WAV files (actual: "001_tts 9626.wav", manifest: "tts 9626.wav")
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

    logger.info("Processing %d WAV files ...", len(wav_files))

    embeddings, labels = [], []
    for wav, row in wav_files:
        try:
            mfcc = extract_mfcc(wav)
            embeddings.append(make_embedding(mfcc, target_dim=128))
            dual = float(row.get("dual_speaker", 50))
            labels.append(1 if dual > 95 else 0)
        except Exception as e:
            logger.warning("Failed %s: %s", wav.name, e)

    if not embeddings:
        logger.error("No audio processed")
        return

    embeddings = np.stack(embeddings).astype(np.float32)
    labels_arr = np.array(labels, dtype=np.int64)
    n = len(embeddings)

    # Bucket into speaker groups of ~6 each (ASV needs >=4 utterances/speaker)
    n_per = max(4, n // (n // 6)) if n >= 8 else n
    n_spk = max(1, (n + n_per - 1) // n_per)
    # Rebalance: spread evenly so no speaker has < 4
    base = n // n_spk
    extra = n % n_spk
    speaker_labels = []
    idx = 0
    for s in range(n_spk):
        count = base + (1 if s < extra else 0)
        for _ in range(count):
            speaker_labels.append(f"spk_{s + 1:03d}")

    dst.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(dst, embeddings=embeddings, labels=labels_arr,
                        speaker_labels=speaker_labels)
    logger.info("Saved %s: %d samples, %d speakers (%d-%d/spk), fraud %.0f%%",
                dst, n, n_spk, min(np.unique(speaker_labels, return_counts=True)[1]),
                max(np.unique(speaker_labels, return_counts=True)[1]),
                100 * labels_arr.mean())


if __name__ == "__main__":
    main()
