#!/bin/bash
while true; do
  clear
  echo "=== $(date '+%H:%M:%S') ==="
  echo "GPU: $(nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader)"
  echo "PROC: $(ps aux | grep paper_pipeline | grep -v grep | head -1 | awk '{print $2, $3"%", $4"%"}')"
  echo "EXP: $(grep '运行 exp' /workspace/H100_package_realeval/outputs/logs/run_h100_final.log | tail -1 | grep -oE 'exp[0-9]+')"
  echo "QAD: $(grep 'QAD epoch' /workspace/H100_package_realeval/outputs/logs/run_h100_final.log | tail -1 | grep -oE 'epoch [0-9]+/[0-9]+')"
  echo "DONE: $(ls /workspace/H100_package_realeval/outputs/results/exp*_*.json 2>/dev/null | wc -l)/14"
  sleep 1
done
