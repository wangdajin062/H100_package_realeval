#!/usr/bin/env bash
# run_pipeline.sh — 容器侧一键流水线（合并 setup_and_run_paper / train_and_run_paper）
#
# 用法:
#   bash scripts/run_pipeline.sh           # 安装依赖 + 下载权重 + 运行论文流水线
#   bash scripts/run_pipeline.sh --train    # 同上，但先训练 LoRA adapter（chifraud），再跑实验
#
# 在 RunPod H100 上以 detached 方式执行，输出重定向到启动日志。

set -euo pipefail
cd /workspace/H100_package_realeval

# Data lives on the pod's persistent volume at /workspace/data (matches the Dockerfile
# ENV and the rest of the data chain). The repo's own data/ holds only scripts/, so
# pointing DATA_ROOT there left every loader empty.
export REALEVAL_DATA_ROOT=/workspace/data
export REALEVAL_MODELS_ROOT=/workspace/models
export REALEVAL_ADAPTER_ROOT=/workspace/outputs/lora_manual
export HF_HOME=/workspace/hf_cache
export HF_HUB_ENABLE_HF_TRANSFER=1
export HF_HUB_DISABLE_PROGRESS_BARS=1
export PYTHONPATH=/workspace/H100_package_realeval:${PYTHONPATH:-}
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
export TOKENIZERS_PARALLELISM=false

TRAIN_FIRST=0
for a in "$@"; do
    [ "$a" = "--train" ] && TRAIN_FIRST=1
done

# ── Step 1: Install dependencies ──
echo "=== [1] pip install deps ==="
python -m pip install --upgrade pip >/dev/null 2>&1 || true
python -m pip install -q -r requirements.txt || { echo "PIP_REQ_FAILED"; }
python -m pip install -q accelerate bitsandbytes huggingface_hub hf_transfer || { echo "PIP_EXTRA_FAILED"; }
if [ "$TRAIN_FIRST" = "1" ]; then
    python -m pip install -q peft >/dev/null 2>&1 || echo "PIP_WARN"
fi
echo "  installed. key pkgs:"
python -c "import importlib.util as u; [print('   ', m, bool(u.find_spec(m))) for m in ['transformers','datasets','accelerate','bitsandbytes','huggingface_hub']]"

# ── Step 2: Download model weights ──
echo "=== [2] download model weights ==="
mkdir -p "$REALEVAL_MODELS_ROOT" "$HF_HOME"
dl() {
    local repo="$1"; local target="$2"
    if [ -f "$target/config.json" ] && ls "$target"/*.safetensors >/dev/null 2>&1; then
        echo "  skip $repo (already present)"; return 0
    fi
    echo "  downloading $repo -> $target"
    huggingface-cli download "$repo" --local-dir "$target" >/dev/null 2>&1 \
        && echo "  ok $repo" || echo "  FAILED $repo"
}
dl "Qwen/Qwen2.5-0.5B-Instruct" "$REALEVAL_MODELS_ROOT/Qwen/Qwen2.5-0.5B-Instruct"
dl "Qwen/Qwen2-0.5B"            "$REALEVAL_MODELS_ROOT/Qwen/Qwen2-0.5B"
dl "Qwen/Qwen2.5-1.5B-Instruct" "$REALEVAL_MODELS_ROOT/Qwen/Qwen2.5-1.5B-Instruct"
dl "Qwen/Qwen2.5-3B-Instruct"   "$REALEVAL_MODELS_ROOT/Qwen/Qwen2.5-3B-Instruct"
dl "Qwen/Qwen2.5-7B-Instruct"   "$REALEVAL_MODELS_ROOT/Qwen/Qwen2.5-7B-Instruct"
dl "openai/whisper-tiny"        "$REALEVAL_MODELS_ROOT/openai/whisper-tiny"
echo "  models present:"
find "$REALEVAL_MODELS_ROOT" -maxdepth 2 -name config.json -printf '   %h\n' 2>/dev/null | sort -u

# ── Step 3 (optional): Train LoRA adapter ──
if [ "$TRAIN_FIRST" = "1" ]; then
    echo "=== [3] train LoRA adapter (corpus=chifraud, imbalanced + pos_weight) ==="
    ADAPTER=/workspace/outputs/lora_manual/best
    if [ -f "/workspace/outputs/lora_manual/history.json" ] && grep -q '"corpus": "chifraud"' "/workspace/outputs/lora_manual/history.json"; then
        echo "  chifraud adapter already exists at $ADAPTER — skipping training"
    else
        echo "  removing any stale adapter and retraining on chifraud"
        rm -rf /workspace/outputs/lora_manual
        mkdir -p /workspace/outputs/lora_manual
        python cluster/train_lora_manual.py \
            --corpus chifraud --epochs 3 --max-samples 16000 \
            --output-dir /workspace/outputs/lora_manual
    fi
    if [ -f "$ADAPTER/adapter_config.json" ]; then
        echo "  OK adapter at $ADAPTER"; ls -1 "$ADAPTER"
    else
        echo "  FATAL: adapter not produced — aborting paper run"; exit 3
    fi
fi

# ── Step 4: Run paper pipeline ──
STEP_NUM=$([ "$TRAIN_FIRST" = "1" ] && echo "4" || echo "3")
echo "=== [$STEP_NUM] run paper pipeline (--paper) ==="
bash run_h100.sh --paper

echo "=== ALL DONE ==="
