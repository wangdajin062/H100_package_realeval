#!/bin/bash
# gpu_monitor.sh — RunPod GPU 监控工具集（合并 gpu_procs / monitor_gpu / monitor_runpod）
#
# 用法:
#   bash gpu_monitor.sh procs      # 一次性 GPU 进程快照
#   bash gpu_monitor.sh top        # nvtop 交互式监控（q 退出）
#   bash gpu_monitor.sh watch      # 循环实时监控（Ctrl+C 退出）
#
# 共用 SSH 连接配置，通过 POD/KEY 环境变量可覆盖默认值。

set -euo pipefail
POD="${POD:-mhypfkvge474n8-64411fb1@ssh.runpod.io}"
KEY="${KEY:-$HOME/.ssh/id_ed25519}"
SSH_OPTS="-tt -o BatchMode=yes -o ConnectTimeout=20 -o StrictHostKeyChecking=accept-new -i $KEY"

usage() {
    echo "Usage: $0 {procs|top|watch}"
    echo "  procs  — 一次性 GPU 进程快照（含命令行）"
    echo "  top    — nvtop 交互式可视化监控（q 退出）"
    echo "  watch  — 循环实时监控（每秒刷新，Ctrl+C 退出）"
    exit 1
}

MODE="${1:-}"
if [ -z "$MODE" ] || [ "$MODE" = "-h" ] || [ "$MODE" = "--help" ]; then
    usage
fi

case "$MODE" in
    procs)
        REMOTE='echo "===== GPU overview ====="; nvidia-smi --query-gpu=index,name,utilization.gpu,utilization.memory,memory.used,memory.total,power.draw,power.limit,temperature.gpu --format=csv,noheader; echo; echo "===== GPU compute processes ====="; nvidia-smi --query-compute-apps=pid,used_memory,process_name --format=csv,noheader; echo; echo "===== process cmdline ====="; for pid in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader); do cmd=$(tr "\0" " " < /proc/$pid/cmdline 2>/dev/null | cut -c1-120); echo "  PID $pid: $cmd"; done; exit'
        { printf '%s\n' "$REMOTE"; } | ssh $SSH_OPTS "$POD" 2>&1 | tr -d '\r' | grep -aE '=====|^0, |^[0-9]+, [0-9]+ MiB, |^  PID |^[0-9]+ MiB'
        ;;
    top)
        { printf 'nvtop\n'; } | ssh $SSH_OPTS "$POD" 2>&1
        ;;
    watch)
        REMOTE='while true; do clear; date "+%Y-%m-%d %H:%M:%S"; echo ===== GPU =====; nvidia-smi --query-gpu=index,name,utilization.gpu,utilization.memory,memory.used,memory.total,power.draw,temperature.gpu --format=csv,noheader; echo; echo ===== python 进程 =====; ps aux | grep python | grep -v grep | head -8; echo; echo ===== GPU 计算进程 =====; nvidia-smi --query-compute-apps=pid,used_memory,process_name --format=csv,noheader 2>/dev/null || echo none; sleep 1; done'
        { printf '%s\n' "$REMOTE"; } | ssh $SSH_OPTS "$POD" 2>&1
        ;;
    *)
        echo "错误: 未知子命令 '$MODE'"
        usage
        ;;
esac
