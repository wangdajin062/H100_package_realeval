#!/usr/bin/env bash
# runpod_rerun.sh — RunPod H100 优先级重跑清单（P0 → P1 → P2 → 验证 → 出图）
#
# 用法（在 pod 内 /workspace/H100_package_realeval 目录）:
#   bash scripts/runpod_rerun.sh              # 全量按优先级重跑（--resume 断点续跑）
#   bash scripts/runpod_rerun.sh --no-resume  # 不跳过已完成实验（从头跑）
#   SYNC=1 bash scripts/runpod_rerun.sh       # 先 git reset 到 origin/main
#   DATA_FIX=1 bash scripts/runpod_rerun.sh   # 先跑 TAF-28k 转录/特征修复链（约 55 分钟）
#   SKIP_P0=1 bash scripts/runpod_rerun.sh    # 跳过 P0 阶段
#
# 关键约定（见 docs/REPRODUCIBILITY.md）:
#   - 重跑单实验一律 --no-archive，避免误清全部结果
#   - exp5/13/14 依赖 exp1 生成的 split manifest，故 exp1 必须先跑
#   - 结果落在 outputs/results/，图表脚本从该目录读取
set -euo pipefail

cd "$(dirname "$0")/.."                      # 回到仓库根目录

# ── 0. 环境变量 + 解释器 ────────────────────────────────────────────────
export REALEVAL_DATA_ROOT=/workspace/data
export REALEVAL_MODELS_ROOT=/workspace/models
export REALEVAL_ADAPTER_ROOT=/workspace/outputs/lora_manual
export HF_HOME=/workspace/hf_cache
export HF_HUB_ENABLE_HF_TRANSFER=1
export HF_HUB_DISABLE_PROGRESS_BARS=1
export TOKENIZERS_PARALLELISM=false
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"

if [ -x /workspace/venv/bin/python ]; then
  PY=/workspace/venv/bin/python
else
  PY=python
fi
RUNNER="$PY -m experiments.runner --no-archive --config config/runpod_h100.yaml"

RESUME="--resume"
SYNC=0
DATA_FIX=0
SKIP_P0=0
for a in "$@"; do
  [ "$a" = "--no-resume" ] && RESUME=""
  [ "$a" = "SYNC=1" ] && SYNC=1
  [ "$a" = "DATA_FIX=1" ] && DATA_FIX=1
  [ "$a" = "SKIP_P0=1" ] && SKIP_P0=1
done
[ "${SYNC:-0}" = "1" ] && SYNC=1
[ "${DATA_FIX:-0}" = "1" ] && DATA_FIX=1
[ "${SKIP_P0:-0}" = "1" ] && SKIP_P0=1

echo "=== PY=$PY  RESUME=$RESUME  SYNC=$SYNC  DATA_FIX=$DATA_FIX  SKIP_P0=$SKIP_P0 ==="

# ── 1. 代码同步（可选 SYNC=1） ──────────────────────────────────────────
if [ "$SYNC" = "1" ]; then
  echo "=== [1] git sync to origin/main ==="
  git fetch origin && git checkout main && git reset --hard origin/main
  git log --oneline -1
else
  echo "=== [1] skip git sync（设 SYNC=1 开启）==="
fi

# ── 2. 快速自检 ─────────────────────────────────────────────────────────
echo "=== [2] GPU + 存储自检 ==="
$PY -c "import torch; print('torch', torch.__version__, '|', torch.cuda.get_device_name(0))"
ls /workspace/data /workspace/models /workspace/hf_cache 2>/dev/null || echo "  ⚠ 数据/模型目录缺失，先跑 cluster/setup_runpod.sh"

echo "=== [2a] pytest 单元测试（应 65 passed）==="
$PY -m pytest tests/ -q || echo "  ⚠ pytest 有失败，见上"

echo "=== [2b] 硬件/存储检查 ==="
$PY -m experiments.runner --check || true
$PY -m experiments.runner --storage-check || true

# ── 3. TAF-28k 数据修复链（可选 DATA_FIX=1，约 55 分钟） ────────────────
if [ "$DATA_FIX" = "1" ]; then
  echo "=== [3] TAF-28k 转录 → 声学特征 ==="
  $PY data/scripts/transcribe_taf28k.py --resume
  $PY data/scripts/build_taf28k_npz.py
else
  echo "=== [3] skip TAF-28k 数据修复（设 DATA_FIX=1 开启）==="
fi

# ── 4. P0（结论反转 / 核心数字）─────────────────────────────────────────
if [ "$SKIP_P0" = "1" ]; then
  echo "=== [4] skip P0（设 SKIP_P0=1 已跳过）==="
else
  echo "=== [4] P0: exp1(先跑，生成 split manifest) → exp3 → exp11 → exp2 → exp9 ==="
  $RUNNER $RESUME --exp 1
  $RUNNER $RESUME --exp 3,11
  $RUNNER $RESUME --exp 2,9
fi

# ── 5. P1 主结果链（Tab.3 → Fig.3）──────────────────────────────────────
echo "=== [5] P1: exp4 → exp5 → exp10 → exp13 → exp14 ==="
$RUNNER $RESUME --exp 4
$RUNNER $RESUME --exp 5,10,13,14

# ── 6. P2 补测 / 降级 ───────────────────────────────────────────────────
echo "=== [6] P2: exp6 → exp7 → exp8 → exp12 ==="
$RUNNER $RESUME --exp 6,7,8,12

# ── 7. 验证 ─────────────────────────────────────────────────────────────
echo "=== [7] 字段合约 / 绘图对齐 / 一致性守门员 ==="
$PY -m experiments.runner --validate-contract || echo "  ⚠ validate-contract 非零（缺测字段会报 MISSING，属预期）"
$PY docs/figure_scripts/check_alignment.py || echo "  ⚠ check_alignment 非零（MISSING 属预期，实测后应 PASS）"
$PY -m experiments.consistency_check || echo "  ⚠ consistency_check 标出 CITED/DRIFT，属设计行为"

# ── 8. 出图 + 回收提示 ──────────────────────────────────────────────────
echo "=== [8] 生成论文图表 ==="
cd docs/figure_scripts && $PY generate_all.py && cd ../..

echo "=== ALL DONE — 结果回收（在 pod 内执行，把 b64 文本贴回本地解码）==="
echo "  tar czf - outputs/results | base64"
echo "  （本地: base64 -d | tar xzf -，覆盖 D 盘 outputs/results/）"
