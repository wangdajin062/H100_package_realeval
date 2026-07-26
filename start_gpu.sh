#!/bin/bash
cd /workspace
nohup python scripts/gpu_web.py --port 8890 > gpu_web.log 2>&1 &
echo "GPU Monitor started, PID=$!"

