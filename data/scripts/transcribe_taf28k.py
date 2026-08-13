#!/usr/bin/env python3
"""transcribe_taf28k.py — 用 whisper 转录 TAF-28k 音频，重建可学习的 taf28k.jsonl。

修复数据引用逻辑：`load_taf28k()` 读取的 taf28k.jsonl 原先是音频指令模板（无类别信号），
本脚本把 sft 数据引用的真实音频转成文本，使文本分类管道能学到 fraud/normal 区分。

用法:
  python data/scripts/transcribe_taf28k.py --limit 100      # 试跑前 100 条
  python data/scripts/transcribe_taf28k.py                  # 全量转录
  python data/scripts/transcribe_taf28k.py --resume         # 断点续传

输出: data/TAF28k/taf28k.jsonl  (text=whisper 转录文本, label=fraud→1/normal→0)
"""
from __future__ import annotations
import argparse
import json
import time
from pathlib import Path

BASE = Path("/workspace/data/TAF28k")
AUDIO_ROOT = BASE / "audio"
SRC = ["sft/train_1.jsonl", "sft/train_2.jsonl", "sft/test.jsonl"]
LABEL_MAP = {"fraud": 1, "normal": 0}
OUT = BASE / "taf28k.jsonl"
WHISPER_MODEL = "/workspace/models/openai/whisper-tiny"


def gather_samples(limit: int) -> list[tuple[str, int]]:
    samples: list[tuple[str, int]] = []
    for fn in SRC:
        with open(BASE / fn, "rb") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    ans = str(obj.get("answers", "")).strip().lower()
                    if ans not in LABEL_MAP:
                        continue
                    auds = obj.get("audios") or []
                    if not auds:
                        continue
                    samples.append((str(auds[0]), LABEL_MAP[ans]))
                except Exception:
                    continue
    if limit:
        samples = samples[:limit]
    return samples


def main() -> None:
    ap = argparse.ArgumentParser(description="whisper 转录 TAF-28k 音频")
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 条（0=全部）")
    ap.add_argument("--resume", action="store_true", help="断点续传（追加，跳过已转录）")
    args = ap.parse_args()

    import torch
    import torchaudio
    from transformers import WhisperProcessor, WhisperForConditionalGeneration

    proc = WhisperProcessor.from_pretrained(WHISPER_MODEL)
    model = WhisperForConditionalGeneration.from_pretrained(WHISPER_MODEL)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device).eval()

    samples = gather_samples(args.limit)
    done: set[str] = set()
    if args.resume and OUT.exists():
        with open(OUT, encoding="utf-8") as f:
            for line in f:
                try:
                    done.add(json.loads(line)["audio"])
                except Exception:
                    pass

    print(f"[transcribe] {len(samples)} samples | resume-done={len(done)} | dev={device}")
    mode = "a" if args.resume else "w"
    n_ok, n_miss = 0, 0
    t0 = time.time()
    BATCH = 8
    resampler_48k = torchaudio.transforms.Resample(48000, 16000)  # 保持 CPU（wav 在 CPU）

    def _flush(batch_wavs, batch_labels, batch_audios, out):
        nonlocal n_ok, n_miss
        if not batch_wavs:
            return
        try:
            feats = proc(batch_wavs, sampling_rate=16000, return_tensors="pt", padding=True)
            feats = {k: v.to(device) for k, v in feats.items()}
            with torch.no_grad():
                gen = model.generate(**feats, language="zh", task="transcribe")
            texts = proc.batch_decode(gen, skip_special_tokens=True)
            for t, lab, ar in zip(texts, batch_labels, batch_audios):
                t = t.strip()
                if t:
                    out.write(json.dumps({"text": t, "label": lab, "audio": ar},
                                         ensure_ascii=False) + "\n")
                    n_ok += 1
                else:
                    n_miss += 1
        except Exception:
            n_miss += len(batch_wavs)

    with open(OUT, mode, encoding="utf-8") as out:
        bw, bl, ba = [], [], []
        for i, (audio_rel, label) in enumerate(samples):
            if audio_rel in done:
                continue
            apath = BASE / audio_rel
            if not apath.exists():
                n_miss += 1
                continue
            try:
                wav, sr = torchaudio.load(str(apath))
                if wav.shape[0] > 1:
                    wav = wav.mean(0, keepdim=True)
                wav16 = wav if sr == 16000 else resampler_48k(wav)
                bw.append(wav16[0].numpy())
                bl.append(label)
                ba.append(audio_rel)
            except Exception:
                n_miss += 1
                continue
            if len(bw) >= BATCH:
                _flush(bw, bl, ba, out)
                bw, bl, ba = [], [], []
            if (i + 1) % 200 == 0:
                print(f"  [{i+1}/{len(samples)}] ok={n_ok} miss={n_miss} "
                      f"elapsed={time.time()-t0:.0f}s")
                out.flush()
        _flush(bw, bl, ba, out)
        out.flush()

    print(f"[done] transcribed={n_ok} missing/failed={n_miss} -> {OUT}")


if __name__ == "__main__":
    main()
