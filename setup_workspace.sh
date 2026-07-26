#!/usr/bin/env bash
# Re-establish the workspace layout after a container restart.
set -euo pipefail
cd /workspace

# realeval must resolve to exactly one copy; the symlink does not survive restarts.
ln -sfn /workspace/H100_package_realeval/realeval /workspace/realeval
echo "realeval -> $(readlink -f /workspace/realeval)"

export PYTHONPATH=/workspace:${PYTHONPATH:-}
export REALEVAL_ADAPTER_ROOT=/workspace/outputs/sft_checkpoints

python3 - <<'PY'
import realeval.data as D
from pathlib import Path
r = Path('/workspace/H100_package_realeval/realeval')
checks = [
    ('group_split',       hasattr(D, 'group_split')),
    ('load_dataset',      hasattr(D, 'load_dataset')),
    ('load_text_corpus',  hasattr(D, 'load_text_corpus')),
    ('student_loader.py', (r / 'student_loader.py').exists()),
    ('real_backend wiring', 'student_loader' in (r / 'real_backend.py').read_text()),
]
bad = [n for n, ok in checks if not ok]
for n, ok in checks:
    print(('[ OK ]' if ok else '[FAIL]'), n)
if bad:
    raise SystemExit(f"missing: {bad} — rerun apply_all_fixes.py")
PY
echo "workspace ready"
