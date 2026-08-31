#!/bin/bash
# download_taf28k_audio.sh — 下载并解压 TAF-28k 音频到 /workspace/data/TAF28k/audio/
#
# 数据集: TeleAntiFraud-28k (ACM MM '25)
#   论文:   https://arxiv.org/abs/2503.24115
#   官方仓库: https://github.com/JimmyMa99/TeleAntiFraud
#   HF (gated): https://huggingface.co/datasets/JimmyMa99/TeleAntiFraud
#
# 音频规模: ~13,711 个 mp3（48kHz / ~60s，共 ~12 GB），音频目录布局为
#   audio/POS-imitate-N/tts_testXXXX.mp3（与 sft/*.jsonl 的 audios 字段对齐）。
#
# 用法（二选一）:
#   1) 官方 gated 源（推荐，需 HF 登录 + 授权）:
#        pip install -U huggingface_hub
#        huggingface-cli login                          # 登录 HF 账号
#        huggingface-cli download JimmyMa99/TeleAntiFraud \
#            --repo-type dataset --local-dir /workspace/data/TAF28k/
#      （首次访问需在 HF 网页同意 "share your contact information" 授权）
#   2) 手动下载压缩包后传 URL（离线/镜像场景）:
#        bash download_taf28k_audio.sh <URL>
#
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "==> 无 URL 参数。TAF-28k 音频需从官方 gated 源下载（需授权），不支持匿名直链。" >&2
  echo "" >&2
  echo "官方获取方式:" >&2
  echo "  huggingface-cli login" >&2
  echo "  huggingface-cli download JimmyMa99/TeleAntiFraud \\" >&2
  echo "      --repo-type dataset --local-dir /workspace/data/TAF28k/" >&2
  echo "" >&2
  echo "或提供压缩包 URL 重跑: bash $0 <URL>" >&2
  exit 2
fi

URL="$1"
DEST=/workspace/data/TAF28k/audio
TMP=/tmp/taf28k_audio_dl
mkdir -p "$TMP"
echo "==> 下载 $URL"
case "$URL" in
  *.tar.gz|*.tgz) curl -sSL "$URL" -o "$TMP/audio.tar.gz" && tar -xzf "$TMP/audio.tar.gz" -C "$TMP" ;;
  *.zip)          curl -sSL "$URL" -o "$TMP/audio.zip" && (cd "$TMP" && unzip -q audio.zip) ;;
  *.tar)          curl -sSL "$URL" -o "$TMP/audio.tar" && tar -xf "$TMP/audio.tar" -C "$TMP" ;;
  *)              echo "未知格式（支持 .tar.gz/.zip/.tar），请提供压缩包 URL" >&2; exit 2 ;;
esac
echo "==> 移动音频到 $DEST"
mkdir -p "$DEST"
# 支持 audio/ 前缀或直接音频文件两种布局
if [ -d "$TMP/audio" ]; then
  cp -r "$TMP/audio/"* "$DEST/"
else
  cp -r "$TMP/"* "$DEST/" 2>/dev/null || true
fi
echo "==> 音频数量: $(find "$DEST" -name '*.mp3' | wc -l)"
echo "==> 示例目录: $(find "$DEST" -name '*.mp3' | head -2)"
echo DONE
