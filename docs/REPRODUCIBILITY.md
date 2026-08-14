# QAD-MultiGuard 复现与重跑指南

本文档是完整实验复现与 H100 重跑的权威参考，以「重新跑出论文数值」为主线组织：先完成环境与前置准备，再按 P0 → P1 → P2 的优先级重跑实验，逐步验证，最后回收结果同步 GitHub。

> **铁律**：重跑单个实验一律用 `runner --no-archive`。`run_h100.sh` 用于全量论文级流水线，**默认保留旧结果**——只有显式传 `--clean`（或设 `CLEAN=1`）才会清空 `outputs/results|metrics|predictions`；需归档清理时先跑 `scripts/archive_and_clear.py`。
> **核心原则**：先改论文结论，再改数字。在数据修复链走完、真实数字稳定前，不要用论文声称值覆盖 `paper_data.py` 的 fallback——那会把「复现失败」伪装成「复现成功」。

---

## 目录

1. [环境配置与前置准备](#1-环境配置与前置准备)
2. [多 seed 配置](#2-多-seed-配置)
3. [重跑执行流程（P0 → P1 → P2）](#3-重跑执行流程p0--p1--p2)
4. [每步验证](#4-每步验证)
5. [结果回收与同步 GitHub](#5-结果回收与同步-github)
6. [一键复现（paper pipeline）](#6-一键复现paper-pipeline)
7. [生成论文图表](#7-生成论文图表)
8. [归档与清理工作流](#8-归档与清理工作流)
9. [CLI 命令参考](#9-cli-命令参考)
10. [配置参数字典](#10-配置参数字典)
11. [字段对齐说明](#11-字段对齐说明)
12. [手机端 Snapdragon 8 Gen 3 实测流程](#12-手机端-snapdragon-8-gen-3-实测流程)
13. [常见问题](#13-常见问题)
14. [TAF-28k 数据修复链](#14-taf-28k-数据修复链音频转录--特征--重跑)

---

## 1. 环境配置与前置准备

### 1.1 依赖安装

```bash
# 克隆仓库
git clone https://github.com/wangdajin062/H100_package_realeval.git
cd H100_package_realeval

# 安装 Python 依赖（可编辑模式）
pip install -e .
# 或
pip install -r requirements.txt
```

### 1.2 运行环境

| 项目 | 要求 |
|------|------|
| Python | ≥ 3.10（实测 3.12.3） |
| PyTorch | ≥ 2.1（实测 2.8.0+cu128） |
| CUDA | 12.x（论文级运行需要 H100 SXM5 80GB；实测 12.8） |
| 磁盘 | ≥ 100 GB（模型权重 + 数据集） |

**RunPod H100 实测环境**（2026-08-03，pod `mhypfkvge474n8`，镜像 `runpod/pytorch:2.8.0`）：

| 组件 | 版本 |
|------|------|
| Python | 3.12.3 |
| PyTorch | 2.8.0+cu128 |
| CUDA / cuDNN | 12.8 / 9.1.0.2 |
| Driver | 580.126.09 |
| GPU | NVIDIA H100 80GB HBM3 ×1 |
| CPU | x86_64, 208 cores |
| transformers | 5.14.1 |
| accelerate | 1.14.0 |
| bitsandbytes | 0.50.0 |
| scikit-learn | 1.9.0 |
| BF16 / Flash Attn / torch.compile / NCCL | ✅ / ✅ / ✅ / ✅ |

> **部署策略**：统一走 RunPod 基础镜像 `runpod/pytorch:2.8.0-py3.12-cuda12.8.0-devel-ubuntu22.04`（见 `template/runpod-template.json`）；`template/Dockerfile` + `docker-compose.yml` 的自建镜像已弃用（2026-08-14），仅作历史参考。

### 1.3 配置文件说明

```
config/
  experiments.yaml    # 基础配置（models、data、training、distillation 等）
  h100.yaml           # H100 硬件覆盖层（BF16、FlashAttention-2、DDP）
  runpod_h100.yaml    # RunPod 云 GPU 覆盖层
```

配置加载顺序：`experiments.yaml` → 覆盖层（如 `h100.yaml`）→ 环境变量（`REALEVAL_*`）

### 1.4 RunPod 前置（Pod 恢复后第一步）

```bash
# 1) RunPod 控制台启动 pod → 网页终端 tmux attach -t realeval（若需看实时 GPU/日志）
# 2) SSH 进入（RunPod 强制 PTY）
ssh -tt <pod-id>@ssh.runpod.io -i ~/.ssh/id_ed25519   # <pod-id> from the RunPod console

# 3) 代码同步到最新（origin/main，含 smoke 移除 + 路径统一 + 第三轮全量审计 P0/P1/P2/P3 全部修复）
cd /workspace/H100_package_realeval
git fetch origin && git checkout main && git reset --hard origin/main
git log --oneline -1        # 应为 origin/main 最新提交

# 4) venv 存活确认（容器重启会清系统 pip，venv 在持久卷不受影响）
/workspace/venv/bin/python -c "import torch; print(torch.cuda.device_count(), torch.__version__)"

# 5) 数据/模型确认
ls /workspace/data /workspace/models /workspace/hf_cache

# 6) H100 就绪快速自检（可选，应全部 ✅）
/workspace/venv/bin/python -c "
from pathlib import Path
print('run_h100.sh:', Path('run_h100.sh').exists())
print('paper_pipeline.py:', Path('experiments/paper_pipeline.py').exists())
print('runpod_h100.yaml:', Path('config/runpod_h100.yaml').exists())
from config.loader import load_config
c = load_config('config/runpod_h100.yaml')
print('config profile:', c.get('profile'))
print('GPU 显存检查: 需 ≥35GB 可用')
"
```

### 1.5 最新验证状态（2026-08-14 第三轮审计后）

| 检查项 | 结果 | 说明 |
|--------|------|------|
| `pytest tests/ -q` | ✅ **65 passed, 1 warning** | 全量测试通过（第三轮审计每批修复均验证一致） |
| `check_alignment.py` | ⚠️ 预期 MISSING | `outputs/` 为空时 67 处 `_from_result` 报 MISSING（有实测结果后应 PASS） |
| `--validate-contract` | ⚠️ 预期 | `outputs/` 为空时 exit 2（exp1 NON_H100 + 13 missing），H100 实测后应 PASS |
| `consistency_check` | ⚠️ 预期 P0 | 标出 CITED/DRIFT（实测与论文声称有差距，属设计行为） |
| `--report` | ✅ | 生成 5 个交付物（summary.csv, tables.md, Table2.tex, fig_latency_benchmark.png/.pdf） |
| 14 个实验 `run_paper` 路径 | ✅ | 全部存在且可导入 |
| `realeval` 核心模块 | ✅ | `real_backend`, `models`, `data`, `specdec`, `privacy`, `metrics`, `benchmark` 全部可用 |
| 配置加载 | ✅ | `runpod_h100.yaml` 加载正常，profile=`runpod_1xH100_80GB` |

**结论：H100 上可以跑出所有结果。** 本机执行 `--paper` 正确报 `GPU 显存不足（11.8GB 可用，需要 35GB）`，这是预期的保护行为。

---

## 2. 多 seed 配置

多 seed 配置已内置（`reproducibility.exp*_seeds`，默认 5，见 `config/experiments.yaml` + `config/runpod_h100.yaml`），无需手动追加。

> ⚠️ **4 处 std 补齐的两种路径**（exp1/exp3/exp11/exp14 目前单次运行、无实测 std，`check_alignment.py` 报 4 处 MISSING）：
>
> - **路径 A（推荐先走）**：不改脚本，跑完后接受「回退论文误差条 + `_MISSING_PLACEHOLDERS` 标注 NOT measured」的诚实状态，清单里其余数字先对齐。
> - **路径 B（需真实误差条）**：为 exp1/exp3/exp11/exp14 增加多 seed 支持（参照 exp2 的 `n_seeds` 模式）——这是**代码改动**，须在本地 D 盘做、审核后提交推送，再上 Pod 重跑。

---

## 3. 重跑执行流程（P0 → P1 → P2）

> 命令统一前缀：`cd /workspace/H100_package_realeval && /workspace/venv/bin/python -m experiments.runner --no-archive --config config/runpod_h100.yaml --exp N`

### 3.1 P0（结论反转 / 核心数字崩塌，最先处理）

| # | 对应清单        | 实验          | 命令`--exp` | 验证目标 / 通过标准                                                                                                                       |
| - | --------------- | ------------- | ------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| 1 | Tab.5 · §KL   | exp2 损失消融 | `2`         | 多 seed（5）跑完：`variants[*].std` 非 None、非 0.007 恒值；**若 kl_only 仍最差 → 重构 §Method/Highlights「Pure-KL 最优」立论** |
| 2 | Tab.CoT         | exp9 思维链   | `9`         | `with_cot.fpr` 应远低于 0.9573（生成式判定已修）；**若 CoT 仍反转（with < without）→ 删除/改写「CoT 有效」结论**                 |
| 3 | Fig.7a · §OVF | exp1 + exp3   | `1,3`       | `drift_pct_final` / `conditions.*.variance_drift_pct` 随 OVF **响应变化，不再恒 61.479**                                        |
| 4 | Fig.5a          | exp11 量化    | `11`        | 4 方案各自独立：fp16=显式半精度、int4=FP4、nf4=NF4、int8=8-bit（`models.py` 已修）                                                      |

### 3.2 P1 主结果链（Tab.3 → Fig.3 → Tab.2 → Tab.4 → Fig.4 → Fig.5b）

| #  | 对应清单       | 实验    | 命令`--exp` | 验证目标                                                                   |
| -- | -------------- | ------- | ------------- | -------------------------------------------------------------------------- |
| 5  | Tab.3 QAD      | exp1    | `1`         | 真实 QAD F1（现 0.4256）；trajectory 供 Fig.4 重绘                         |
| 6  | Tab.3 QAD+OVF  | exp3    | `3`         | `ov_freeze_full.f1`（现 0.688）——**旗舰数字**                    |
| 7  | Tab.3 PTQ 系列 | exp11   | `11`        | 4 方案 F1（现 fp16 0.3125 / int8 0.3452 / int4 0.4287 / nf4 0.3072）       |
| 8  | Tab.3 Q4_K_M   | exp14   | `14`        | bf16(0.5853) vs q4km(0.7025)                                               |
| 9  | Tab.4 跨数据集 | exp5    | `5`         | taf28k(0.2611)/chifraud(0.5654)/advfraud curated(0.0897)+full(0.1238) 实测 |
| 10 | Tab.2 恢复率   | 随 5–8 | 回填          | 恢复率 = 实测 F1 / BF16 基线，随 Tab.3                                     |

> 注：advfraud curated / ldp 等字段现缺测时**显式报 None**（不再静默回退论文自引值），重跑后一律用实测替换。

### 3.3 P2（补测 / 降级）

| #  | 对应清单                   | 实验  | 命令`--exp` | 处理方式                                                                                                                |
| -- | -------------------------- | ----- | ------------- | ----------------------------------------------------------------------------------------------------------------------- |
| 11 | Tab.spec                   | exp6  | `6`         | 补测 generic α（现 0.468）与真实 wall-clock 加速；**不可测 → 全部降级「理论/引用」并去掉 measured 字样**        |
| 12 | Tab.privacy                | exp7  | `7`         | 补测 WER/PESQ/STOI/MOS（现为空）；更正 speaker 数 10→11（acc 0.0909≈随机，结论保留）                                  |
| 13 | Tab.fusion                 | exp13 | `13`        | 类目轴对齐：softmax/sigmoid/transformer vs early/late/hybrid，用一致定义重跑；**0.92 来自融合层，勿归因 QAD-LLM** |
| 14 | 端侧时延                   | exp8  | `8`         | H100 已测；Snapdragon 无 → 正文标注「预估」                                                                            |
| 15 | Tab.2 footprint            | exp12 | `12`        | footprint 已实测 491.4MB → 更正论文 248MB；确认仍 ≤500MB                                                              |
| 16 | §NBE/§arch LoRA/§误分类 | —    | —            | 无对应实验 → 补测或标注「引自 NVIDIA / illustrative」                                                                  |

---

## 4. 每步验证

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

### 快速对照表：本次审核已确认「无需重跑」的项

| 项                                  | 依据                                                     |
| ----------------------------------- | -------------------------------------------------------- |
| 图像脚本 import / 字段锚点          | `check_alignment.py` + `_extract` 全路径可解析       |
| 脚本可导入性                        | 14/14 模块 import 成功                                   |
| exp8 latency p50/p99                | 已改结构化`latency_detail`，消除 p99 误读 p50          |
| 量化分支（fp16/nf4/int4/int8 区分） | `models.py` 已修（fp16 显式半精度、int4=FP4、nf4=NF4） |
| exp2 多 seed 机制                   | 已实现（`reproducibility.exp*_seeds`，默认 5）         |

---

## 5. 结果回收与同步 GitHub

```bash
# 打包拉回本地（scp/sftp 不可用，用 tar+base64，见 runpod 笔记）
cd /workspace/H100_package_realeval && tar czf - outputs/results | base64   # 输出 b64 文本 → 本地解码解包
```

1. 本地 D 盘覆盖 `outputs/results/*`，核对 `check_alignment.py` 与 `--validate-contract`。
2. **H100 实测后更新 `experiments/consistency_check.py` 的 `PAPER_CLAIMS` 表**，把声称值替换为实测值，使其成为长期守门员。
3. 更新 `reports/` 下的运行/审计报告，提交：
   ```bash
   cd /d/Projects/H100_package_realeval
   git add reports/ experiments/consistency_check.py && git commit -m "results: 同步 RunPod H100 实测结果" && git push origin main
   ```
   注意：`outputs/` 整体在 `.gitignore` 中（结果 JSON 属生成物，不进 git）；结果文件本身通过 scp/同步脚本回收，无需 `git add outputs/...`。
4. 回填论文 `v25_blind.tex` 前，逐项对照审计报告判定（P0 结论反转项先改结论再改数字）。

---

## 6. 一键复现（paper pipeline）

在 H100 SXM5 上运行完整论文流水线：

```bash
# 一键运行全部实验（自动归档旧结果）
bash run_h100.sh

# 等价命令
python -m experiments.paper_pipeline --paper --config config/h100.yaml

# 运行指定实验分组
python -m experiments.runner --paper --exp 1,3,6 --config config/h100.yaml

# 跳过运行前归档（调试用）
python -m experiments.runner --paper --no-archive
```

### 实验分组

| 分组 | 实验 | 说明 |
|------|------|------|
| `00_train` | exp1 | QAD 蒸馏训练（为 exp4/exp11 保存模型） |
| `01_baseline` | exp4 | BF16 教师 + 经典基线 |
| `02_quantization` | exp11 | INT4/NVFP4 方案对比 |
| `03_QAD` | exp2 | KL loss 消融 |
| `04_OV-Freeze` | exp3 | OV-Freeze 消融 + 匹配正则控制 |
| `05_latency` | exp8, exp6 | 延迟基准 + 推测解码加速 |
| `06_robustness` | exp5, exp7 | 跨数据集 + 对抗/隐私验证 |

### 输出目录结构

```
outputs/
  results/
    exp1_20260731_120000.json    # 单次实验结果（带时间戳）
    exp2_20260731_120100.json
    ...
    all_experiments.json          # 全量归并（paper_data.py 候补来源）
    metrics.json                  # 聚合指标
    paper_table.md                # 论文表格（Markdown）
    latency.csv / throughput.csv / memory.csv
    paper_tables/                 # LaTeX 表格片段
  archive/
    2026-07-31_120000_experiment_results.md   # 每次重跑前自动归档
  logs/
    experiments.log               # 实验日志
    runlog.jsonl                  # 完整溯源日志（含 git commit、config hash）
```

---

## 7. 生成论文图表

实验完成后，图像脚本从 `outputs/results/` 自动读取结果：

```bash
cd docs/figure_scripts

# 生成所有图（Fig 1–8）
python generate_all.py

# 生成单张图
python fig3_main_results.py
python fig4_loss_convergence.py
python fig5_loss_teacher_ablation.py
python fig6_ovf_ablation.py
python fig7_speculative_decoding.py
python fig8_revision_ablations.py
```

生成的图像保存至 `docs/figure/`（PNG + PDF + TIFF，400 DPI）。

> **注意**：图像脚本（`docs/figure_scripts/`）**不允许修改**。  
> 若图表数值需要更新，请修改实验脚本使其产出正确字段，而非更改图像脚本。

### 数据流

```
实验脚本（exp1–exp14）
    → outputs/results/expN_{ts}.json
    → outputs/results/all_experiments.json
        → docs/figure_scripts/paper_data.py（桥接层）
            → fig3_main_results.py
            → fig4_loss_convergence.py
            → ...
                → docs/figure/fig{N}.png/.pdf/.tiff
```

---

## 8. 归档与清理工作流

每次重跑前，流水线会自动将旧实验结果以带时间戳的 Markdown 保存，然后清空输出目录。

### 自动归档（集成在流水线中）

`python -m experiments.runner --paper` 启动时，若 `outputs/results/` 存在旧结果，会：
1. 构建包含所有实验数据、CSV 表格、图像索引的归档快照
2. 写入 `outputs/archive/{YYYY-MM-DD_HHMMSS}_experiment_results.md`
3. 删除所有旧实验 JSON、CSV 和图像
4. 重建空占位目录

### 手动归档

```bash
# 归档 + 清理（默认行为）
python scripts/archive_and_clear.py

# 仅归档，不清理
python scripts/archive_and_clear.py --archive-only

# 预览，不实际执行
python scripts/archive_and_clear.py --dry-run

# 跳过归档步骤直接运行实验
python -m experiments.runner --paper --no-archive
```

---

## 9. CLI 命令参考

### `python -m experiments.runner`

```
--paper              论文级运行（真实 Qwen + H100）
--exp 1,3,6          仅运行指定实验（编号或 exp1,exp3 格式）
--config path.yaml   指定配置文件（默认 config/experiments.yaml）
--resume             跳过已有结果的实验
--no-archive         跳过运行前的自动归档步骤
--validate-contract  验证最新结果是否满足图像脚本字段合约
--report             从已有结果生成论文表格（不运行实验）
--check              硬件检查
--storage-check      存储挂载检查
--benchmark          仅运行基准测试
```

### `python -m experiments.paper_pipeline`

```
--paper              论文级运行
--no-archive         跳过归档
--config path.yaml   指定配置文件
```

### 环境变量覆盖

所有配置均可通过 `REALEVAL_` 前缀的环境变量覆盖：

```bash
REALEVAL_DATA__DATASET=chifraud python -m experiments.runner --paper
REALEVAL_TRAINING__EPOCHS=3 python -m experiments.runner --paper --exp 1
```

---

## 10. 配置参数字典

完整参数列表见 `config/__init__.py` 的 `CONFIG_SCHEMA` 字典。核心参数如下：

| 参数路径 | 默认值 | 说明 |
|----------|--------|------|
| `models.teacher` | `Qwen/Qwen2.5-0.5B-Instruct` | BF16 同构教师 |
| `models.student` | `Qwen/Qwen2.5-0.5B-Instruct` | 量化学生（同架构） |
| `data.dataset` | `chifraud` | 主训练语料库 |
| `data.max_samples` | `16000` | 最大采样数 |
| `training.batch_size` | `64` | 批次大小 |
| `training.learning_rate` | `5e-5` | 学习率 |
| `training.epochs` | `5` | 训练轮数 |
| `training.quantize` | `int4` | 量化方案 |
| `training.apply_ov_rescaling` | `true` | 启用 OV-Freeze |
| `distillation.temperature` | `2.0` | 蒸馏温度 |
| `distillation.total_steps` | `2000` | 概念步数（Fig4 对齐） |
| `distillation.ovf_activation_ratio` | `0.7` | OV-Freeze 激活时机 |
| `reproducibility.seed` | `42` | 全局随机种子 |
| `speculative_decoding.gamma` | `5` | 草稿 token 数 γ |

---

## 11. 字段对齐说明

详见 `docs/experiment_result_contract.md`。

**核心原则**：
- 图像脚本通过 `paper_data.py` 的 `_get(exp_id, *keys)` 读取实验结果
- 所有字段均配有论文常量作为回退值，保证图像脚本始终可运行
- 实验脚本只走 paper 路径（真实 H100 结果），字段结构完全一致

---

## 12. 手机端 Snapdragon 8 Gen 3 实测流程

本项目的边缘部署目标是生成 **0.5B Q4_K_M GGUF**，用于 Snapdragon 8 Gen 3 或其他 `llama.cpp` 兼容移动平台。

### 12.1 导出 GGUF

1. 训练完成后，使用导出脚本生成 GGUF：
   ```bash
   python scripts/export_to_gguf.py --source outputs/models/exp1_qad --output outputs/models/exp1_qad_q4km.gguf
   ```
2. 导出默认量化类型为 `q4_k_m`，这是 Snapdragon 8 Gen 3 上最推荐的 GGUF 格式。
3. 如果目标机上仍需测试 `q4_0` / `q4_1`，可通过 `--quant-type q4_0` 或 `--quant-type q4_1` 指定。

### 12.2 手机端测试准备

1. 在手机端或安卓开发环境中准备 `llama.cpp`：
   - 推荐使用 `llama.cpp` 的 Android / Snapdragon 8 Gen 3 构建；
   - 确保支持 GGUF 模型加载与 `Q4_K_M` 量化格式。
2. 将生成的 GGUF 文件传到设备，例如：
   - `outputs/models/exp1_qad_q4km.gguf`
   - 或通过 adb / scp 复制到手机存储。
3. 确认设备上 `llama.cpp` 调用命令行可以加载模型：
   ```bash
   ./main -m /path/to/exp1_qad_q4km.gguf -p "测试一句话"
   ```

### 12.3 推荐测试流程

1. 先做一次最小延迟验证：
   - `batch_size=1`
   - `threads=4` 或 `threads=6`（视 Snapdragon 8 Gen 3 CPU 核心而定）
2. 运行标准 prompt，验证模型能成功加载并给出合理输出。
3. 测量推理延迟：
   - 记录 p50/p90/p99 结果；
   - 重点观察首 token 和完整生成时间。
4. 若需要移动端定量性能对比，可参考仓库中 `exp14_gguf_comparison.py` 的逻辑，比较 `BF16` 与 `Q4_K_M` 在相同任务上的行为差异。

### 12.4 注意事项

- Snapdragon 8 Gen 3 上的移动部署应优先使用 `q4_k_m`，因为它兼顾精度与推理效率。
- 模型大小约为 `~240 MB`，请确认手机端存储空间和文件传输路径。
- 若出现加载失败，可先检查 GGUF 文件是否完整、是否为 `llama.cpp` 最新版本、以及是否支持 `Q4_K_M`。

---

## 13. 常见问题

**Q：如何确认图像脚本使用的是最新实验结果？**  
A：`paper_data.py` 加载 `outputs/results/exp*_*.json`（最新时间戳优先）和 `all_experiments.json`。运行 `python docs/figure_scripts/paper_data.py` 可查看当前加载状态。

**Q：how to skip archiving for CI/CD？**  
A：传入 `--no-archive` 参数，或在 CI 中设置 `REALEVAL_NO_ARCHIVE=1`（需在 runner.py 中实现此环境变量，目前请直接用 `--no-archive`）。

**Q：修改了实验脚本但图像没有更新？**  
A：图像脚本读取 `outputs/results/` 中的 JSON 文件，不是直接调用实验脚本。需先重新运行实验，再重新生成图像。

**Q：多次运行会积累很多 JSON 文件吗？**  
A：不会。每次运行前归档功能会清理旧文件，保留归档 Markdown。若手动运行 `--no-archive`，则需要自行清理或使用 `python scripts/archive_and_clear.py`。

---

## 14. TAF-28k 数据修复链（音频转录 → 特征 → 重跑）

> **背景**：TAF-28k 是**音频分类数据集**——其 `taf28k.jsonl` 中每条的 `text` 是同一段音频分析指令模板，真实的 fraud/normal 信号在音频文件里。若直接用该文本做分类，模型学不到任何区分（去重后仅 1 个唯一文本，结果坍缩为单类预测）。`whisper-tiny` 虽在模型清单中，但代码从未调用——这是数据引用逻辑缺口。

### 14.1 修复链路

```
音频（audio/*.mp3，13,711 条，48kHz/~60s）
   │ ① transcribe_taf28k.py（whisper 转录）
   ▼
taf28k.jsonl（13,388 条真实转写文本 + 标签，去重 13,333）
   │ ② build_taf28k_npz.py（whisper 编码器特征）
   ▼
taf28k.npz（13,388 × 384 声学嵌入 + labels + speaker_labels）
   │ ③ 重跑 exp5 / exp10 / exp13
   ▼
真实论文数值
```

### 14.2 脚本用法

```bash
# ① 转录音频 → 重建 taf28k.jsonl（text=whisper 转写, label=fraud/normal）
python data/scripts/transcribe_taf28k.py --limit 100   # 试跑
python data/scripts/transcribe_taf28k.py               # 全量（H100 约 55 分钟）
python data/scripts/transcribe_taf28k.py --resume      # 断点续传

# ② 生成声学特征 → taf28k.npz（exp13 融合的真实声学部分）
python data/scripts/build_taf28k_npz.py --limit 100
python data/scripts/build_taf28k_npz.py

# ③ 重跑受影响实验
python -m experiments.runner --exp 5,10,13 --paper --no-archive --config config/runpod_h100.yaml
```

### 14.3 关键事实

| 项 | 值 |
|----|----|
| 音频规模 | 13,711 个 mp3（48kHz，50-74 秒/条，共 ~12 GB） |
| 转录样本 | 13,388 条（fraud 7,177 / normal 6,211） |
| 去重文本数 | 13,333（修复前为 1） |
| 声学特征 | `taf28k.npz`（13,388 × 384，whisper 编码器 last_hidden_state 均值池化） |
| 修复效果 | exp10 教师规模从坍缩（0/0.667）变为真实 F1（0.56-0.92）；exp13 late_fusion 达 F1=0.928 |

### 14.4 RunPod 环境要点

- **持久化 venv**：`/workspace/venv`（`python3 -m venv --system-site-packages /workspace/venv`）。RunPod 容器重启会清空系统 pip 包，venv 装在持久卷 `/workspace` 上可避免重复安装。
- **运行命令**：`bash run_h100.sh`（已配置自动检测 `/workspace/venv/bin/python`）。
- **数据/模型位置**：`/workspace/data`、`/workspace/models`、`/workspace/hf_cache`（均为持久卷）。
