QAD-MultiGuard · RunPod 恢复后执行清单

> 依据：`rerun_checklist.md`（P0/P1/P2 分级）× 2026-08-13 字段对齐与 H100 就绪审核（D 盘 `4278290` 已推送 GitHub）
> 环境：RunPod H100 单卡 80GB（pod `mhypfkvge474n8`）· 持久 venv `/workspace/venv` · 代码 `/workspace/H100_package_realeval`
> 铁律：**重跑单个实验一律用 `runner --no-archive`，不要用 `run_h100.sh`**（它开头会 `rm -rf outputs/results/*` 清掉全部结果）

---

## 0. 最新验证状态（2026-08-13 本地审核）

| 检查项 | 结果 | 说明 |
|--------|------|------|
| `pytest tests/ -q` | ✅ **65 passed, 1 warning** | 全量测试通过 |
| `check_alignment.py` | ✅ **PASS** | 65 处 `_from_result` 字段全部可解析 |
| `--validate-contract` | ✅ | 字段合约校验（H100 实测后应 PASS） |
| `consistency_check` | ⚠️ 预期 P0 | 标出 CITED/DRIFT（实测与论文声称有差距，属设计行为） |
| `--report` | ✅ | 生成 5 个交付物（summary.csv, tables.md, Table2.tex, fig_latency_benchmark.png/.pdf） |
| 14 个实验 `run_paper` 路径 | ✅ | 全部存在且可导入 |
| `realeval` 核心模块 | ✅ | `real_backend`, `models`, `data`, `specdec`, `privacy`, `metrics`, `benchmark` 全部可用 |
| 配置加载 | ✅ | `runpod_h100.yaml` 加载正常，profile=`runpod_1xH100_80GB` |

**结论：H100 上可以跑出所有结果。** 本机执行 `--paper` 正确报 `GPU 显存不足（11.8GB 可用，需要 35GB）`，这是预期的保护行为。

---

## 阶段 0 · 前置准备（Pod 恢复后第一步）

```bash
# 1) RunPod 控制台启动 pod → 网页终端 tmux attach -t realeval（若需看实时 GPU/日志）
# 2) SSH 进入（RunPod 强制 PTY）
ssh -tt mhypfkvge474n8-64411fb1@ssh.runpod.io -i ~/.ssh/id_ed25519

# 3) 代码同步到最新（origin/main，含 smoke 移除 + 路径统一 + P0/P1/P2/P3 审计修复）
cd /workspace/H100_package_realeval
git fetch origin && git checkout main && git reset --hard origin/main
git log --oneline -1        # 应为 origin/main 最新提交

# 4) venv 存活确认（容器重启会清系统 pip，venv 在持久卷不受影响）
/workspace/venv/bin/python -c "import torch; print(torch.cuda.device_count(), torch.version.__version__)"

# 5) 数据/模型确认
ls /workspace/data /workspace/models /workspace/hf_cache

# 6) H100 就绪快速自检（可选，应全部 ✅）
/workspace/venv/bin/python -c "
from pathlib import Path
import ast
print('run_h100.sh:', Path('run_h100.sh').exists())
print('paper_pipeline.py:', Path('experiments/paper_pipeline.py').exists())
print('runpod_h100.yaml:', Path('config/runpod_h100.yaml').exists())
from config.loader import load_config
c = load_config('config/runpod_h100.yaml')
print('config profile:', c.get('profile'))
print('GPU 显存检查: 需 ≥35GB 可用')
"
```

## 阶段 0.5 · 多 seed 配置（一次配好）

多 seed 配置已内置（`reproducibility.exp*_seeds`，默认 5，见 `config/experiments.yaml` + `config/runpod_h100.yaml`），无需手动追加。

> ⚠️ **4 处 std 补齐的两种路径**（exp1/exp3/exp11/exp14 目前单次运行、无实测 std，`check_alignment.py` 报 4 处 MISSING）：
>
> - **路径 A（推荐先走）**：不改脚本，跑完后接受「回退论文误差条 + `_MISSING_PLACEHOLDERS` 标注 NOT measured」的诚实状态，清单里其余数字先对齐。
> - **路径 B（需真实误差条）**：为 exp1/exp3/exp11/exp14 增加多 seed 支持（参照 exp2 的 `n_seeds` 模式）——这是**代码改动**，须在本地 D 盘做、审核后提交推送，再上 Pod 重跑。

---

## 阶段 1 · P0（结论反转/核心数字崩塌，最先处理）

> 命令统一前缀：`cd /workspace/H100_package_realeval && /workspace/venv/bin/python -m experiments.runner --no-archive --config config/runpod_h100.yaml --exp N`

| # | 对应清单        | 实验          | 命令`--exp` | 验证目标 / 通过标准                                                                                                                       |
| - | --------------- | ------------- | ------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| 1 | Tab.5 · §KL   | exp2 损失消融 | `2`         | 多 seed（5）跑完：`variants[*].std` 非 None、非 0.007 恒值；**若 kl_only 仍最差 → 重构 §Method/Highlights「Pure-KL 最优」立论** |
| 2 | Tab.CoT         | exp9 思维链   | `9`         | `with_cot.fpr` 应远低于 0.9573（生成式判定已修）；**若 CoT 仍反转（with < without）→ 删除/改写「CoT 有效」结论**                 |
| 3 | Fig.7a · §OVF | exp1 + exp3   | `1,3`       | `drift_pct_final` / `conditions.*.variance_drift_pct` 随 OVF **响应变化，不再恒 61.479**                                        |
| 4 | Fig.5a          | exp11 量化    | `11`        | 4 方案各自独立：fp16=显式半精度、int4=FP4、nf4=NF4、int8=8-bit（`models.py` 已修）                                                      |

## 阶段 2 · P1 主结果链（Tab.3 → Fig.3 → Tab.2 → Tab.4 → Fig.4 → Fig.5b）

| #  | 对应清单       | 实验    | 命令`--exp` | 验证目标                                                                   |
| -- | -------------- | ------- | ------------- | -------------------------------------------------------------------------- |
| 5  | Tab.3 QAD      | exp1    | `1`         | 真实 QAD F1（现 0.4256）；trajectory 供 Fig.4 重绘                         |
| 6  | Tab.3 QAD+OVF  | exp3    | `3`         | `ov_freeze_full.f1`（现 0.688）——**旗舰数字**                    |
| 7  | Tab.3 PTQ 系列 | exp11   | `11`        | 4 方案 F1（现 fp16 0.3125 / int8 0.3452 / int4 0.4287 / nf4 0.3072）       |
| 8  | Tab.3 Q4_K_M   | exp14   | `14`        | bf16(0.5853) vs q4km(0.7025)                                               |
| 9  | Tab.4 跨数据集 | exp5    | `5`         | taf28k(0.2611)/chifraud(0.5654)/advfraud curated(0.0897)+full(0.1238) 实测 |
| 10 | Tab.2 恢复率   | 随 5–8 | 回填          | 恢复率 = 实测 F1 / BF16 基线，随 Tab.3                                     |

> 注：advfraud curated / ldp 等字段现缺测时**显式报 None**（不再静默回退论文自引值），重跑后一律用实测替换。

## 阶段 3 · P2（补测 / 降级）

| #  | 对应清单                   | 实验  | 命令`--exp` | 处理方式                                                                                                                |
| -- | -------------------------- | ----- | ------------- | ----------------------------------------------------------------------------------------------------------------------- |
| 11 | Tab.spec                   | exp6  | `6`         | 补测 generic α（现 0.468）与真实 wall-clock 加速；**不可测 → 全部降级「理论/引用」并去掉 measured 字样**        |
| 12 | Tab.privacy                | exp7  | `7`         | 补测 WER/PESQ/STOI/MOS（现为空）；更正 speaker 数 10→11（acc 0.0909≈随机，结论保留）                                  |
| 13 | Tab.fusion                 | exp13 | `13`        | 类目轴对齐：softmax/sigmoid/transformer vs early/late/hybrid，用一致定义重跑；**0.92 来自融合层，勿归因 QAD-LLM** |
| 14 | 端侧时延                   | exp8  | `8`         | H100 已测；Snapdragon 无 → 正文标注「预估」                                                                            |
| 15 | Tab.2 footprint            | exp12 | `12`        | footprint 已实测 491.4MB → 更正论文 248MB；确认仍 ≤500MB                                                              |
| 16 | §NBE/§arch LoRA/§误分类 | —    | —            | 无对应实验 → 补测或标注「引自 NVIDIA / illustrative」                                                                  |

## 阶段 4 · 每步 / 整体验证（对齐审核闭环）

```bash
# 字段合约验证（H100 实测后应无 [FAIL]；若字段缺测会标 MISSING，属预期）
/workspace/venv/bin/python -m experiments.runner --validate-contract

# 绘图字段对齐（65 处字段全部可解析才算 PASS）
/workspace/venv/bin/python docs/figure_scripts/check_alignment.py

# 论文数字 vs 实测一致性守门员（H100 实测后应无 DRIFT；实测与论文声称有 DRIFT 属预期）
/workspace/venv/bin/python -m experiments.consistency_check

# 出图（可选，从已有结果生成）
/workspace/venv/bin/python -m experiments.runner --report
```

## 阶段 5 · 结果回收与同步 GitHub

```bash
# 打包拉回本地（scp/sftp 不可用，用 tar+base64，见 runpod 笔记）
cd /workspace/H100_package_realeval && tar czf - outputs/results | base64   # 输出 b64 文本 → 本地解码解包
```

1. 本地 D 盘覆盖 `outputs/results/*`，核对 `check_alignment.py` 与 `--validate-contract`。
2. **H100 实测后更新 `experiments/consistency_check.py` 的 `PAPER_CLAIMS` 表**，把声称值替换为实测值，使其成为长期守门员。
3. 更新 `reports/` 下的运行/审计报告，提交：
   ```bash
   cd /d/Projects/H100_package_realeval
   git add outputs/results reports/ experiments/consistency_check.py && git commit -m "results: 同步 RunPod H100 实测结果" && git push origin main
   ```
4. 回填论文 `v25_blind.tex` 前，逐项对照 `rerun_checklist.md` 判定（P0 结论反转项先改结论再改数字）。

---

## 快速对照表：本次审核已确认「无需重跑」的项

| 项                                  | 依据                                                     |
| ----------------------------------- | -------------------------------------------------------- |
| 图像脚本 import / 字段锚点          | `check_alignment.py` + `_extract` 全路径可解析       |
| 脚本可导入性                        | 14/14 模块 import 成功                                   |
| exp8 latency p50/p99                | 已改结构化`latency_detail`，消除 p99 误读 p50          |
| 量化分支（fp16/nf4/int4/int8 区分） | `models.py` 已修（fp16 显式半精度、int4=FP4、nf4=NF4） |
| exp2 多 seed 机制                   | 已实现（`reproducibility.exp*_seeds`，默认 5）         |
