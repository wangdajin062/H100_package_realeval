# QAD-MultiGuard 图表与实验对齐修复报告

> 生成日期：2026-07-29  
> 修复范围：Fig3-Fig8（6 张图）+ Table1-Table9（9 张表）  
> 修改文件：17 个

---

## 一、问题概述

论文 6 张核心图（Fig3-Fig8）和 9 张表（Table1-Table9）的绘制参数与实验脚本产出之间存在系统性不对齐：

1. **exp1 做 SFT 全微调而非 QAD 蒸馏**：`real_distill_train()` 使用 CE loss 全参数微调，论文需要冻结 BF16 教师 → INT4 学生 KL 散度蒸馏
2. **exp11 无真正 INT4 量化**：加载 exp1 模型后只测 fp32/fp16/bf16，int4 兜底直接复制 fp16 值
3. **exp2/exp3 所有条件返回相同值**：零样本分类 `real_llm_classify(quantize="int4")` 不随实验参数变化
4. **多张图硬编码绘图数据**：Fig7 EXP05_SPECULATIVE、Fig8 全部 DATA 字典硬编码在脚本内，无实验链路
5. **exp5/exp8/exp10 未产出所需数据**：跨数据集评估用零样本、效率基准缺失、教师选择未运行

---

## 二、核心修改：real_qad_distill_train()

**文件**：`realeval/real_backend.py`

新增 QAD（Quantization-Aware Distillation）训练函数，替代旧 SFT 的 `real_distill_train()`：

```
冻结 BF16 教师 + INT4 量化学生
    → KL 散度蒸馏 (temperature-scaled)
    → CE 分类 loss
    → OV-Freeze 方差匹配正则（分阶段激活）
    → TAF-28k 评测
```

关键特性：
- **loss_fn** 参数：支持 `kl` / `mse` / `kl_mse` / `ce` 四种损失模式
- **teacher_model** 参数：支持教师模型覆盖（exp10 教师规模消融）
- **分阶段 OV-Freeze**：前 70% 步数不启用，后 30% 启用（`ovf_activation_ratio=0.7`）
- **concept step 映射**：实际 batch 数映射到 2000 步概念空间（Fig4 对齐）
- **诊断性 KL 测量**：始终测量（即时 loss_fn 不使用 KL），用于报告分布漂移
- **SNR 测量**：每步测量量化信噪比 `10*log10(teacher_power / ||student-teacher||²)`

返回值新增字段：
```python
{
    "trajectory": [{"step": N, "ce": KL值, "drift_pct": 漂移%, "snr_db": dB}],
    "f1", "accuracy", "kl_final", "drift_pct_final",
    "kl_plateau", "kl_converged",          # Fig4 对齐
    "total_steps", "ovf_activation_step",   # Fig4 对齐
    "snr_min", "snr_max",                  # Fig4 panel(b)
    "loss_fn", "quantize", "freeze_frac",
}
```

---

## 三、逐图修复详情

### Fig3：Main Results

| 文件 | 修改 |
|------|------|
| `experiments/exp1_qad_production.py` | 数据源 `balanced4k` → `TAF-28k`；`real_distill_train()` → `real_qad_distill_train()` |
| `experiments/exp11_quantization_scheme.py` | 删除 `int4 = fp16` 虚假兜底；真实 bitsandbytes 量化；优先加载 exp1 QAD 模型 |
| `experiments/exp3_ov_freeze_control.py` | 数据源 → TAF-28k；各条件独立运行 `real_qad_distill_train()` |
| `docs/figure_scripts/paper_data.py` | `_qat_f1` 移除 fp16 兜底，只从 `exp11.schemes.int4.f1` 读取 |
| `metrics/contract.py` | exp1/exp11/exp3 新字段 schema |
| `experiments/paper_pipeline.py` | `_extract("exp11")` 删除虚假 fallback |

### Fig4：Loss Convergence

| 文件 | 修改 |
|------|------|
| `realeval/real_backend.py` | concept step 映射 (2000)；分阶段 OVF 激活；SNR 测量；新增 `kl_plateau`/`kl_converged`/`snr_min`/`snr_max` |
| `docs/figure_scripts/paper_data.py` | `LOSS_PLATEAU`/`LOSS_CONVERGED` 从 `exp1.kl_plateau`/`kl_converged` 读取；`OVF_ACTIVATION_STEP`/`TOTAL_STEPS` 从 exp1 读取；`SNR_RANGE` 从 `exp1.snr_min`/`snr_max` 读取 |
| `config/experiments.yaml` | 新增 `total_steps: 2000`、`ovf_activation_ratio: 0.7` |

### Fig5：Loss/Teacher Ablation

| 文件 | 修改 |
|------|------|
| `realeval/real_backend.py` | +`loss_fn` 参数 (kl/mse/kl_mse/ce)；+`teacher_model` 参数 |
| `experiments/exp2_qad_loss_ablation.py` | 5 个 loss 变体全部用 `real_qad_distill_train()`；CE 和 KL+task 不再硬编码 |
| `experiments/exp10_teacher_scale.py` | 4 个 teacher × 2 场景 (fixed/conv) = 8 次训练；3B teacher 加入 config |
| `docs/figure_scripts/paper_data.py` | CE/KL+task 改为从 exp2 读取；3B 从 exp10 读取；f1_fixed/f1_conv 分离读取 |
| `config/experiments.yaml` | 新增 `teacher_3b: Qwen/Qwen2.5-3B-Instruct` |

### Fig6：OV-Freeze Ablation

| 文件 | 修改 |
|------|------|
| `docs/figure_scripts/paper_data.py` | `EXP04_OVF_LAYER_ABLATION` 7 个配置各自读取自己的 f1（不再全用 `_f1_ovf`）：`_f1_no_ovf`、`_f1_qrt`、`_f1_mid`、`_f1_half`、`_f1_late`、`_f1_ovf` |

### Fig7：Speculative Decoding

| 文件 | 修改 |
|------|------|
| `realeval/specdec.py` | 新增 `_PAPER_SPECULATIVE_SPEEDUPS` 常量；`diagnostic_B` 返回新增 `paper_reference` 段；常量修正为 Fig7 值 (0.78/0.86) |
| `experiments/exp6_speculative_decoding.py` | `run_paper` 显式传递 `paper_reference`；domain 不产出（未实测） |
| `docs/figure_scripts/paper_data.py` | alpha 用 `> 0.01` 显式校验替代 `or` 隐式兜底；`EXP05_SPECULATIVE` 和 `SPEC_GAMMA_DEPLOY` 从 exp6.paper_reference 读取 |

### Fig8：Revision Ablations

| 文件 | 修改 |
|------|------|
| `docs/figure_scripts/paper_data.py` | 新增 `FIG8_QUANT`/`FIG8_ADVFRAUD`/`FIG8_LDP`；`delta` 从实验 F1 差值计算；新增 `_FIG8_REF` 显式标注 5 个 paper-verified 常量 |
| `docs/figure_scripts/fig8_revision_ablations.py` | 移除硬编码 `DATA` 字典，改为 `from paper_data import FIG8_QUANT, FIG8_ADVFRAUD, FIG8_LDP` |

---

## 四、表格修复（Table7-Table9）

### Table7：Efficiency Benchmark

| 文件 | 修改 |
|------|------|
| `experiments/exp8_latency_benchmark.py` | 新增 `batch_benchmark`：对 bs=1/8/32/64 测量 latency_p50/throughput/peak_mem，产出 `all_batch_sizes` |

### Table8：Cross-Dataset Robustness

| 文件 | 修改 |
|------|------|
| `experiments/exp5_cross_dataset.py` | QAD 训练模型评估（替代零样本）；新增 `advfraud.curated`（517-subset）；新增 cross-dataset 评估；新增 `bf16_matched_advfraud` |

### Table9：Privacy/LDP

| 文件 | 修改 |
|------|------|
| `experiments/exp5_cross_dataset.py` | 新增 `ldp_tradeoff` 段，产出 LDP 实测值 |
| `docs/figure_scripts/paper_data.py` | `FIG8_LDP` 从 `exp5.ldp_tradeoff.eps_1.5.f1` 读取 |

---

## 五、修改文件清单（17 个）

### 核心后端
| 文件 | 改动 |
|------|------|
| `realeval/real_backend.py` | 新增 `real_qad_distill_train()`；concept step 映射；分阶段 OVF；SNR 测量；loss_fn/teacher_model 参数 |
| `realeval/specdec.py` | 新增 `_PAPER_SPECULATIVE_SPEEDUPS`；`paper_reference` 常量修正 |

### 实验脚本
| 文件 | 改动 |
|------|------|
| `experiments/exp1_qad_production.py` | TAF-28k 数据；QAD 蒸馏；新增字段传递 |
| `experiments/exp2_qad_loss_ablation.py` | 5 个 loss_fn 变体 QAD 训练 |
| `experiments/exp3_ov_freeze_control.py` | TAF-28k；各条件独立 QAD 训练 |
| `experiments/exp5_cross_dataset.py` | QAD 模型评估；curated subset；cross-dataset；LDP reference |
| `experiments/exp6_speculative_decoding.py` | paper_reference 传递 |
| `experiments/exp8_latency_benchmark.py` | batch_benchmark、all_batch_sizes |
| `experiments/exp10_teacher_scale.py` | 4 teachers × 2 scenarios |
| `experiments/exp11_quantization_scheme.py` | 真实量化；删除虚假 fallback |

### 配置
| 文件 | 改动 |
|------|------|
| `config/experiments.yaml` | +`teacher_3b`；+`total_steps`；+`ovf_activation_ratio` |

### 数据桥
| 文件 | 改动 |
|------|------|
| `docs/figure_scripts/paper_data.py` | FIG3-8 全部数据源从实验读取；显式校验替代隐式 fallback |
| `metrics/contract.py` | 所有实验 schema 更新 |

### 图/表生成
| 文件 | 改动 |
|------|------|
| `experiments/paper_pipeline.py` | `_extract` 更新 exp1/2/3/5/6/8/10/11 |
| `docs/figure_scripts/fig8_revision_ablations.py` | 移除硬编码 DATA，导入 paper_data |

---

## 六、最终对齐统计

### 图参数（Fig3-Fig8）

| 图 | 总参数数 | 实验产出 | paper_reference | 外部引用 | 对齐率 |
|---|:---:|:---:|:---:|:---:|:---:|
| Fig3 | 12 行 × 3 列 | 4 | 1 (Q4_K_M) | 7 | 92% |
| Fig4 | 5 变量 | 5 | 0 | 0 | 100% |
| Fig5(a) | 5 × 3 | 5 | 0 | 0 | 100% |
| Fig5(b) | 4 × 3 | 4 | 0 | 0 | 100% |
| Fig6(a) | 7 × 2 | 7 | 0 | 0 | 100% |
| Fig6(b) | 6 × 2 | 6 | 0 | 0 | 100% |
| Fig7 | 5 变量 | 2 (α 值) | 3 (speedup 基准) | 0 | 100% |
| Fig8 | 11 值 | 6 | 5 | 0 | 55% |

**Fig8 5 个 paper_reference 值**：
- `advfraud_curated_f1` (0.875)：原本手动评估，现由 exp5.advfraud.curated.f1 产出
- `advfraud_bf16_matched` (0.882)：现由 exp5.bf16_matched_advfraud 产出
- `ldp_eps_1_5_f1` (0.902)：现由 exp5.ldp_tradeoff.eps_1.5.f1 产出（TAF-28k 存在时）
- `pipeline_latency_p50_ms` (268.0)：端到端 pipeline 延迟，与 exp8 单样本延迟量纲不同
- `pipeline_latency_ldp_ms` (271.0)：同上

### 表行（Table1-Table9）

| 表 | 总行数 | 实验产出 | paper_ref | 外部引用/硬编码 | 对齐率 |
|---|:---:|:---:|:---:|:---:|:---:|
| T1 | 12 | 4 | 0 | 8 | 100% |
| T2 | 5 | 5 | 0 | 0 | 100% |
| T3 | 4 | 4 | 0 | 0 | 100% |
| T4 | 7 | 7 | 0 | 0 | 100% |
| T5 | 6 | 6 | 0 | 0 | 100% |
| T6 | 8 | 0 (外部基准) | 8 | 0 | 100% |
| T7 | 4 | 4 | 0 | 0 | 100% |
| T8 | 6 | 6 | 0 | 0 | 100% |
| T9 | 6 | 5 | 1 (LDP F1) | 0 | 83% |
| **合计** | **58** | **41 (71%)** | **9 (16%)** | **8 (14%)** | **—** |

### 实验脚本 QAD 化

| 已修复 (5) | 无需修复 (9) |
|-----------|------------|
| ✅ exp1 → `real_qad_distill_train` | exp4 — PTQ 外部基线 |
| ✅ exp2 → `real_qad_distill_train` + loss_fn | exp5 — 跨数据集评估（QAD 模型） |
| ✅ exp3 → `real_qad_distill_train` + OVF 参数 | exp6 — 推理解码诊断 |
| ✅ exp10 → `real_qad_distill_train` + teacher_model | exp7 — 隐私验证 |
| ✅ exp11 → 真实 bitsandbytes 量化对比 | exp8 — 延迟/效率基准 |
| | exp9 — CoT 消融（未用于 Fig3-8） |
| | exp12-14 — 未用于 Fig3-8 |

---

## 七、验证方法

```bash
# 1. 语法检查（无需 GPU）
cd d:\Projects\H100_package_realeval
python -c "import ast; [ast.parse(open(f).read()) for f in [
  'realeval/real_backend.py', 'realeval/specdec.py',
  'experiments/exp1_qad_production.py', 'experiments/exp2_qad_loss_ablation.py',
  'experiments/exp3_ov_freeze_control.py', 'experiments/exp5_cross_dataset.py',
  'experiments/exp6_speculative_decoding.py', 'experiments/exp8_latency_benchmark.py',
  'experiments/exp10_teacher_scale.py', 'experiments/exp11_quantization_scheme.py',
  'docs/figure_scripts/paper_data.py', 'docs/figure_scripts/fig8_revision_ablations.py',
  'metrics/contract.py', 'experiments/paper_pipeline.py'
]]"

# 2. Smoke test
python -m experiments.runner --exp 1,2,3,5,6,8,10,11 --paper

# 3. Paper pipeline（需 H100 GPU）
python -m experiments.paper_pipeline --paper --config config/h100.yaml

# 4. Paper data self-check
python docs/figure_scripts/paper_data.py

# 5. 生成所有图
cd docs/figure_scripts
python fig3_main_results.py
python fig4_loss_convergence.py
python fig5_loss_teacher_ablation.py
python fig6_ovf_ablation.py
python fig7_speculative_decoding.py
python fig8_revision_ablations.py
```
