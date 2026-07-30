#!/usr/bin/env bash
# Container-side one-shot: install deps -> download weights -> run paper pipeline.
# Executed detached on RunPod H100. All output goes to the log passed by the launcher.
set -uo pipefail
cd /workspace/H100_package_realeval

export REALEVAL_DATA_ROOT=/workspace/H100_package_realeval/data
export REALEVAL_MODELS_ROOT=/workspace/models
export HF_HOME=/workspace/hf_cache
export HF_HUB_ENABLE_HF_TRANSFER=1
export HF_HUB_DISABLE_PROGRESS_BARS=1

echo "=== [1/3] pip install deps ==="
python -m pip install --upgrade pip >/dev/null 2>&1 || true
python -m pip install -q -r requirements.txt || { echo "PIP_REQ_FAILED"; }
python -m pip install -q accelerate bitsandbytes huggingface_hub hf_transfer || { echo "PIP_EXTRA_FAILED"; }
echo "  installed. key pkgs:"
python -c "import importlib.util as u; [print('   ', m, bool(u.find_spec(m))) for m in ['transformers','datasets','accelerate','bitsandbytes','huggingface_hub']]"

echo "=== [2/3] download model weights ==="
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

echo "=== [3/3] run paper pipeline (--paper) ==="
bash run_h100.sh --paper

echo "=== ALL DONE ==="
