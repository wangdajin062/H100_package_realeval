#!/bin/bash
cd /workspace/H100_package_realeval || exit 1
tar -xf /tmp/code.tar && echo "EXTRACT_OK"
ls -la experiments/runner.py realeval/io.py config/experiments.yaml docs/figure_scripts/paper_data.py 2>&1
echo "=== python import smoke (after deps install expected) ==="
echo "=== done ==="
