# 实验结果合约（供图像脚本消费）

本文档定义 `docs/figure_scripts/paper_data.py` 所需的最小 JSON 字段集合。  
实验脚本必须产出符合此合约的结果；`paper_data.py` **不得修改**，字段对齐由实验侧负责。

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
