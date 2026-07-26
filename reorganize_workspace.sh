#!/usr/bin/env bash
# reorganize_workspace.sh — 整理 /workspace 目录结构
set -euo pipefail

REPO="/workspace/H100_package_realeval"
echo "===== 整理容器工作目录 ====="

# ── 1. 将根目录的零散 .py 移入 repo 对应目录 ──
echo ""
echo "--- 1. 零散脚本归位 ---"
cd /workspace

declare -A PY_MAP=(
  [train_ovfreeze_paper.py]="experiments/"
  [train_lora_manual.py]="cluster/"
  [train_ovf_simple.py]="cluster/"
  [apply_all_fixes.py]="cluster/"
  [fix_train_sft.py]="cluster/"
  [fix_collator.py]="cluster/"
  [diag_trainer.py]="cluster/"
  [diag_nan.py]="cluster/"
  [diagnose_v25_run.py]="cluster/"
  [exp6_speculative_decoding.py]="experiments/"
  [gpu_dashboard.py]="cluster/"
  [gpu_monitor_daemon.py]="cluster/"
  [kanban.py]="cluster/"
  [do_start.py]="cluster/"
)
for f in "${!PY_MAP[@]}"; do
  if [ -f "/workspace/$f" ]; then
    echo "  $f → ${REPO}/${PY_MAP[$f]}"
    mv "/workspace/$f" "${REPO}/${PY_MAP[$f]}$f"
  fi
done

# ── 2. shell 脚本归位 ──
echo ""
echo "--- 2. Shell 脚本归位 ---"
for f in run_all.sh run_h100.sh run.sh setup.sh start_gpu.sh setup_workspace.sh; do
  if [ -f "/workspace/$f" ] && [ ! -L "/workspace/$f" ]; then
    echo "  $f → ${REPO}/"
    mv "/workspace/$f" "${REPO}/$f"
  fi
done

# ── 3. 配置文件/文档归位 ──
echo ""
echo "--- 3. 配置文件/文档归位 ---"
for f in requirements.txt pyproject.toml README.md LICENSE; do
  if [ -f "/workspace/$f" ] && [ ! -L "/workspace/$f" ]; then
    echo "  $f → ${REPO}/"
    # 对比内容，若不同才覆盖
    if [ -f "${REPO}/$f" ]; then
      if ! cmp -s "/workspace/$f" "${REPO}/$f"; then
        cp "/workspace/$f" "${REPO}/$f"
        echo "  (内容更新到 repo)"
      fi
      rm "/workspace/$f"
    else
      mv "/workspace/$f" "${REPO}/$f"
    fi
  fi
done

# ── 4. 数据文件归位 ──
echo ""
echo "--- 4. 数据文件归位 ---"
for f in analysis_results.json diagnosis_report.json gpu_stats.json; do
  if [ -f "/workspace/$f" ]; then
    echo "  $f → ${REPO}/outputs/"
    mv "/workspace/$f" "${REPO}/outputs/$f"
  fi
done

# ── 5. 大二进制文件处理 ──
echo ""
echo "--- 5. 大文件处理 ---"
if [ -f "/workspace/cloudflared" ]; then
  sz=$(du -h "/workspace/cloudflared" | cut -f1)
  echo "  cloudflared (${sz}) — 挪到 cluster/"
  mv /workspace/cloudflared "${REPO}/cluster/cloudflared"
fi
if [ -f "/workspace/quickstart_runpod.ipynb" ]; then
  echo "  quickstart_runpod.ipynb → ${REPO}/"
  mv /workspace/quickstart_runpod.ipynb "${REPO}/"
fi
if [ -f "/workspace/Untitled1.ipynb" ]; then
  rm /workspace/Untitled1.ipynb
  echo "  删除 Untitled1.ipynb (空的默认 notebook)"
fi

# ── 6. 清理垃圾文件 ──
echo ""
echo "--- 6. 删除垃圾文件 ---"
# 孤儿 data.py
rm -f /workspace/data.py.orphan /workspace/data.py
# RunPod patch diff (已合入不需要)
rm -f /workspace/runpod_patch.diff
# 日志
rm -f /workspace/streamlit.log /workspace/gpu_dashboard.log
# 奇怪命名的文件
rm -f /workspace/GPU\ ban /workspace/\=0.46.1
# pyc
find /workspace/H100_package_realeval -name "__pycache__" -exec rm -rf {} + 2>/dev/null; true
find /workspace/H100_package_realeval -name "*.pyc" -delete 2>/dev/null; true

# ── 7. 备份压缩包 ──
echo ""
echo "--- 7. 删除旧备份 ---"
rm -f /workspace/h100_backup.tar.gz /workspace/results_latest.tar.gz /workspace/results_final.tar.gz

# ── 8. 确保符号链接存在 ──
echo ""
echo "--- 8. 确保符号链接 ---"
if [ ! -L "/workspace/realeval" ] || [ "$(readlink /workspace/realeval)" != "${REPO}/realeval" ]; then
  rm -f /workspace/realeval
  ln -sfn "${REPO}/realeval" /workspace/realeval
  echo "  /workspace/realeval → ${REPO}/realeval (已重建)"
else
  echo "  /workspace/realeval → ${REPO}/realeval (正常)"
fi

# ── 9. 清理未用 HF 模型 ──
echo ""
echo "--- 9. 清理未用 HF 模型缓存 ---"
for m in \
  /workspace/hf_cache/models--Qwen--Qwen2.5-0.5B \
  /workspace/hf_cache/models--Qwen--Qwen2.5-0.5B-Instruct \
  /workspace/hf_cache/models--Qwen--Qwen2.5-1.5B-Instruct \
  /workspace/hf_cache/models--Qwen--Qwen2.5-7B-Instruct; do
  if [ -d "$m" ]; then
    sz=$(du -sh "$m" 2>/dev/null | cut -f1)
    echo "  删除 $m ($sz)"
    rm -rf "$m"
  fi
done
pip cache purge 2>/dev/null || true

# ── 结果 ──
echo ""
echo "===== 整理完成 ====="
echo "当前 /workspace 根目录:"
ls -1 /workspace/ | grep -v -E '^(H100_package_realeval|data|hf_cache|outputs|models|venv|realeval|\.cache|\.git)$' | head -20
echo ""
echo "干净了吗？现在根目录只剩:"
ls -d /workspace/H100_package_realeval /workspace/data /workspace/hf_cache /workspace/outputs /workspace/models /workspace/venv /workspace/realeval /workspace/.cache /workspace/.git 2>/dev/null
