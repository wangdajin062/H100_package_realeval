#!/bin/bash
# monitor_runpod.sh — RunPod Pod (mhypfkvge474n8) 进程/GPU 实时监控，每 1 秒刷新
# 用法: bash monitor_runpod.sh   （Ctrl+C 退出）
# 说明: RunPod 代理忽略 ssh 命令参数，需经 stdin 管道喂命令。每 1 秒刷新 GPU + python 进程。
POD=mhypfkvge474n8-64411fb1@ssh.runpod.io
KEY=~/.ssh/id_ed25519
REMOTE='while true; do clear; date "+%Y-%m-%d %H:%M:%S"; echo ===== GPU =====; nvidia-smi --query-gpu=index,name,utilization.gpu,utilization.memory,memory.used,memory.total,power.draw,temperature.gpu --format=csv,noheader; echo; echo ===== python 进程 =====; ps aux | grep python | grep -v grep | head -8; echo; echo ===== GPU 计算进程 =====; nvidia-smi --query-compute-apps=pid,used_memory,process_name --format=csv,noheader 2>/dev/null || echo none; sleep 1; done'

{ printf '%s\n' "$REMOTE"; } | ssh -tt -o BatchMode=yes -o ConnectTimeout=20 -o StrictHostKeyChecking=accept-new -i "$KEY" "$POD" 2>&1
