#!/bin/bash
# launch.sh — H100 cluster 启动脚本（合并 launch_ddp / launch_h100 / launch_runpod_h100）
#
# 用法:
#   ./cluster/launch.sh ddp              # 多卡 DDP 训练启动
#   ./cluster/launch.sh h100             # 8×H100 集群全量运行
#   ./cluster/launch.sh runpod           # RunPod 单卡 H100 运行（含 pre-flight 检查）
#   NGPU=4 ./cluster/launch.sh ddp       # 自定义 GPU 数量

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
cd "$REPO_DIR"

MODE="${1:-}"
usage() {
    echo "Usage: $0 {ddp|h100|runpod}"
    echo "  ddp    — 多卡 DDP 训练启动（exp1）"
    echo "  h100   — 8×H100 集群全量实验运行"
    echo "  runpod — RunPod 单卡 H100（含 storage/hardware check）"
    exit 1
}

if [ -z "$MODE" ]; then usage; fi

case "$MODE" in
    ddp)
        NGPU="${NGPU:-8}"
        MASTER_PORT="${MASTER_PORT:-29500}"
        echo "========================================="
        echo " Launching DDP Training (${NGPU} GPUs)"
        echo "========================================="
        torchrun \
            --nproc_per_node="$NGPU" \
            --master_port="$MASTER_PORT" \
            -m experiments.runner --exp 1 --paper --resume
        ;;
    h100)
        NGPU="${NGPU:-8}"
        export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0,1,2,3,4,5,6,7}"
        export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}"
        export MKL_NUM_THREADS="${MKL_NUM_THREADS:-4}"
        export NUMEXPR_NUM_THREADS="${NUMEXPR_NUM_THREADS:-4}"
        export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-4}"
        export NCCL_DEBUG="${NCCL_DEBUG:-INFO}"
        export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"
        export TORCHINDUCTOR_FX_REMOVE_RANDOM_SEED="${TORCHINDUCTOR_FX_REMOVE_RANDOM_SEED:-1}"
        echo "========================================="
        echo " H100 Cluster Launch (${NGPU}×H100)"
        echo "========================================="
        echo " CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES"
        echo " OMP_NUM_THREADS=$OMP_NUM_THREADS"
        echo " PYTORCH_CUDA_ALLOC_CONF=$PYTORCH_CUDA_ALLOC_CONF"
        echo ""
        exec python -m experiments.runner --exp all --paper --resume --benchmark
        ;;
    runpod)
        export CUDA_VISIBLE_DEVICES=0
        export OMP_NUM_THREADS=8
        export MKL_NUM_THREADS=8
        export NUMEXPR_NUM_THREADS=8
        export OPENBLAS_NUM_THREADS=8
        export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
        export TORCHINDUCTOR_FX_REMOVE_RANDOM_SEED=1
        echo "========================================="
        echo " RunPod Single-Card H100 Launch"
        echo "========================================="
        echo " Step 1/3: Storage check..."
        python -m experiments.runner --storage-check || echo "  ⚠ Storage check incomplete, continuing..."
        echo " Step 2/3: Hardware check..."
        python -m experiments.runner --check || true
        echo " Step 3/3: Full paper-grade run..."
        exec python -m experiments.runner --exp all --paper --resume
        ;;
    *)
        echo "错误: 未知模式 '$MODE'"
        usage
        ;;
esac
