#!/usr/bin/env bash
# Container-side one-shot: ensure deps -> train LoRA adapter (local corpus) -> run paper pipeline.
# Produces /workspace/outputs/lora_manual/best which config students.qad_ovf points to,
# so exp1/2/3/4/5/8 can load the trained student instead of failing "no LoRA adapter found".
# Executed detached on RunPod H100. All output goes to the log passed by the launcher.
set -uo pipefail
cd /workspace/H100_package_realeval

export REALEVAL_DATA_ROOT=/workspace/H100_package_realeval/data
export REALEVAL_MODELS_ROOT=/workspace/models
export REALEVAL_ADAPTER_ROOT=/workspace/outputs/lora_manual
export HF_HOME=/workspace/hf_cache
export HF_HUB_DISABLE_PROGRESS_BARS=1
export TOKENIZERS_PARALLELISM=false
export PYTHONPATH=/workspace/H100_package_realeval:${PYTHONPATH:-}
export CUDA_VISIBLE_DEVICES=0

ADAPTER=/workspace/outputs/lora_manual/best

echo "=== [1/4] ensure deps (peft etc.) ==="
python -m pip install -q peft accelerate bitsandbytes >/dev/null 2>&1 || echo "PIP_WARN"
python -c "import importlib.util as u;[print('   ',m,bool(u.find_spec(m))) for m in ['transformers','peft','accelerate','bitsandbytes','datasets']]"

echo "=== [2/4] train LoRA adapter (corpus=chifraud, imbalanced + pos_weight) ==="
# Primary eval switched to ChiFraud (discriminative). Force a fresh retrain so a stale
# balanced4k adapter is replaced.
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

echo "=== [3/4] verify adapter ==="
if [ -f "$ADAPTER/adapter_config.json" ]; then
  echo "  OK adapter at $ADAPTER"; ls -1 "$ADAPTER"
else
  echo "  FATAL: adapter not produced — aborting paper run"; exit 3
fi

echo "=== [4/4] run paper pipeline (--paper) ==="
bash run_h100.sh --paper

echo "=== ALL DONE ==="
