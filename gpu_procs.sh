#!/bin/bash
# gpu_procs.sh — RunPod GPU 进程快照（一次性查看，含进程命令行）
# 用法: bash gpu_procs.sh
# 说明: RunPod 代理忽略 ssh 命令参数，需经 stdin 管道喂命令。
POD=mhypfkvge474n8-64411fb1@ssh.runpod.io
KEY=~/.ssh/id_ed25519

REMOTE='echo "===== GPU overview ====="; nvidia-smi --query-gpu=index,name,utilization.gpu,utilization.memory,memory.used,memory.total,power.draw,power.limit,temperature.gpu --format=csv,noheader; echo; echo "===== GPU compute processes ====="; nvidia-smi --query-compute-apps=pid,used_memory,process_name --format=csv,noheader; echo; echo "===== process cmdline ====="; for pid in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader); do cmd=$(tr "\0" " " < /proc/$pid/cmdline 2>/dev/null | cut -c1-120); echo "  PID $pid: $cmd"; done; exit'

{ printf '%s\n' "$REMOTE"; } | ssh -tt -o BatchMode=yes -o ConnectTimeout=20 -o StrictHostKeyChecking=accept-new -i "$KEY" "$POD" 2>&1 | tr -d '\r' | grep -aE '=====|^0, |^[0-9]+, [0-9]+ MiB, |^  PID |^[0-9]+ MiB'
