#!/usr/bin/env bash
# cleanup_runpod.sh — Free up disk space on RunPod container
# Run as root:  bash cleanup_runpod.sh
set -euo pipefail

REPO="/workspace/H100_package_realeval"
START_AVAIL=$(df /workspace --output=avail 2>/dev/null | tail -1)
echo "===== RunPod 容器空间清理 ====="
echo "开始时间: $(date)"
echo ""

# ── Tier 1: 完全安全 ──
echo "──────────────────────────────────────"
echo "🟢 [Tier 1] 安全删除 (备份包 / pip缓存 / pyc)"
echo "──────────────────────────────────────"

echo "→ 删除备份压缩包..."
rm -f /workspace/h100_backup.tar.gz
rm -f /workspace/results_latest.tar.gz
rm -f /workspace/results_final.tar.gz
echo "  已删除 h100_backup.tar.gz, results_latest.tar.gz, results_final.tar.gz"

echo "→ 清理 pip 缓存..."
pip cache purge 2>/dev/null || true

echo "→ 清理 Python 字节码缓存..."
find "$REPO" -name "__pycache__" -exec rm -rf {} + 2>/dev/null; true
find "$REPO" -name "*.pyc" -delete 2>/dev/null; true
echo "  已清理 __pycache__ 和 .pyc"

# ── Tier 2: 大概率安全 ──
echo ""
echo "──────────────────────────────────────"
echo "🟡 [Tier 2] 清理 HF 缓存中未使用的模型版本"
echo "──────────────────────────────────────"

# 检查各模型大小
for model in \
  /workspace/hf_cache/models--Qwen--Qwen2.5-0.5B \
  /workspace/hf_cache/models--Qwen--Qwen2.5-0.5B-Instruct \
  /workspace/hf_cache/models--Qwen--Qwen2.5-1.5B-Instruct \
  /workspace/hf_cache/models--Qwen--Qwen2.5-7B-Instruct; do
  if [ -d "$model" ]; then
    sz=$(du -sh "$model" 2>/dev/null | cut -f1)
    echo "→ 删除未用模型: $model ($sz)"
    rm -rf "$model"
  fi
done
echo "  保留: Qwen2.5-3B-Instruct"

# HuggingFace cache — 检查是否与 hf_cache 重叠
if [ -d /workspace/.cache/huggingface ]; then
  HF_SIZE=$(du -sh /workspace/.cache/huggingface 2>/dev/null | cut -f1)
  echo "→ 检查 .cache/huggingface (${HF_SIZE})..."
  # 如果 datasets 目录中有数据集缓存较大, 仅保留 tokenizers
  if [ -d /workspace/.cache/huggingface/datasets ]; then
    DS_SIZE=$(du -sh /workspace/.cache/huggingface/datasets 2>/dev/null | cut -f1)
    echo "   datasets 缓存: ${DS_SIZE}, 可以安全删除"
    rm -rf /workspace/.cache/huggingface/datasets
  fi
  echo "  保留: .cache/huggingface (tokenizers 配置)"
fi

echo "→ 检查 hf_cache/hub 是否多余..."
if [ -d /workspace/hf_cache/hub ] && [ -d /workspace/hf_cache ] && [ "$(ls -A /workspace/hf_cache/hub 2>/dev/null)" ]; then
  HUB_SIZE=$(du -sh /workspace/hf_cache/hub 2>/dev/null | cut -f1)
  # hub 目录通常是 snapshots 的 symlink/副本
  echo "   hf_cache/hub: ${HUB_SIZE}"
  echo "   保留不删 (可能是实际存储)"
fi

# ── Tier 3: 仓库内文件清理 ──
echo ""
echo "──────────────────────────────────────"
echo "🔵 [Tier 3] 仓库内无用文件 (有Bug的脚本/旧版本/可再生产物)"
echo "──────────────────────────────────────"

cd "$REPO"

echo "→ 删除有严重Bug的未追踪实验脚本 (代码审查确认完全无法运行)..."
for f in \
  experiments/exp9_cot_ablation.py \
  experiments/exp10_teacher_scale.py \
  experiments/exp12_fraudfusion_baseline.py \
  experiments/exp14_gguf_comparison.py \
  experiments/train_ovfreeze_paper.py; do
  if [ -f "$f" ] && git status --porcelain "$f" 2>/dev/null | grep -q '??'; then
    echo "   删除: $f"
    rm -f "$f"
  elif [ -f "$f" ]; then
    echo "   跳过(已追踪): $f"
  fi
done

echo "→ 删除旧版本论文..."
rm -f docs/v25.tex docs/v25_blind.tex
echo "   已删除: docs/v25.tex, docs/v25_blind.tex"

echo "→ 删除旧版图文存档..."
if [ -d docs/v27 ]; then
  rm -rf docs/v27
  echo "   已删除: docs/v27/"
fi

echo "→ 删除代码审查记录..."
if [ -d docs/review ]; then
  rm -rf docs/review
  echo "   已删除: docs/review/"
fi

echo "→ 删除可再生的图片产物 (可随时通过 generate_all.py 重新生成)..."
rm -f docs/figure/fig1_architecture.png
rm -f docs/figure/fig01_architecture.pdf
echo "   已删除: fig1_architecture.png, fig01_architecture.pdf"

# ── Tier 4: Git 深度压缩 ──
echo ""
echo "──────────────────────────────────────"
echo "⚪ [Tier 4] Git 历史压缩"
echo "──────────────────────────────────────"

echo "→ 压缩 git 对象..."
git gc --aggressive --prune=now 2>/dev/null || true
echo "   完成: git gc --aggressive --prune=now"

# ── 清理 shell 历史 ──
rm -f /root/.bash_history /root/.python_history 2>/dev/null || true

# ── Tier 5: 历史冗余 realeval 拷贝 ──
echo ""
echo "──────────────────────────────────────"
echo "🧹 [Tier 5] 清理历史冗余 realeval 拷贝"
echo "──────────────────────────────────────"

AUTHORITATIVE="/workspace/H100_package_realeval/realeval"
KEEP_SYMLINK="/workspace/realeval"

echo "→ 权威路径: $AUTHORITATIVE"
echo "→ 保留符号链接: $KEEP_SYMLINK (实验框架依赖)"

# 找到所有非权威、非符号链接的 realeval 目录
while IFS= read -rd '' candidate; do
  # 跳过权威路径
  if [ "$(realpath "$candidate" 2>/dev/null)" = "$(realpath "$AUTHORITATIVE" 2>/dev/null)" ]; then
    continue
  fi
  # 跳过符号链接本身
  if [ -L "$candidate" ]; then
    echo "  跳过符号链接: $candidate -> $(readlink "$candidate")"
    continue
  fi
  # 跳过容器启动必需的符号链接
  if [ "$(realpath "$candidate" 2>/dev/null)" = "$(realpath "$KEEP_SYMLINK" 2>/dev/null)" ]; then
    continue
  fi
  sz=$(du -sh "$candidate" 2>/dev/null | cut -f1)
  echo "→ 删除冗余 realeval: $candidate ($sz)"
  rm -rf "$candidate"
done < <(find /workspace -maxdepth 3 -type d -name "realeval" -print0 2>/dev/null)

# 清理 repo/ 下的历史拷贝 (测试日志提到 /workspace/repo/ 含旧 realeval)
for hist_dir in /workspace/repo /workspace/repo_*; do
  if [ -d "$hist_dir" ]; then
    sz=$(du -sh "$hist_dir" 2>/dev/null | cut -f1)
    # 只删除包含 realeval 但非 H100_package_realeval 的历史拷贝
    if [ -d "$hist_dir/realeval" ] && [ "$hist_dir" != "/workspace/H100_package_realeval" ]; then
      echo "→ 删除历史仓库拷贝: $hist_dir ($sz)"
      rm -rf "$hist_dir"
    fi
  fi
done

# 清理根目录下遗落的 orphan 文件 (测试日志 1.2 节提到 /workspace/data.py 遮蔽 bug)
for orphan in /workspace/data.py.orphan /workspace/data.py; do
  if [ -f "$orphan" ]; then
    echo "→ 删除孤儿文件: $orphan"
    rm -f "$orphan"
  fi
done

# ── 统计结果 ──
echo ""
echo "=============================="
echo "✅ 清理完成"
echo "=============================="
END_AVAIL=$(df /workspace --output=avail 2>/dev/null | tail -1)
FREED=$(( (END_AVAIL - START_AVAIL) / 1024 ))
echo "释放空间: ~${FREED} MB"
echo "当前可用: $(df -h /workspace 2>/dev/null | tail -1 | awk '{print $4}')"
echo "结束时间: $(date)"
echo ""
echo "提示: 若仍需更多空间，可考虑:"
echo "  - 删除 TAF-28k 原始音频: rm -rf /workspace/data/TAF28k (可释放20G, 但将丢失原始数据!)"
echo "  - 删除 sft-teacher 权重: rm -rf /workspace/models/sft-teacher-merged"
echo "  - 检查 venv 能否精简: du -sh /workspace/venv"
