#!/usr/bin/env bash
# One-command H100 paper-validation entry.
#   bash run_h100.sh                 # paper-grade (real Qwen + H100), single process
#   bash run_h100.sh --all           # same, runs all experiment groups (default)
#   bash run_h100.sh --smoke         # sandbox verification (no GPU/weights)
#   bash run_h100.sh --distributed   # 8x H100 via torchrun --nproc_per_node=8 + NCCL
#
# Pipeline: CUDA check -> GPU detect -> env report -> model load -> benchmark -> metrics -> save
# Deliverables: outputs/{metrics/, tables/, results/}
set -euo pipefail
cd "$(dirname "$0")"

MODE="--paper"
DISTRIBUTED=0
for a in "$@"; do
  [ "$a" = "--smoke" ] && MODE="--smoke"
  [ "$a" = "--distributed" ] && DISTRIBUTED=1
done

# Python 解析：优先使用 /workspace/venv（RunPod 持久化环境，容器重启后系统 pip 包会丢失）
if [ -x /workspace/venv/bin/python ]; then
  PY=/workspace/venv/bin/python
else
  PY=python
fi

# 配置：默认 runpod_h100.yaml（单卡 RunPod）；可用 CONFIG=/path 覆盖（如 config/h100.yaml 多卡）
CONFIG="${CONFIG:-config/runpod_h100.yaml}"

# Auto-clean previous results before each fresh run
rm -rf outputs/results/* outputs/metrics/* outputs/predictions/* 2>/dev/null
echo "=== Cleaned previous outputs ==="

# H100 multi-GPU: expose all 8 cards for NCCL/DDP (harmless if fewer/none present).
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0,1,2,3,4,5,6,7}"
export HF_HUB_DISABLE_PROGRESS_BARS="${HF_HUB_DISABLE_PROGRESS_BARS:-1}"
export TRANSFORMERS_NO_ADVISORY_WARNINGS="${TRANSFORMERS_NO_ADVISORY_WARNINGS:-1}"
export TOKENIZERS_PARALLELISM="${TOKENIZERS_PARALLELISM:-false}"
export NCCL_DEBUG="${NCCL_DEBUG:-WARN}"

echo "=== H100 paper-validation pipeline ($MODE) — PY=$PY CONFIG=$CONFIG ==="
if [ "$DISTRIBUTED" = "1" ]; then
  NGPU="$("$PY" -c 'import torch;print(torch.cuda.device_count())' 2>/dev/null || echo 1)"
  echo "=== torchrun --nproc_per_node=$NGPU (NCCL) ==="
  torchrun --nproc_per_node="$NGPU" -m experiments.paper_pipeline "$MODE" --config "$CONFIG"
else
  "$PY" -m experiments.paper_pipeline "$MODE" --config "$CONFIG"
fi
echo "=== Deliverables in outputs/ ==="
ls -1 outputs/ 2>/dev/null || true

