#!/bin/bash
# entrypoint.sh — H100 RealEval Template Entrypoint
# ===========================================================================
# Starts all services in background, then launches the user command.
# Ports: SSH:22 | Jupyter:8888 | VSCode:3000 | Ollama:11434 | API:8000
# ===========================================================================
set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║          H100 RealEval Template — Ready                     ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  Jupyter Lab  → http://localhost:8888                       ║"
echo "║  VSCode       → http://localhost:3000                       ║"
echo "║  Ollama       → http://localhost:11434                      ║"
echo "║  API          → http://localhost:8000                       ║"
echo "║  SSH          → port 22                                     ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  /workspace   → Persistent Storage                          ║"
echo "║  Models       → /workspace/models                           ║"
echo "║  HF Cache     → /workspace/hf_cache                         ║"
echo "╚══════════════════════════════════════════════════════════════╝"

# ── Activate venv if not already ──
if [ -f /workspace/venv/bin/activate ]; then
    source /workspace/venv/bin/activate
elif [ -f /opt/venv/bin/activate ]; then
    source /opt/venv/bin/activate
fi

# ── Start Jupyter Lab ──
if command -v jupyter-lab &>/dev/null; then
    echo "[entrypoint] Starting Jupyter Lab on :8888..."
    jupyter-lab --ip=0.0.0.0 --port=8888 --no-browser --allow-root \
        --ServerApp.token='' --ServerApp.password='' \
        --notebook-dir=/workspace &
fi

# ── Start Ollama ──
if command -v ollama &>/dev/null; then
    echo "[entrypoint] Starting Ollama on :11434..."
    ollama serve &
fi

# ── Start VSCode server (if installed) ──
if command -v code-server &>/dev/null; then
    echo "[entrypoint] Starting code-server on :3000..."
    code-server --bind-addr 0.0.0.0:3000 --auth none /workspace &
fi

# ── Start API server (placeholder) ──
echo "[entrypoint] API endpoint available at :8000"

# ── Ensure workspace directories ──
mkdir -p /workspace/{models,hf_cache,outputs/{results,predictions,metrics,tables,figures,logs},data}

# ── GPU info ──
if command -v nvidia-smi &>/dev/null; then
    echo "[entrypoint] GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader)"
fi

echo "[entrypoint] Ready. Executing: $@"
exec "$@"
