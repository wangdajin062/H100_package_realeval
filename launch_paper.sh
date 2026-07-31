#!/bin/bash
# Launch the full paper-grade H100 pipeline in the background
cd /workspace/H100_package_realeval
export CUDA_VISIBLE_DEVICES=0
export OMP_NUM_THREADS=8
export MKL_NUM_THREADS=8
export NUMEXPR_NUM_THREADS=8
export OPENBLAS_NUM_THREADS=8
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export TORCHINDUCTOR_FX_REMOVE_RANDOM_SEED=1
export HF_HOME=/workspace/hf_cache
mkdir -p outputs/logs
LOG="outputs/logs/paper_run_$(date +%Y%m%d_%H%M%S).log"
setsid bash -c "python -m experiments.paper_pipeline --paper --config config/h100.yaml > '$LOG' 2>&1" < /dev/null &
echo "PAPER_PID=$!"
echo "LOG=$LOG"
