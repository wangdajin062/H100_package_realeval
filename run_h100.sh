#!/usr/bin/env bash
# One-command H100 paper-validation entry.
#   bash run_h100.sh                 # paper-grade (real Qwen + H100), single process
#                                    # (runs ALL experiment groups by default — no --all flag)
#   bash run_h100.sh --distributed   # 8x H100 via torchrun --nproc_per_node=8 + NCCL
#
# Pipeline: CUDA check -> GPU detect -> env report -> model load -> benchmark -> metrics -> save
# Deliverables: outputs/{metrics/, tables/, results/}
set -euo pipefail
cd "$(dirname "$0")"

MODE="--paper"
DISTRIBUTED=0
# Respect an inherited CLEAN=1 from the environment; default to 0 when unset.
# (A bare `CLEAN=0` here would clobber `CLEAN=1 bash run_h100.sh`.)
CLEAN="${CLEAN:-0}"
for a in "$@"; do
  [ "$a" = "--distributed" ] && DISTRIBUTED=1
  [ "$a" = "--clean" ] && CLEAN=1
done

# Python 解析：优先使用 /workspace/venv（RunPod 持久化环境，容器重启后系统 pip 包会丢失）
if [ -x /workspace/venv/bin/python ]; then
  PY=/workspace/venv/bin/python
else
  PY=python
fi

# 配置：单卡默认 runpod_h100.yaml；--distributed 多卡 DDP 默认 config/h100.yaml
# （num_gpu:8 / ddp:true / nccl:true）。均可用 CONFIG=/path 覆盖。
if [ "$DISTRIBUTED" = "1" ]; then
  CONFIG="${CONFIG:-config/h100.yaml}"
else
  CONFIG="${CONFIG:-config/runpod_h100.yaml}"
fi

# 持久卷路径兜底（与 scripts/run_pipeline.sh 对齐）。paths.py 在 RunPod 上会自动发现
# /workspace/*，此处显式兜底使 `bash run_h100.sh` 脱离 run_pipeline.sh 也能独立跑通。
# 注意 REALEVAL_ADAPTER_ROOT：训练脚本 cluster/train_lora_manual.py 写 /workspace/outputs/
# lora_manual，而 student_loader 默认找 sft_checkpoints——不显式设置会加载不到 adapter。
export REALEVAL_DATA_ROOT="${REALEVAL_DATA_ROOT:-/workspace/data}"
export REALEVAL_MODELS_ROOT="${REALEVAL_MODELS_ROOT:-/workspace/models}"
export REALEVAL_ADAPTER_ROOT="${REALEVAL_ADAPTER_ROOT:-/workspace/outputs/lora_manual}"
export HF_HOME="${HF_HOME:-/workspace/hf_cache}"

# 清理旧结果：默认不自动清空（避免单实验重跑误清全部结果）。
# 需清空时用 --clean 参数或 CLEAN=1 环境变量，或先 scripts/archive_and_clear.py 归档。
if [ "${CLEAN:-0}" = "1" ]; then
  rm -rf outputs/results/* outputs/metrics/* outputs/predictions/* 2>/dev/null
  echo "=== Cleaned previous outputs ==="
else
  echo "=== Skipping auto-clean（保留旧结果；用 --clean / CLEAN=1 / archive_and_clear.py 清理）==="
fi

# 单卡默认只暴露 card 0；--distributed 才暴露全部 8 卡给 NCCL/DDP。
if [ "$DISTRIBUTED" = "1" ]; then
  export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0,1,2,3,4,5,6,7}"
else
  export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
fi
export HF_HUB_DISABLE_PROGRESS_BARS="${HF_HUB_DISABLE_PROGRESS_BARS:-1}"
export TRANSFORMERS_NO_ADVISORY_WARNINGS="${TRANSFORMERS_NO_ADVISORY_WARNINGS:-1}"
export TOKENIZERS_PARALLELISM="${TOKENIZERS_PARALLELISM:-false}"
export NCCL_DEBUG="${NCCL_DEBUG:-WARN}"

echo "=== H100 paper-validation pipeline ($MODE) — PY=$PY CONFIG=$CONFIG ==="
if [ "$DISTRIBUTED" = "1" ]; then
  NGPU="$("$PY" -c 'import torch;print(torch.cuda.device_count())' 2>/dev/null || echo 1)"
  echo "=== torchrun --nproc_per_node=$NGPU (NCCL) ==="
  "$PY" -m torch.distributed.run --nproc_per_node="$NGPU" -m experiments.paper_pipeline "$MODE" --config "$CONFIG"
else
  "$PY" -m experiments.paper_pipeline "$MODE" --config "$CONFIG"
fi
echo "=== Deliverables in outputs/ ==="
ls -1 outputs/ 2>/dev/null || true

