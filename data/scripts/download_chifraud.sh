#!/bin/bash
# download_chifraud.sh — 从官方 GitHub 下载 ChiFraud CSV 并校验 sha256。
#
# 官方数据集: ChiFraud: A Long-Term Web Text Benchmark for Chinese Fraud Detection
#   (COLING 2025) — https://aclanthology.org/2025.coling-main.398/
# 仓库:        https://github.com/xuemingxxx/ChiFraud/tree/main/dataset
# 许可:        CC BY-NC 4.0（非商业）
#
# 下载后运行:  python data/scripts/prep_datasets.py   # 生成 data/ChiFraud/chifraud.jsonl
#
# 用法: bash data/scripts/download_chifraud.sh
set -euo pipefail

BASE_URL="https://raw.githubusercontent.com/xuemingxxx/ChiFraud/main/dataset"
DEST="data/ChiFraud/dataset"
mkdir -p "$DEST"

# sha256 校验和为本地实测值（对 data/ChiFraud/dataset/ 三个 CSV 逐一 sha256sum 所得）。
# 注意：dataset/metadata.json 的 sha256 字段与文件名存在循环错位（元数据过期，实测
#   train=fc7cacab… / t2022=25469871… / t2023=9775352b…），勿直接引用 metadata.json。
check() {
  local f="$1" expected="$2"
  local got
  got=$(sha256sum "$f" | awk '{print $1}')
  if [ "$got" != "$expected" ]; then
    echo "✗ 校验失败: $f" >&2
    echo "  期望 $expected" >&2
    echo "  实际 $got" >&2
    return 1
  fi
  echo "✓ 校验通过: $f"
}

dl() {
  local f="$1" sha="$2"
  local out="$DEST/$f"
  if [ -s "$out" ]; then
    echo "→ 已存在且非空，跳过下载: $out"
  else
    echo "→ 下载 $BASE_URL/$f"
    curl -fL --retry 3 "$BASE_URL/$f" -o "$out"
  fi
  check "$out" "$sha"
}

dl "ChiFraud_train.csv" "fc7cacabce4891bd0904ae75feae83e58248a437a1c320cdc2286392e430d8f0"
dl "ChiFraud_t2022.csv" "25469871dc93c7e06d2b312dffdfd59ef7287468aa232dd629971ca0509affd7"
dl "ChiFraud_t2023.csv" "9775352b407d19080c963b54741404a477f9c44ea7bab42f1850bd84b703ba27"

echo ""
echo "✓ ChiFraud CSV 就绪。生成 JSONL:"
echo "  python data/scripts/prep_datasets.py"
