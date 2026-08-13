#!/bin/bash
# download_taf28k_audio.sh — 下载并解压 TAF-28k 音频到 /workspace/data/TAF28k/audio/
# 用法: bash download_taf28k_audio.sh <URL>
set -euo pipefail
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
