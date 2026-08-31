#!/bin/bash
# download_taf28k_audio.sh — 下载并解压 TAF-28k 音频到 /workspace/data/TAF28k/audio/
#
# 数据集: TeleAntiFraud-28k (ACM MM '25)
#   论文:       https://arxiv.org/abs/2503.24115
#   官方仓库:   https://github.com/JimmyMa99/TeleAntiFraud
#   官方 HF(gated): https://huggingface.co/datasets/JimmyMa99/TeleAntiFraud
#   公开镜像:   https://huggingface.co/buckets/wangdajin062/TeleAntiFraud-bucket
#
# 音频规模: audio.zip 约 12.7 GB（~13,711 个 mp3，48kHz / ~60s），解压布局
#   audio/POS-imitate-N/tts_testXXXX.mp3（与 sft/*.jsonl 的 audios 字段对齐）。
#
# 用法（三选一）:
#   1) 公开镜像 bucket（推荐，无需 HF 登录/授权）:
#        bash download_taf28k_audio.sh --bucket
#      - 国内/镜像场景走 hf-mirror.com（默认）。
#      - RunPod / 境外直连 huggingface.co 更快：MIRROR=0 bash download_taf28k_audio.sh --bucket
#   2) 官方 gated 源（备用，需 HF 登录 + 网页授权）:
#        pip install -U huggingface_hub
#        huggingface-cli login
#        huggingface-cli download JimmyMa99/TeleAntiFraud \
#            --repo-type dataset --local-dir /workspace/data/TAF28k/
#   3) 手动下载压缩包后传 URL（离线/自备镜像）:
#        bash download_taf28k_audio.sh <URL>
#
set -euo pipefail

BUCKET="wangdajin062/TeleAntiFraud-bucket"
ROOT=/workspace/data/TAF28k
DEST="$ROOT/audio"          # 最终音频目录（zip 内 audio/ 前缀解压至此）
TMP=/tmp/taf28k_audio_dl
MIRROR="${MIRROR:-1}"

if [ $# -lt 1 ]; then
  cat >&2 <<'EOF'
==> 无参数。TAF-28k 音频获取方式：

  [推荐·公开镜像] bash download_taf28k_audio.sh --bucket
      （wangdajin062/TeleAntiFraud-bucket 公开 bucket，audio.zip 12.7GB，无需授权）
      RunPod/境外直连：MIRROR=0 bash download_taf28k_audio.sh --bucket

  [官方 gated] huggingface-cli login 后：
      huggingface-cli download JimmyMa99/TeleAntiFraud \
          --repo-type dataset --local-dir /workspace/data/TAF28k/

  [自备压缩包] bash download_taf28k_audio.sh <URL>
EOF
  exit 2
fi

# 解压 zip 到 $ROOT，使内容落在 $DEST（若 zip 无 audio/ 前缀则手工归位）。
unpack_to_root() {
  local zip="$1"
  mkdir -p "$ROOT"
  if command -v unzip >/dev/null 2>&1; then
    unzip -q -o "$zip" -d "$ROOT"
  else
    python - "$zip" "$ROOT" <<'PY'
import sys, zipfile
zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])
PY
  fi
  # zip 内为 audio/ 前缀布局 → 已是 $DEST
  if [ -d "$DEST" ]; then
    return 0
  fi
  # 无前缀兜底：把 $ROOT 下散落的 mp3 归入 $DEST
  mkdir -p "$DEST"
  find "$ROOT" -maxdepth 1 -name '*.mp3' -exec mv -t "$DEST" {} + 2>/dev/null || true
}

report() {
  local n
  n=$(find "$DEST" -name '*.mp3' 2>/dev/null | wc -l)
  echo "==> 音频数量: $n"
  echo "==> 示例: $(find "$DEST" -name '*.mp3' 2>/dev/null | head -2)"
}

if [ "$1" = "--bucket" ]; then
  if [ "$MIRROR" = "1" ]; then
    BASE="https://hf-mirror.com"
  else
    BASE="https://huggingface.co"
  fi
  URL="$BASE/buckets/$BUCKET/resolve/audio.zip"
  echo "==> 下载公开 bucket audio.zip（12.7GB）: $URL"
  mkdir -p "$TMP"
  curl -fL -C - --retry 3 --retry-delay 5 -o "$TMP/audio.zip" "$URL"
  echo "==> 解压到 $ROOT（最终 $DEST）"
  unpack_to_root "$TMP/audio.zip"
  rm -f "$TMP/audio.zip"
  report
  echo DONE
  exit 0
fi

URL="$1"
mkdir -p "$TMP"
echo "==> 下载 $URL"
ZIP="$TMP/audio_manual.zip"
case "$URL" in
  *.tar.gz|*.tgz) curl -sSL "$URL" -o "$TMP/audio.tar.gz" && tar -xzf "$TMP/audio.tar.gz" -C "$TMP" ;;
  *.zip)          curl -sSL -C - --retry 3 "$URL" -o "$ZIP" && unpack_to_root "$ZIP" && rm -f "$ZIP" ;;
  *.tar)          curl -sSL "$URL" -o "$TMP/audio.tar" && tar -xf "$TMP/audio.tar" -C "$TMP" ;;
  *)              echo "未知格式（支持 .tar.gz/.zip/.tar），请提供压缩包 URL" >&2; exit 2 ;;
esac
# .tar* 分支仍走 /tmp 解压 → 归位
if [ -d "$TMP/audio" ]; then
  mkdir -p "$ROOT"
  cp -r "$TMP/audio" "$DEST" 2>/dev/null || true
fi
report
echo DONE
