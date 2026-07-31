#!/bin/bash
# monitor_gpu.sh — RunPod GPU 多指标可视化监控（nvtop，每秒刷新，q 退出）
# 用法: bash monitor_gpu.sh
# 说明: RunPod 代理忽略 ssh 命令参数，需经 stdin 管道喂命令。nvtop 为 GPU 版 htop，
#       展示利用率/显存/功耗/温度/时钟的彩色条形图与进程列表，1 秒刷新。
POD=mhypfkvge474n8-64411fb1@ssh.runpod.io
KEY=~/.ssh/id_ed25519

# 喂入 nvtop 命令；stdin 关闭后 bash 退出，sss 随之断开
{ printf 'nvtop\n'; } | ssh -tt -o BatchMode=yes -o ConnectTimeout=20 -o StrictHostKeyChecking=accept-new -i "$KEY" "$POD" 2>&1
