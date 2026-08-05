# QAD-MultiGuard RealEval — H100 真实评测套件

> Python ≥ 3.10 · 验证平台：NVIDIA H100 SXM5 80 GB HBM3 + RunPod 云 GPU

本仓库是 **QAD-MultiGuard** 论文的配套真实评测套件：在真实 Qwen 权重 + H100 上运行 14 个实验，
产出论文数值，并将结果与论文声称逐项对照。所有实验均为真实计算，不含合成数据结果。

---

## 1. 包目标

| 目标 | 说明 |
|------|------|
| **真实计算** | 全部实验在真实 Qwen2.5 权重 + H100 上运行，结果写入带时间戳 JSON |
| **可复现** | 运行前自动归档旧结果，并记录 git SHA、配置 hash、seed |
| **诚实标注** | 论文声称与实测差异在结果文件中显式标注，不掩盖、不合并 |
| **双运行路径** | `smoke`（CPU 验证代码路径）与 `paper`（H100 真实数值）严格区分 |
| **字段对齐** | 实验输出字段与论文图像脚本字段一一对应（契约见 `docs/experiment_result_contract.md`） |

## 2. 任务

本套件评测 **QAD-MultiGuard**——面向金融欺诈防御的多模态（文本 / 语音）安全系统：

- **判别任务**：中文金融欺诈二分类（ChiFraud 404k 主数据集，保持 ~14.3% 自然欺诈比例）
- **同源自蒸馏（QAD）**：BF16 教师（Qwen2.5-0.5B-Instruct）监督同架构低比特量化学生，配合 OV-Freeze 输出方差冻结正则
- **多模态融合**：文本嵌入 + 语音特征（whisper 编码器）的 early / late / hybrid 融合（TAF-28k 转录 13,388 条）
- **边缘部署形态**：0.5B Q4_K_M GGUF（~240 MB）学生模型

### 2.1 14 个实验一览

| 实验 | 模块 | 内容 | 关键数值 |
|---|---|---|---|
| exp1 | `exp1_qad_production.py` | QAD 生产蒸馏（KL + OV-Freeze） | F1 0.4256（int4） |
| exp2 | `exp2_qad_loss_ablation.py` | 损失消融：KL / MSE / CE / 混合 | mse_only 0.7911 |
| exp3 | `exp3_ov_freeze_control.py` | OV-Freeze：层选择 · ρ 扫描 · 条件控制 | ov_freeze_full 0.688 |
| exp4 | `exp4_baseline_comparison.py` | 经典基线：LogReg / XGBoost / MLP | MLP 0.9488 |
| exp5 | `exp5_cross_dataset.py` | 跨数据集：TAF-28k / ChiFraud / AdvFraud-3k / LDP | bf16_matched 0.882 |
| exp6 | `exp6_speculative_decoding.py` | 投机解码 α 诊断 | generic α 0.468（与论文参照 0.78 有差异，已标注） |
| exp7 | `exp7_privacy_verification.py` | 隐私：ASV-EER / GLO 攻击 / PII | EER 43.2%，重建相关 0.3001 |
| exp8 | `exp8_latency_benchmark.py` | 延迟基准（p50/p90/p99 + 吞吐） | int4 p50 46.47ms |
| exp9 | `exp9_cot_ablation.py` | 思维链消融 | 无 CoT 0.2892 vs 有 CoT 0.2288 |
| exp10 | `exp10_teacher_scale.py` | 教师规模：0.5B/1.5B/3B/7B | 0.5B 教师最优 0.8963 |
| exp11 | `exp11_quantization_scheme.py` | 量化方案：fp16/int8/int4/nf4 | int4 0.4287 最优 |
| exp12 | `exp12_fraudfusion_baseline.py` | FraudFusion 竞品基线 + 存储分解 | QAD_INT4 0.6965；总优势 30.8× |
| exp13 | `exp13_fusion_strategy.py` | 融合策略消融 | late_fusion 0.9275 最优 |
| exp14 | `exp14_gguf_comparison.py` | BF16 transformers vs Q4_K_M llama.cpp | q4km 0.7025 vs bf16 0.5853 |

数值源文件：`outputs/results/expN_{timestamp}.json` 与 `outputs/results/all_experiments.json`。

## 3. 实验流程

```
bash run_h100.sh（或 python -m experiments.runner --paper）
   │
   ├─ 1. 归档旧结果        outputs/results/ → outputs/archive/{ts}_experiment_results.md
   ├─ 2. CUDA / GPU / 环境检查（含显存 ≥35GB 预检、模型资产检查）
   ├─ 3. 配置加载          config/experiments.yaml → h100.yaml / runpod_h100.yaml 覆盖层
   ├─ 4. 运行实验分组      00_train → 01_baseline → 02_quantization → 03_QAD
   │                       → 04_OV-Freeze → 05_latency → 06_robustness
   ├─ 5. 设备基准          H100 延迟 / 吞吐 / 显存（batch 1/8/32）
   ├─ 6. 归并输出          outputs/results/all_experiments.json + expN_{ts}.json
   ├─ 7. 生成交付物        metrics.json · latency.csv · throughput.csv · memory.csv
   │                       · paper_table.md · paper_tables/*.tex
   │
   ▼ 后处理（可选）
python -m experiments.runner --report               # 从已有结果生成论文表格/图像
python -m experiments.runner --validate-contract    # 校验字段合约
cd docs/figure_scripts && python generate_all.py    # 论文图像（只读脚本）
```

### 3.1 运行模式

| 模式 | 命令 | 用途 |
|------|------|------|
| **smoke** | `python -m experiments.runner --smoke` | 任意 CPU 机器验证完整代码路径，无需 GPU/权重 |
| **paper** | `bash run_h100.sh` 或 `python -m experiments.paper_pipeline --paper` | H100 + 真实 Qwen，产出论文数值 |

其他 CLI：`--exp 1,3,6`（指定实验）、`--resume`（跳过已完成）、`--no-archive`、`--check`（硬件检查）、`--report`（从已有结果生成表格/图像）。

### 3.2 RunPod 部署先决条件

| 项 | 要求 |
|---|---|
| **GPU** | NVIDIA H100 SXM 80GB（单卡；`--distributed` 需 ≥1 卡） |
| **依赖** | `accelerate`（量化/`device_map` 必需；缺失时 `models.py` 自动回退 CPU/设备转移） |
| **LoRA adapters** | 训练产物置于 `REALEVAL_ADAPTER_ROOT`（默认 `/workspace/outputs/sft_checkpoints`；本地可用该环境变量覆盖） |
| **数据** | `/workspace/data`（TAF-28k/ChiFraud/AdvFraud-3k 等，持久卷） |
| **模型** | `/workspace/models` + HF 缓存 `/workspace/hf_cache` |
| **Python** | 持久 venv `/workspace/venv`（`--system-site-packages` 复用 torch 2.8） |
| **exp2 多 seed** | `config/runpod_h100.yaml` 的 `reproducibility.exp2_seeds: 5`（论文声称 5） |

> ⚠️ **`run_h100.sh` 清理行为**：该脚本用于全量论文级流水线。**默认不再自动清空** `outputs/results|metrics|predictions`；需显式加 `--clean` 才清空（或先 `scripts/archive_and_clear.py` 归档）。
> **重跑单个实验**请用 `python -m experiments.runner --no-archive --config config/runpod_h100.yaml --exp N`（避免误清全部结果）。

## 4. 代码结构

```
├── realeval/                  # 核心库
│   ├── real_backend.py        #   H100 推理路径：蒸馏 · 分类 · 融合
│   ├── models.py              #   Qwen 加载 + 量化（BF16/FP16/INT4/INT8/NF4）
│   ├── data.py                #   数据集：TAF-28k · ChiFraud · AdvFraud-3k
│   ├── specdec.py / privacy.py / metrics.py / benchmark.py
│   ├── runlog.py              #   溯源：git SHA · config hash · seed
│   └── io/                    #   IO 子包（序列化 · 路径 · 归档）
│       ├── paths.py
│       ├── serialization.py
│       └── archive.py
├── experiments/               # 14 个实验（§2.1）+ 兼容层
│   ├── framework.py           #   模式分发 · 数据回退 · 防泄漏分割
│   ├── runner.py              #   CLI 包装器
│   ├── paper_pipeline.py      #   一键 H100 流水线
│   ├── common.py              #   公共训练/评估 helper
│   ├── alignment.py           #   兼容 re-export
│   ├── contract.py            #   兼容 re-export
│   └── exp*_*.py              #   各实验实现
├── config/                    # 统一配置管理
│   ├── __init__.py            #   暴露 load_config / validate_config
│   ├── defaults.py            #   默认配置
│   ├── loader.py              #   加载 / 合并 / 环境变量覆盖
│   └── schema.py              #   schema 与校验
├── runner/                    # 实验编排
│   ├── registry.py            #   14 个实验注册表
│   ├── experiment_runner.py   #   单实验运行封装
│   └── orchestrator.py        #   多实验调度 + 归档 + 归并
├── metrics/                   # 指标计算与字段合约
│   ├── contract.py            #   图像脚本字段合约
│   ├── extraction.py          #   headline 指标提取
│   └── aggregation.py         #   多 seed 聚合
├── cli/                       # 命令入口
│   └── parser.py              #   统一 argparse
├── utils/                     # 通用工具
│   ├── logging.py             #   统一日志工厂
│   ├── exceptions.py          #   结构化异常
│   └── typing.py              #   公共类型别名
├── data/scripts/              # TAF-28k 数据链：下载 · 转录 · 特征构建
├── docs/figure_scripts/       # 论文图像脚本（只读）
├── docs/REFACTORING.md        # 重构说明
├── docs/experiment_result_contract.md  # 字段对齐契约
├── claims/ + audit/           # 论文声称 + 证据图谱
├── reports/                   # 实验结果报告
└── outputs/                   # results / archive / logs / metrics / figures
```

## 5. 快速开始

```bash
# 1) smoke 验证（无 GPU，验证代码路径）
python -m experiments.runner --smoke

# 2) 论文级运行（H100 + 真实 Qwen）
bash run_h100.sh

# 3) 仅跑指定实验
python -m experiments.runner --paper --exp 1,11 --config config/runpod_h100.yaml

# 4) 生成报告与论文图像
python -m experiments.runner --report
cd docs/figure_scripts && python generate_all.py
```

## 6. 手机端 Snapdragon 8 Gen 3 实测流程

本项目的边缘部署目标是生成 **0.5B Q4_K_M GGUF**，用于 Snapdragon 8 Gen 3 或其他 `llama.cpp` 兼容移动平台。

### 6.1 导出 GGUF

1. 训练完成后，使用导出脚本生成 GGUF：
   ```bash
   python scripts/export_to_gguf.py --source outputs/models/exp1_qad --output outputs/models/exp1_qad_q4km.gguf
   ```
2. 导出默认量化类型为 `q4_k_m`，这是 Snapdragon 8 Gen 3 上最推荐的 GGUF 格式。
3. 如果目标机上仍需测试 `q4_0` / `q4_1`，可通过 `--quant-type q4_0` 或 `--quant-type q4_1` 指定。

### 6.2 手机端测试准备

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

### 6.3 推荐测试流程

1. 先做一次最小延迟验证：
   - `batch_size=1`
   - `threads=4` 或 `threads=6`（视 Snapdragon 8 Gen 3 CPU 核心而定）
2. 运行标准 prompt，验证模型能成功加载并给出合理输出。
3. 测量推理延迟：
   - 记录 p50/p90/p99 结果；
   - 重点观察首 token 和完整生成时间。
4. 若需要移动端定量性能对比，可参考仓库中 `exp14_gguf_comparison.py` 的逻辑，比较 `BF16` 与 `Q4_K_M` 在相同任务上的行为差异。

### 6.4 注意事项

- Snapdragon 8 Gen 3 上的移动部署应优先使用 `q4_k_m`，因为它兼顾精度与推理效率。
- 模型大小约为 `~240 MB`，请确认手机端存储空间和文件传输路径。
- 若出现加载失败，可先检查 GGUF 文件是否完整、是否为 `llama.cpp` 最新版本、以及是否支持 `Q4_K_M`。

## 7. 相关文档

- [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md) — 完整复现路径
- [`docs/experiment_result_contract.md`](docs/experiment_result_contract.md) — 字段对齐契约
- [`reports/2026-08-01_experiment_results.md`](reports/2026-08-01_experiment_results.md) — 实验数值结果

## 8. 许可证

见 [LICENSE](LICENSE)。
