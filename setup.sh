#!/bin/bash
# setup.sh — Environment setup for QAD-MultiGuard
# Usage: bash setup.sh

set -euo pipefail
cd "$(dirname "$0")"

echo "=== QAD-MultiGuard Environment Setup ==="

# Python version check (requires >= 3.10)
PY_VER=$(python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    echo "ERROR: Python >= 3.10 required (found $PY_VER)" >&2
    exit 1
fi
echo "Python $PY_VER OK"

# Create virtual environment
if [ ! -d "venv" ]; then
    python -m venv venv
    echo "Created virtual environment"
fi

# Cross-platform virtualenv activation (Linux/macOS: bin/, Windows Git-Bash: Scripts/)
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
elif [ -f "venv/Scripts/activate" ]; then
    source venv/Scripts/activate
else
    echo "❌ Could not find venv activation script" >&2; exit 1
fi

# Install dependencies (from pyproject.toml)
pip install --upgrade pip
pip install -e .

# Create output directories
mkdir -p outputs/predictions outputs/metrics outputs/statistics outputs/figures outputs/tables outputs/logs outputs/results

echo "=== Setup complete ==="
echo "Run experiments: python -m experiments.runner --smoke"
