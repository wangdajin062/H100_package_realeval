#!/bin/bash
# run_all.sh — H100 RealEval One-Click Pipeline
# ===========================================================================
# Persistent Storage: /workspace (network volume)
# Ports: SSH:22 | Jupyter:8888 | VSCode:3000 | Ollama:11434 | API:8000
#
# Usage:
#   bash run_all.sh                  # Full pipeline: setup → SFT → paper run
#   bash run_all.sh --setup-only     # Environment bootstrap only
#   bash run_all.sh --sft-only       # SFT training only
#   bash run_all.sh --paper-only     # Paper-grade experiments only
#   bash run_all.sh --smoke          # Quick smoke verification
# ===========================================================================
set -euo pipefail
cd "$(dirname "$0")"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_DIR="/workspace/outputs/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/run_all_$TIMESTAMP.log"

# ── Colors ──
RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
log()  { echo -e "${CYAN}[$(date +%H:%M:%S)]${NC} $*" | tee -a "$LOG"; }
ok()   { echo -e "${GREEN}[$(date +%H:%M:%S)] ✅${NC} $*" | tee -a "$LOG"; }
err()  { echo -e "${RED}[$(date +%H:%M:%S)] ❌${NC} $*" | tee -a "$LOG"; }

# ── Flags ──
MODE="full"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --setup-only) MODE="setup"; shift ;;
        --sft-only)   MODE="sft"; shift ;;
        --paper-only) MODE="paper"; shift ;;
        --smoke)      MODE="smoke"; shift ;;
        *) echo "Unknown: $1"; exit 2 ;;
    esac
done

# ═══════════════════════════════════════════════════════════════════════════
# Phase 0: Environment Detection
# ═══════════════════════════════════════════════════════════════════════════
log "=== H100 RealEval Pipeline ($MODE) ==="
log "Workspace: /workspace"

# Check persistent volume
if mount | grep -q "/workspace"; then
    ok "Persistent volume mounted at /workspace"
else
    log "No persistent volume detected — using local storage"
fi

# GPU check
if command -v nvidia-smi &>/dev/null; then
    GPU=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo "Unknown")
    VRAM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader 2>/dev/null || echo "Unknown")
    ok "GPU: $GPU | VRAM: $VRAM"
else
    err "No GPU detected! H100 required for paper-grade runs."
    exit 1
fi

# ═══════════════════════════════════════════════════════════════════════════
# Phase 1: Environment Setup
# ═══════════════════════════════════════════════════════════════════════════
setup_env() {
    log "=== Phase 1: Environment Setup ==="

    PYTHON="${PYTHON:-python3}"
    VENV="/workspace/venv"

    # Create venv if needed (persists across restarts on network volume)
    if [ ! -f "$VENV/bin/python" ]; then
        log "Creating virtual environment..."
        $PYTHON -m venv "$VENV"
    else
        ok "Virtual environment found: $VENV"
    fi

    PY="$VENV/bin/python"
    PIP="$VENV/bin/pip"

    # Install dependencies (skip torch if installed)
    if $PY -c "import torch" 2>/dev/null; then
        ok "PyTorch already installed: $($PY -c 'import torch; print(torch.__version__)')"
    else
        log "Installing dependencies (5-10 min)..."
        $PIP install --upgrade pip -q
        $PIP install -e "$SCRIPT_DIR" peft datasets accelerate bitsandbytes -q
        ok "Dependencies installed"
    fi

    # HF authentication
    if [ -n "${HF_TOKEN:-}" ]; then
        $PY -c "from huggingface_hub import HfApi; HfApi().whoami()" 2>/dev/null && \
            ok "HF authenticated" || \
            $VENV/bin/hf auth login --token "$HF_TOKEN" 2>/dev/null && ok "HF authenticated"
    else
        log "HF_TOKEN not set — HF features may be limited"
    fi

    # Model cache: use /workspace/models (network volume)
    mkdir -p /workspace/models /workspace/hf_cache
    export HF_HOME="/workspace/hf_cache"
    export REALEVAL_MODELS_ROOT="/workspace/models"

    # Download base models if not cached
    log "Checking model cache..."
    $PY -c "
from huggingface_hub import snapshot_download
import os
models = [
    ('Qwen/Qwen2.5-0.5B-Instruct', '/workspace/models/Qwen/Qwen2.5-0.5B-Instruct'),
    ('Qwen/Qwen2.5-0.5B', '/workspace/models/Qwen/Qwen2.5-0.5B'),
]
for repo, target in models:
    if os.path.exists(f'{target}/config.json'):
        print(f'  ✅ {repo} (cached)')
    else:
        print(f'  ⬇ {repo} ...')
        snapshot_download(repo, local_dir=target, max_workers=4)
        print(f'  ✅ {repo} (downloaded)')
print('Models ready.')
" 2>&1 | while read line; do log "$line"; done

    ok "Phase 1 complete"
}

# ═══════════════════════════════════════════════════════════════════════════
# Phase 2: SFT Training
# ═══════════════════════════════════════════════════════════════════════════
run_sft() {
    log "=== Phase 2: SFT Training (Teacher-First Strategy) ==="

    SFT_OUTPUT="/workspace/models/sft-teacher-merged"
    if [ -f "$SFT_OUTPUT/config.json" ]; then
        ok "SFT teacher already exists: $SFT_OUTPUT"
        return 0
    fi

    log "Training SFT teacher (2 epochs, LoRA r=16)..."
    $PY cluster/train_sft.py \
        --epochs 2 --lr 2e-5 --batch-size 8 --gradient-accumulation 4 \
        --output-dir /workspace/models/sft-teacher \
        2>&1 | tee -a "$LOG"

    # Merge LoRA into full model
    if [ -d "/workspace/models/sft-teacher" ]; then
        log "Merging LoRA adapter into full model..."
        $PY -c "
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
base = 'Qwen/Qwen2.5-0.5B-Instruct'
model = AutoModelForCausalLM.from_pretrained(base, torch_dtype=torch.bfloat16)
model = PeftModel.from_pretrained(model, '/workspace/models/sft-teacher')
model = model.merge_and_unload()
model.save_pretrained('$SFT_OUTPUT', safe_serialization=True)
tok = AutoTokenizer.from_pretrained(base)
tok.save_pretrained('$SFT_OUTPUT')
print('SFT teacher merged and saved.')
" 2>&1 | while read line; do log "$line"; done
        ok "SFT teacher ready: $SFT_OUTPUT"
    else
        err "SFT training failed — check $LOG"
        return 1
    fi
}

# ═══════════════════════════════════════════════════════════════════════════
# Phase 3: Paper-Grade Experiments
# ═══════════════════════════════════════════════════════════════════════════
run_paper() {
    log "=== Phase 3: Paper-Grade Experiments ==="

    SFT_TEACHER="/workspace/models/sft-teacher-merged"

    if [ -f "$SFT_TEACHER/config.json" ]; then
        # Use SFT teacher config
        CONFIG="config/sft_teacher.yaml"
        if [ ! -f "$CONFIG" ]; then
            cp config/experiments.yaml "$CONFIG"
            sed -i "s|teacher:.*|teacher: \"$SFT_TEACHER\"|" "$CONFIG"
        fi
        log "Using SFT teacher: $SFT_TEACHER"
    else
        CONFIG="config/experiments.yaml"
        log "Using base teacher (no SFT model found)"
    fi

    # Create output directories
    mkdir -p outputs/{results,predictions,metrics,tables,figures,logs}

    # Run all experiments
    log "Running experiments..."
    $PY -m experiments.runner --paper --config "$CONFIG" \
        2>&1 | tee -a "$LOG"

    # Generate report
    log "Generating paper report..."
    $PY -m experiments.runner --report 2>&1 | tee -a "$LOG"

    ok "Phase 3 complete"
    log "Results: /workspace/outputs/"
}

# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════
case "$MODE" in
    full)
        setup_env
        run_sft
        run_paper
        ok "=== Pipeline Complete ==="
        log "Summary: /workspace/outputs/metrics/summary.csv"
        ;;
    setup)
        setup_env
        ok "=== Setup Complete ==="
        log "Next: bash run_all.sh --sft-only   (or --paper-only)"
        ;;
    sft)
        setup_env
        run_sft
        ok "=== SFT Complete ==="
        log "Teacher saved to /workspace/models/sft-teacher-merged"
        ;;
    paper)
        setup_env
        run_paper
        ok "=== Paper Run Complete ==="
        ;;
    smoke)
        log "=== Smoke Verification ==="
        setup_env
        $PY -m experiments.runner --smoke 2>&1 | tee -a "$LOG"
        ok "Smoke test complete"
        ;;
esac

echo ""
log "Log: $LOG"
