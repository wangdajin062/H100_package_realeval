#!/usr/bin/env python3
"""build_taf28k_npz.py — 用 whisper 编码器提取 taf28k 音频特征，生成 taf28k.npz。

使 exp13 融合实验的声学部分使用真实 whisper 特征（而非 synthetic）。
对齐顺序：读取已转录的 taf28k.jsonl（text/label/audio），按同序生成嵌入。

用法:
  python data/scripts/build_taf28k_npz.py --limit 100   # 试跑前 100 条
  python data/scripts/build_taf28k_npz.py               # 全量

输出: /workspace/data/TAF28k/taf28k.npz
  embeddings:      (n, 384) whisper 编码器 last_hidden_state 时间均值池化
  labels:         (n,)     fraud=1 / normal=0
  speaker_labels: (n,)     按 NEG/POS-imitate-N 分组
"""
from __future__ import annotations
import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
import torchaudio
from transformers import WhisperProcessor, WhisperForConditionalGeneration

BASE = Path("/workspace/data/TAF28k")
OUT = BASE / "taf28k.npz"
MODEL = "/workspace/models/openai/whisper-tiny"
BATCH = 8


def main() -> None:
    ap = argparse.ArgumentParser(description="whisper 特征生成 taf28k.npz")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(BASE / "taf28k.jsonl", encoding="utf-8")
            if l.strip()]
    if args.limit:
        rows = rows[: args.limit]
    print(f"[npz] {len(rows)} samples")

    proc = WhisperProcessor.from_pretrained(MODEL)
    model = WhisperForConditionalGeneration.from_pretrained(MODEL).to("cuda").eval()
    resampler = torchaudio.transforms.Resample(48000, 16000)

    embs, labels, spk = [], [], []
    batch_wavs, batch_idx = [], []

    def flush() -> None:
        if not batch_wavs:
            return
        feats = proc(batch_wavs, sampling_rate=16000, return_tensors="pt", padding=True)
        feats = {k: v.to("cuda") for k, v in feats.items()}
        with torch.no_grad():
            enc = model.model.encoder(**feats).last_hidden_state  # (B, T, 384)
        pooled = enc.mean(dim=1).cpu().numpy()  # (B, 384)
        for k, i in enumerate(batch_idx):
            embs.append(pooled[k])
            labels.append(rows[i]["label"])
            spk.append(f"spk_{rows[i]['audio'].split('/')[1]}")
        batch_wavs.clear()
        batch_idx.clear()

    t0 = time.time()
    for i, r in enumerate(rows):
        apath = BASE / r["audio"]
        if not apath.exists():
            continue
        wav, sr = torchaudio.load(str(apath))
        if wav.shape[0] > 1:
            wav = wav.mean(0, keepdim=True)
        wav16 = wav if sr == 16000 else resampler(wav)
        batch_wavs.append(wav16[0].numpy())
        batch_idx.append(i)
        if len(batch_wavs) >= BATCH:
            flush()
        if (i + 1) % 500 == 0:
            print(f"  [{i+1}/{len(rows)}] elapsed={time.time()-t0:.0f}s")
    flush()

    E = np.stack(embs)
    L = np.array(labels)
    S = np.array(spk)
    np.savez(OUT, embeddings=E, labels=L, speaker_labels=S)
    print(f"[npz] saved {OUT}: embeddings={E.shape} labels={L.shape} spk={S.shape}")


if __name__ == "__main__":
    main()
