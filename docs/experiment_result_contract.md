# 实验产出 → 论文图像脚本 字段对齐映射

> 本文档定义 `docs/figure_scripts/paper_data.py` 所需字段与实验脚本产出字段的完整对齐关系。
> **硬性约束：`docs/figure_scripts/` 下所有文件不可修改，实验侧须主动适配。**

## 一、映射总表

### Figure 3 → Main Results (F1 + Recovery)
| 图脚本变量 | paper_data 读取路径 | 实验产出字段 | 类型 | 备注 |
|-----------|-------------------|------------|------|------|
| EXP01_QUANT_QUALITY | exp1.f1, exp1.std | exp1 → f1, std | float×2 | QAD F1 |
| QAT_QAD_OVF | exp11.schemes.int4.f1, .std | exp11 → schemes.int4.f1, .std | float×2 | QAT baseline |
| BF16_F1 | exp11.schemes.bf16.f1 | exp11 → schemes.bf16.f1 | float | BF16 ceiling |

### Figure 4 → Loss Convergence
| 图脚本变量 | paper_data 读取路径 | 实验产出字段 | 类型 |
|-----------|-------------------|------------|------|
| LOSS_PLATEAU | exp1.kl_plateau | exp1 → kl_plateau | float |
| LOSS_CONVERGED | exp1.kl_converged | exp1 → kl_converged | float |
| OVF_ACTIVATION_STEP | exp1.ovf_activation_step | exp1 → ovf_activation_step | int |
| TOTAL_STEPS | exp1.total_steps | exp1 → total_steps | int |
| SNR_RANGE | exp1.snr_min, exp1.snr_max | exp1 → snr_min, snr_max | float×2 |

### Figure 5 → Loss & Teacher Ablation
| 图脚本变量 | paper_data 读取路径 | 实验产出字段 |
|-----------|-------------------|------------|
| EXP03_LOSS_ABLATION | exp2.variants.{kl,mse,ce,kl_mse}_only.{f1,kl_final,std} | exp2 → variants.{name}.{f1,kl_final,std} |
| EXP09_TEACHER | exp10.scales.{teacher,teacher_1.5b,3b,7b}.{f1_fixed,f1_conv} | exp10 → scales.{key}.{f1_fixed,f1_conv} |

### Figure 6 → OV-Freeze Ablation
| 图脚本变量 | paper_data 读取路径 | 实验产出字段 |
|-----------|-------------------|------------|
| EXP04_OVF_LAYER_ABLATION | exp3.layer_selection.{early,mid,late,all}.{f1,variance_drift_pct} | exp3 → layer_selection.{name}.{f1,variance_drift_pct} |
| EXP10_OVF_STEP_RATIO | exp3.rho_sweep.rho_{0.0..0.5}.{f1,ppl} | exp3 → rho_sweep.{key}.{f1,ppl} |

### Figure 7 → Speculative Decoding
| 图脚本变量 | paper_data 读取路径 | 实验产出字段 |
|-----------|-------------------|------------|
| EXP05_SPECULATIVE | exp6.diagnostic_B.h100_measured.generic | exp6 → diagnostic_B.h100_measured.generic |
| SPEC_ALPHA_GENERIC | exp6.paper_reference.alpha_generic | exp6 → paper_reference.alpha_generic (cited) |
| SPEC_ALPHA_TUNED | exp6.paper_reference.alpha_tuned | exp6 → paper_reference.alpha_tuned (cited) |
| SPEC_GAMMA_DEPLOY | exp6.paper_reference.gamma_deploy | exp6 → paper_reference.gamma_deploy (cited) |

### Figure 8 → Revision Ablations
| 图脚本变量 | paper_data 读取路径 | 实验产出字段 |
|-----------|-------------------|------------|
| FIG8_QUANT | exp11.schemes.{int4,nf4}.f1 + exp11.schemes.bf16.f1 | exp11 → schemes.{int4,nf4,bf16}.f1 |
| FIG8_ADVFRAUD | exp5.advfraud.{full_pool,curated}.f1 + exp5.bf16_matched_advfraud | exp5 → advfraud.{full_pool,curated}.f1 + bf16_matched_advfraud |
| FIG8_LDP | exp5.ldp_tradeoff.eps_1.5.f1 | exp5 → ldp_tradeoff.eps_1.5.f1 |

## 二、结果文件格式与命名规范

| 类型 | 路径 | 命名格式 | 说明 |
|------|------|---------|------|
| 单次实验结果 | `outputs/results/` | `exp{N}_{YYYYMMDD_HHMMSS}.json` | 时间戳确保可追溯 |
| 全量归并 | `outputs/results/all_experiments.json` | 固定名 | paper_data.py 候补来源 |
| 归档快照 | `outputs/archive/` | `{YYYY-MM-DD_HHMMSS}_experiment_results.md` | 旧结果自动归档 |
| 模型产物 | `outputs/models/exp1_qad/` | 固定名 | head.pt 包含 threshold |

### JSON Schema（每个实验结果文件）
```json
{
  "experiment": "exp1",           // str: 实验短ID（必填）
  "computation": "h100_real_qwen", // str: 运行路径标记（必填）
  // ... 实验特定字段（见映射表）
}
```

## 三、旧字段兼容策略

1. **`paper_data.py` 加载逻辑**：先按时间戳加载 `exp*_*.json`，再补充 `all_experiments.json`，后加载者不覆盖前加载者。
2. **阈值兼容**：`head.pt` 无 `threshold` 键时，`real_llm_classify` 回退到 `thr=0.5`（硬 argmax）。
3. **smoke 路径**：smoke 路径产出结构与 paper 路径完全一致，仅 `computation` 字段标记为 `"smoke_sklearn"` 而非 `"h100_real_qwen"`。
4. **`decision_threshold`**：exp1 QAD 蒸馏新增字段；旧版结果文件不包含此字段不影响图像脚本（仅 paper 级训后才会使用）。

## 四、验证命令

```bash
# 验证最新结果文件是否满足契约
python -m experiments.runner --validate-contract

# 查看 paper_data.py 自检报告
python docs/figure_scripts/paper_data.py

# 对齐检查器
python docs/figure_scripts/check_alignment.py

# 生成论文图像
cd docs/figure_scripts && python generate_all.py
```

## 五、变更历史

| 日期 | 变更内容 |
|------|---------|
| 2026-08-03 | 初始映射创建；新增 `decision_threshold` 字段 (exp1)；新增 `std` 字段 (exp2/exp11/exp14 variants/schemes/models)；`cot_max_new_tokens` 配置项；`val_frac` 校准集比例 |


---

## 每个实验结果 JSON 的必填顶层字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `experiment` | `str` | 短 ID，如 `"exp1"` |
| `computation` | `str` | 执行路径，如 `"h100_real_qwen"` 或 `"smoke_sklearn"` |

---

## 实验与图像脚本参数对齐映射

### exp1 → Fig 4（loss 收敛曲线）

| paper_data.py 读取路径 | 实验产出字段 | 回退值 |
|------------------------|-------------|--------|
| `_get("exp1", "f1")` | `result["f1"]` | `0.916` |
| `_get("exp1", "trajectory")` | `result["trajectory"]` (list of `{"step","kl","ce","drift_pct","snr_db"}`) | `[]` |
| `_get("exp1", "kl_plateau")` | `result["kl_plateau"]` | `0.045` |
| `_get("exp1", "kl_converged")` | `result["kl_converged"]` | `0.016` |
| `_get("exp1", "ovf_activation_step")` | `result["ovf_activation_step"]` | `1400` |
| `_get("exp1", "total_steps")` | `result["total_steps"]` | `2000` |
| `_get("exp1", "snr_min")` | `result["snr_min"]` | `18.4` |
| `_get("exp1", "snr_max")` | `result["snr_max"]` | `18.9` |

### exp2 → Fig 5(a)（loss 函数消融）

| paper_data.py 读取路径 | 实验产出字段 |
|------------------------|-------------|
| `_get("exp2", "variants", "kl_only", "f1")` | `result["variants"]["kl_only"]["f1"]` |
| `_get("exp2", "variants", "kl_only", "kl_final")` | `result["variants"]["kl_only"]["kl_final"]` |
| 同上，key = `mse_only` / `ce_only` / `kl_mse_combined` / `kl_task` | 同结构 |

### exp3 → Fig 6(a)(b)（OV-Freeze 消融）

| paper_data.py 读取路径 | 实验产出字段 |
|------------------------|-------------|
| `_get("exp3", "conditions", "no_reg", "f1")` | `result["conditions"]["no_reg"]["f1"]` |
| `_get("exp3", "conditions", "no_reg", "variance_drift_pct")` | `result["conditions"]["no_reg"]["variance_drift_pct"]` |
| 同上，key = `ov_freeze_full` / `ov_freeze_half` / `ov_freeze_quarter` | 同结构 |
| `_get("exp3", "layer_selection", "early", "f1")` | `result["layer_selection"]["early"]["f1"]` |
| `_get("exp3", "layer_selection", "early", "variance_drift_pct")` | `result["layer_selection"]["early"]["variance_drift_pct"]` |
| 同上，key = `mid` / `late` / `all` | 同结构 |
| `_get("exp3", "rho_sweep", "rho_0.0", "f1")` | `result["rho_sweep"]["rho_0.0"]["f1"]` |
| `_get("exp3", "rho_sweep", "rho_0.0", "ppl")` | `result["rho_sweep"]["rho_0.0"]["ppl"]` |
| 同上，key = `rho_0.1` ... `rho_0.5` | 同结构 |

### exp5 → Fig 8(b)(c)（AdvFraud / LDP）

| paper_data.py 读取路径 | 实验产出字段 | 回退值 |
|------------------------|-------------|--------|
| `_get("exp5", "advfraud", "full_pool", "f1")` | `result["advfraud"]["full_pool"]["f1"]` | `0.841` |
| `_get("exp5", "advfraud", "curated", "f1")` | `result["advfraud"]["curated"]["f1"]` | `0.875` |
| `_get("exp5", "bf16_matched_advfraud")` | `result["bf16_matched_advfraud"]` | `0.882` |
| `_get("exp5", "paper_reference", "ldp_eps_1_5_f1")` | `result["paper_reference"]["ldp_eps_1_5_f1"]` | `0.902` |

### exp6 → Fig 7（推测解码）

| paper_data.py 读取路径 | 实验产出字段 | 回退值 |
|------------------------|-------------|--------|
| `_get("exp6", "diagnostic_B", "h100_measured", "generic")` | `result["diagnostic_B"]["h100_measured"]["generic"]` | `0.78` |
| `_get("exp6", "diagnostic_B", "h100_measured", "domain")` | `result["diagnostic_B"]["h100_measured"]["domain"]` | `0.86` |
| `_get("exp6", "paper_reference", "alpha_generic")` | `result["paper_reference"]["alpha_generic"]` | `0.78` |
| `_get("exp6", "paper_reference", "alpha_tuned")` | `result["paper_reference"]["alpha_tuned"]` | `0.86` |
| `_get("exp6", "paper_reference", "gamma_deploy")` | `result["paper_reference"]["gamma_deploy"]` | `5` |
| `_get("exp6", "paper_reference", "speculative_speedups")` | `result["paper_reference"]["speculative_speedups"]` | 内置表 |

### exp8 → Fig 7 / Table 7（延迟基准）

| paper_data.py 读取路径 | 实验产出字段 |
|------------------------|-------------|
| `_get("exp8", "latencies", "int4")` | `result["latencies"]["int4"]`（单位 ms P50） |
| `_get("exp8", "latencies", "fp16")` | `result["latencies"]["fp16"]` |
| `_get("exp8", "latencies", "bf16")` | `result["latencies"]["bf16"]` |

### exp10 → Fig 5(b)（教师规模消融）

| paper_data.py 读取路径 | 实验产出字段 |
|------------------------|-------------|
| `_get("exp10", "scales", "teacher", "f1_fixed")` | `result["scales"]["teacher"]["f1_fixed"]` |
| `_get("exp10", "scales", "teacher", "f1_conv")` | `result["scales"]["teacher"]["f1_conv"]` |
| 同上，key = `teacher_1.5b` / `teacher_3b` / `teacher_7b` | 同结构 |

### exp11 → Fig 3 / Table 4（量化方案）

| paper_data.py 读取路径 | 实验产出字段 |
|------------------------|-------------|
| `_get("exp11", "schemes", "int4", "f1")` | `result["schemes"]["int4"]["f1"]` |
| 同上，key = `nf4` / `fp16` / `int8` | 同结构 |

---

## 结果文件命名规范

| 类型 | 路径 | 说明 |
|------|------|------|
| 单次实验结果 | `outputs/results/exp{N}_{YYYYMMDD_HHMMSS}.json` | 带时间戳，最新文件优先 |
| 全量归并文件 | `outputs/results/all_experiments.json` | `paper_data.py` 候补来源 |
| 归档快照 | `outputs/archive/{YYYY-MM-DD_HHMMSS}_experiment_results.md` | 每次重跑前自动归档 |

---

## 验证命令

```bash
# 验证最新结果文件是否满足合约
python -m experiments.runner --validate-contract

# 查看 paper_data.py 自检报告
python docs/figure_scripts/paper_data.py
```

---

## 旧字段兼容策略

- `paper_data.py` 对所有字段均配有硬编码论文常量作为回退值；
- smoke 路径产出字段结构与 paper 路径完全一致，仅数值为合成近似；
- 禁止修改 `docs/figure_scripts/` 下任何文件；实验侧主动适配图像脚本期望。
