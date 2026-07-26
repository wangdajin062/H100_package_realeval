#!/bin/bash
# manage_models.sh — Download or stage experiment models (Qwen2.5 series + whisper-tiny)
# Usage:
#   ./cluster/manage_models.sh download     # Download to local HF cache
#   ./cluster/manage_models.sh stage        # Stage to shared storage server
#   STAGE_LARGE=1 ./cluster/manage_models.sh download   # Also fetch 1.5B/7B
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
cd "$REPO_DIR"

MODE="${1:-download}"
if [ "$MODE" != "download" ] && [ "$MODE" != "stage" ]; then
    echo "Usage: $0 {download|stage}" >&2
    exit 1
fi

MODELS_ROOT="${REALEVAL_MODELS_ROOT:-/workspace/models}"

# ── Mode-specific setup ──
if [ "$MODE" = "download" ]; then
    HF_CACHE="${HF_HOME:-/workspace/hf_cache}"
    mkdir -p "$MODELS_ROOT" "$HF_CACHE"
    ACTION_ING="Downloading"
    ACTION_ED="downloaded"
    ACTION_PAST="downloaded"
    CACHE_DIR="$HF_CACHE"
else
    mkdir -p "$MODELS_ROOT"
    ACTION_ING="Staging"
    ACTION_ED="staged"
    ACTION_PAST="staged"
    CACHE_DIR="$MODELS_ROOT/hf_cache"
fi

echo "========================================="
echo " Model Management ($MODE)"
echo " Models root: $MODELS_ROOT"
echo " Cache dir:   $CACHE_DIR"
echo "========================================="

manage_model() {
    local repo="$1"
    local target="$2"
    if [ -f "$target/config.json" ] && ls "$target"/*.safetensors 1>/dev/null 2>&1; then
        echo "  ✅ $repo already $ACTION_PAST, skipping"
        return 0
    fi
    echo "  $ACTION_ING $repo ..."
    HF_HOME="$CACHE_DIR" huggingface-cli download "$repo" --local-dir "$target"
    echo "  ✅ $repo $ACTION_ED"
}

manage_model "Qwen/Qwen2.5-0.5B-Instruct" "$MODELS_ROOT/Qwen/Qwen2.5-0.5B-Instruct"
manage_model "Qwen/Qwen2.5-0.5B"        "$MODELS_ROOT/Qwen/Qwen2.5-0.5B"
manage_model "openai/whisper-tiny"        "$MODELS_ROOT/openai/whisper-tiny"

if [ "${STAGE_LARGE:-0}" = "1" ]; then
    echo "  [STAGE_LARGE] $ACTION_ING 1.5B/7B for teacher-scale ablation..."
    manage_model "Qwen/Qwen2.5-1.5B-Instruct" "$MODELS_ROOT/Qwen/Qwen2.5-1.5B-Instruct"
    manage_model "Qwen/Qwen2.5-7B-Instruct"   "$MODELS_ROOT/Qwen/Qwen2.5-7B-Instruct"
fi

echo ""
echo "✅ All models $ACTION_PAST."
echo "   Models root: $MODELS_ROOT"
echo "   Cache dir:   $CACHE_DIR"
