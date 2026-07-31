#!/bin/bash
# Probe B: python env + hf cache details
echo "=== which pythons ==="
which -a python python3 2>/dev/null
python --version 2>&1
python3 --version 2>&1
echo "=== pip key packages (python) ==="
python -m pip list 2>/dev/null | grep -iE "^(torch|transformers|datasets|scikit-learn|numpy|scipy|pyyaml|matplotlib|librosa|soundfile|bitsandbytes|peft|accelerate|flash|sentencepiece|tokenizers)" 
echo "=== venv candidates ==="
ls -d /opt/venv /workspace/*venv* /workspace/H100_package_realeval/.venv 2>/dev/null
echo "=== hf cache hub contents ==="
ls /workspace/hf_cache/hub 2>/dev/null | head -20
echo "=== hf cache xet ==="
ls /workspace/hf_cache/xet 2>/dev/null | head
echo "=== python site-packages hints ==="
python -c "import sys; print(sys.executable); print(sys.prefix)" 2>&1
echo "=== done ==="




