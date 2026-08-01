# QAD-MultiGuard — H100 RealEval Suite

> **最后更新：2026-07-31**
> 包版本：**4.3.0** · Python ≥ 3.10 · 验证平台：NVIDIA H100 SXM5 80 GB HBM3

面向 **QAD-MultiGuard** 论文的真实计算评测套件。
全部 14 个实验在真实 Qwen 权重 + H100 上产出论文级数值；
**smoke 模式**可在任意 CPU-only 机器上快速验证完整代码路径，无需 GPU 或模型权重。

---

## 重构亮点（v4.3）

| 特性                     | 说明                                                                               |
| ------------------------ | ---------------------------------------------------------------------------------- |
| **自动归档**       | 每次重跑前，旧实验结果自动保存为带时间戳的 Markdown 并清空输出目录                 |
| **全量归并输出**   | 所有实验完成后写入`all_experiments.json`，作为 `paper_data.py` 的候补来源      |
| **字段完全对齐**   | 实验脚本产出字段与图像脚本期望字段一一对齐（详见合约文档）                         |
| **exp10 补全**     | smoke 路径新增`teacher_3b` 键，与 Fig 5(b) 对齐                                  |
| **配置 Python 包** | `config/__init__.py` 提供 `get_config()`、`load_config()`、`CONFIG_SCHEMA` |
| **类型注解**       | `framework.py`、`io.py`、`runner.py` 关键函数全面完善类型注解                |
| **中文日志**       | 所有运行时日志、CLI 帮助均改为中文                                                 |

---

## 架构总览

```
H100_package_realeval/
│
├── config/                    # 统一配置管理
│   ├── __init__.py            # Python 包：get_config() · load_config() · CONFIG_SCHEMA
│   ├── experiments.yaml       # 基础配置（models / data / training / distillation）
│   ├── h100.yaml              # H100 硬件覆盖层（BF16 · FlashAttn · DDP）
│   └── runpod_h100.yaml       # RunPod 云 GPU 覆盖层
│
├── realeval/                  # 核心库（v4.3）
│   ├── io.py                  # 配置加载 + 结果保存（含 save_all_results）
│   ├── data.py                # 数据集加载：TAF-28k · ChiFraud · AdvFraud-3k
│   ├── real_backend.py        # H100 推理路径：蒸馏 · 分类 · 融合
│   ├── models.py              # Qwen 加载 + 量化（BF16/FP16/INT4/INT8/NF4）
│   ├── specdec.py             # 推测解码接受率诊断
│   ├── privacy.py             # ASV-EER · GLO attack · 高斯 LDP
│   ├── metrics.py             # F1 · 准确率 · FPR · KL
│   ├── benchmark.py           # 前向延迟 / 吞吐量 / GPU 功耗
│   ├── runlog.py              # 溯源记录（git SHA · config hash · seed）
│   └── ...（其他模块）
│
├── experiments/               # 14 个论文实验 + 编排层
│   ├── framework.py           # 共享运行时（模式分发 · 数据回退 · schema 检查）
│   ├── runner.py              # CLI 编排器（--smoke/--paper/--exp/--report/--no-archive）
│   ├── paper_pipeline.py      # 一键式 H100 流水线（含自动归档 + 全量写入）
│   ├── contract.py            # 图像脚本字段合约验证器
│   ├── exp1_qad_production.py     # QAD 蒸馏（KL 教师→学生 + OV-Freeze）
│   ├── exp2_qad_loss_ablation.py  # Loss 消融：pure-KL / MSE / 3-term 混合
│   ├── exp3_ov_freeze_control.py  # OV-Freeze：层选择 · ρ 扫描 · 条件控制
│   ├── exp4_baseline_comparison.py# 经典基线：LogReg · XGBoost · MLP
│   ├── exp5_cross_dataset.py      # 跨数据集：TAF-28k · ChiFraud · AdvFraud-3k · LDP
│   ├── exp6_speculative_decoding.py # 推测解码 α 诊断（Table 8）
│   ├── exp7_privacy_verification.py # 隐私验证：ASV-EER · GLO attack
│   ├── exp8_latency_benchmark.py  # 延迟基准：端到端墙钟时间
│   ├── exp9_cot_ablation.py       # CoT 消融：思维链 vs 直接输出
│   ├── exp10_teacher_scale.py     # 教师规模：0.5B/1.5B/3B/7B（含 teacher_3b）
│   ├── exp11_quantization_scheme.py # 量化方案：FP16/INT8/INT4/NF4
│   ├── exp12_fraudfusion_baseline.py # FraudFusion 竞品基线
│   ├── exp13_fusion_strategy.py   # 多模态融合策略消融
│   └── exp14_gguf_comparison.py   # BF16 vs Q4_K_M GGUF 对比
│
├── docs/
│   ├── figure_scripts/        # 论文图像脚本（只读，不允许修改）
│   │   ├── paper_data.py      # 实验结果 ↔ 图像脚本桥接层
│   │   ├── fig3_main_results.py
│   │   ├── fig4_loss_convergence.py
│   │   ├── fig5_loss_teacher_ablation.py
│   │   ├── fig6_ovf_ablation.py
│   │   ├── fig7_speculative_decoding.py
│   │   ├── fig8_revision_ablations.py
│   │   └── generate_all.py
│   ├── figure/                # 生成的图像（PNG · PDF · TIFF，400 DPI）
│   ├── experiment_result_contract.md  # 字段对齐映射（权威文档）
│   └── REPRODUCIBILITY.md     # 完整复现路径指南
│
├── scripts/
│   └── archive_and_clear.py   # 归档旧结果 → Markdown，清理输出目录
│
├── outputs/
│   ├── results/               # 实验结果 JSON + all_experiments.json
│   ├── archive/               # 带时间戳的归档快照
│   └── logs/                  # experiments.log · runlog.jsonl
│
└── config/experiments.yaml    # 统一配置入口
```

---

## 快速开始

### 1. smoke 验证（无 GPU）

```bash
# 全量 smoke 运行（自动归档旧结果 → 运行 → 写入 all_experiments.json）
python -m experiments.runner --smoke

# 验证字段合约
python -m experiments.runner --validate-contract

# 生成全部论文图表
cd docs/figure_scripts && python generate_all.py
```

### 2. 论文级运行（H100）

```bash
# 一键运行（推荐）
bash run_h100.sh

# 手动运行
python -m experiments.paper_pipeline --paper --config config/h100.yaml

# 运行指定实验
python -m experiments.runner --paper --exp 1,3,6 --config config/h100.yaml
```

### 3. 查看归档历史

```bash
ls outputs/archive/
# 2026-07-31_120000_experiment_results.md
# 2026-07-30_090000_experiment_results.md
```

---

## 数据流

```
实验脚本（exp1–exp14）
    ↓ save_results()
outputs/results/expN_{timestamp}.json
    ↓ save_all_results()
outputs/results/all_experiments.json
    ↓ paper_data.py（桥接，只读）
        ↓
docs/figure_scripts/fig{N}.py
    ↓
docs/figure/fig{N}.png/.pdf/.tiff
```

**图像脚本不可修改**。若需调整论文数值，请修改实验脚本使其产出正确字段。

---

## 归档工作流

```
每次 --paper / --smoke 运行时：

旧 outputs/results/ ──→ outputs/archive/{ts}_experiment_results.md
                    ↓（清空）
新实验运行 ──→ outputs/results/expN_{ts}.json
           ──→ outputs/results/all_experiments.json
```

跳过归档：`python -m experiments.runner --smoke --no-archive`

---

## CLI 速查

| 命令                    | 说明                                 |
| ----------------------- | ------------------------------------ |
| `--smoke`             | smoke 验证路径（CPU，无需 GPU/权重） |
| `--paper`             | 论文级运行（需 H100 + Qwen 权重）    |
| `--exp 1,3,6`         | 仅运行指定实验                       |
| `--config path.yaml`  | 指定配置文件                         |
| `--resume`            | 跳过已完成的实验                     |
| `--no-archive`        | 跳过运行前归档                       |
| `--validate-contract` | 验证字段合约                         |
| `--report`            | 从已有结果生成表格/图像              |
| `--check`             | 硬件检查                             |

---

## 复现指南

详见 [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md)。

---

## 字段合约

详见 [`docs/experiment_result_contract.md`](docs/experiment_result_contract.md)。

---

## 许可证

见 [LICENSE](LICENSE)。
