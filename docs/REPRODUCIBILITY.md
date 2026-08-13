# QAD-MultiGuard 复现指南

本文档是完整实验复现路径的权威参考，涵盖环境配置、实验运行、图表生成、归档工作流与参数字典。

---

## 目录

1. [环境配置](#1-环境配置)
3. [论文级复现（paper）](#3-论文级复现paper)
4. [生成论文图表](#4-生成论文图表)
5. [归档与清理工作流](#5-归档与清理工作流)
6. [CLI 命令参考](#6-cli-命令参考)
7. [配置参数字典](#7-配置参数字典)
8. [字段对齐说明](#8-字段对齐说明)
9. [手机端 Snapdragon 8 Gen 3 实测流程](#9-手机端-snapdragon-8-gen-3-实测流程)
10. [常见问题](#10-常见问题)
11. [TAF-28k 数据修复链（音频转录 → 特征 → 重跑）](#11-taf-28k-数据修复链音频转录--特征--重跑)

---

## 1. 环境配置

### 依赖安装

```bash
# 克隆仓库
git clone https://github.com/wangdajin062/H100_package_realeval.git
cd H100_package_realeval

# 安装 Python 依赖（可编辑模式）
pip install -e .
# 或
pip install -r requirements.txt
```

### 运行环境

| 项目 | 要求 |
|------|------|
| Python | ≥ 3.10 |
| PyTorch | ≥ 2.1 |
| CUDA | 12.x（论文级运行需要 H100 SXM5 80GB） |
| 磁盘 | ≥ 100 GB（模型权重 + 数据集） |

### 配置文件说明

```
config/
  experiments.yaml    # 基础配置（models、data、training、distillation 等）
  h100.yaml           # H100 硬件覆盖层（BF16、FlashAttention-2、DDP）
  runpod_h100.yaml    # RunPod 云 GPU 覆盖层
```

配置加载顺序：`experiments.yaml` → 覆盖层（如 `h100.yaml`）→ 环境变量（`REALEVAL_*`）

---

## 3. 论文级复现（paper）

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

## 4. 生成论文图表

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

## 5. 归档与清理工作流

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

## 6. CLI 命令参考

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

## 7. 配置参数字典

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

## 8. 字段对齐说明

详见 `docs/experiment_result_contract.md`。

**核心原则**：
- 图像脚本通过 `paper_data.py` 的 `_get(exp_id, *keys)` 读取实验结果
- 所有字段均配有论文常量作为回退值，保证图像脚本始终可运行
- 实验脚本只走 paper 路径（真实 H100 结果），字段结构完全一致

---

## 9. 手机端 Snapdragon 8 Gen 3 实测流程

本项目的边缘部署目标是生成 **0.5B Q4_K_M GGUF**，用于 Snapdragon 8 Gen 3 或其他 `llama.cpp` 兼容移动平台。

### 9.1 导出 GGUF

1. 训练完成后，使用导出脚本生成 GGUF：
   ```bash
   python scripts/export_to_gguf.py --source outputs/models/exp1_qad --output outputs/models/exp1_qad_q4km.gguf
   ```
2. 导出默认量化类型为 `q4_k_m`，这是 Snapdragon 8 Gen 3 上最推荐的 GGUF 格式。
3. 如果目标机上仍需测试 `q4_0` / `q4_1`，可通过 `--quant-type q4_0` 或 `--quant-type q4_1` 指定。

### 9.2 手机端测试准备

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

### 9.3 推荐测试流程

1. 先做一次最小延迟验证：
   - `batch_size=1`
   - `threads=4` 或 `threads=6`（视 Snapdragon 8 Gen 3 CPU 核心而定）
2. 运行标准 prompt，验证模型能成功加载并给出合理输出。
3. 测量推理延迟：
   - 记录 p50/p90/p99 结果；
   - 重点观察首 token 和完整生成时间。
4. 若需要移动端定量性能对比，可参考仓库中 `exp14_gguf_comparison.py` 的逻辑，比较 `BF16` 与 `Q4_K_M` 在相同任务上的行为差异。

### 9.4 注意事项

- Snapdragon 8 Gen 3 上的移动部署应优先使用 `q4_k_m`，因为它兼顾精度与推理效率。
- 模型大小约为 `~240 MB`，请确认手机端存储空间和文件传输路径。
- 若出现加载失败，可先检查 GGUF 文件是否完整、是否为 `llama.cpp` 最新版本、以及是否支持 `Q4_K_M`。

---

## 10. 常见问题

**Q：如何确认图像脚本使用的是最新实验结果？**  
A：`paper_data.py` 加载 `outputs/results/exp*_*.json`（最新时间戳优先）和 `all_experiments.json`。运行 `python docs/figure_scripts/paper_data.py` 可查看当前加载状态。

**Q：how to skip archiving for CI/CD？**  
A：传入 `--no-archive` 参数，或在 CI 中设置 `REALEVAL_NO_ARCHIVE=1`（需在 runner.py 中实现此环境变量，目前请直接用 `--no-archive`）。

**Q：修改了实验脚本但图像没有更新？**  
A：图像脚本读取 `outputs/results/` 中的 JSON 文件，不是直接调用实验脚本。需先重新运行实验，再重新生成图像。

**Q：多次运行会积累很多 JSON 文件吗？**  
A：不会。每次运行前归档功能会清理旧文件，保留归档 Markdown。若手动运行 `--no-archive`，则需要自行清理或使用 `python scripts/archive_and_clear.py`。

---

## 10. TAF-28k 数据修复链（音频转录 → 特征 → 重跑）

> **背景**：TAF-28k 是**音频分类数据集**——其 `taf28k.jsonl` 中每条的 `text` 是同一段音频分析指令模板，真实的 fraud/normal 信号在音频文件里。若直接用该文本做分类，模型学不到任何区分（去重后仅 1 个唯一文本，结果坍缩为单类预测）。`whisper-tiny` 虽在模型清单中，但代码从未调用——这是数据引用逻辑缺口。

### 10.1 修复链路

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

### 10.2 脚本用法

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

### 10.3 关键事实

| 项 | 值 |
|----|----|
| 音频规模 | 13,711 个 mp3（48kHz，50-74 秒/条，共 ~12 GB） |
| 转录样本 | 13,388 条（fraud 7,177 / normal 6,211） |
| 去重文本数 | 13,333（修复前为 1） |
| 声学特征 | `taf28k.npz`（13,388 × 384，whisper 编码器 last_hidden_state 均值池化） |
| 修复效果 | exp10 教师规模从坍缩（0/0.667）变为真实 F1（0.56-0.92）；exp13 late_fusion 达 F1=0.928 |

### 10.4 RunPod 环境要点

- **持久化 venv**：`/workspace/venv`（`python3 -m venv --system-site-packages /workspace/venv`）。RunPod 容器重启会清空系统 pip 包，venv 装在持久卷 `/workspace` 上可避免重复安装。
- **运行命令**：`bash run_h100.sh`（已配置自动检测 `/workspace/venv/bin/python`）。
- **数据/模型位置**：`/workspace/data`、`/workspace/models`、`/workspace/hf_cache`（均为持久卷）。
