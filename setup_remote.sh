#!/bin/bash
# Install python deps for the RealEval paper run on the pod
set -x
cd /workspace/H100_package_realeval
export PATH=/usr/local/bin:$PATH
python --version
python -m pip install --no-input --break-system-packages -r requirements.txt bitsandbytes accelerate > /tmp/pip_install.log 2>&1
echo "PIP_EXIT=$?"
python - <<'PYEOF'
import transformers, datasets, sklearn, scipy, yaml, matplotlib, numpy, librosa, soundfile
print("ALL_DEPS_OK", transformers.__version__, datasets.__version__, sklearn.__version__)
try:
    import bitsandbytes
    print("BNB_OK", bitsandbytes.__version__)
except Exception as e:
    print("BNB_MISSING", e)
PYEOF
echo "SETUP_DONE"

