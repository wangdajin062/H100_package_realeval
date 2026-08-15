# 实验产出 → 论文图像脚本 字段对齐映射

> 本文档定义 `docs/figure_scripts/paper_data.py` 所需字段与实验脚本产出字段的完整对齐关系。
> **硬性约束：`docs/figure_scripts/` 下的**图像脚本**（`figN_*.py` / `paper_style.py`）不可修改；
> `paper_data.py` 是唯一的适配/桥接层——实验侧字段变化在此对齐，实验脚本本身也须相应产出。**

## 一、映射总表

### Figure 3 → Main Results (F1 + Recovery)
| 图脚本变量 | paper_data 读取路径 | 实验产出字段 | 类型 | 备注 |
|-----------|-------------------|------------|------|------|
| EXP01_QUANT_QUALITY | （论文常量，**不读实验**） | 外部 PTQ 基线常量表（RTN/AWQ/GPTQ/SpinQuant/QuaRot/BitDistill） | list | paper_data 硬编码，非本套件测量 |
| QAT_QAD_OVF | exp11.schemes.int4.{f1,std} + exp1.{f1,std} + exp3.conditions.ov_freeze_full.{f1,std} + exp14.models.q4km_0.5b_llama_cpp.{f1,std} | 各实验对应字段 | 4 行 | QAT(int4)/QAD/QAD+OVF/Q4_K_M 四行，分别来自 exp11/exp1/exp3/exp14 |
| BF16_F1 | （论文自引用常量 0.931，**不读实验**） | — | float | BF16 ceiling，非实测 |

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
| EXP03_LOSS_ABLATION | exp2.variants.{kl_only,mse_only,ce_only,kl_mse_combined}.{f1,kl_final,std} | exp2 → variants.{name}.{f1,kl_final,std} |
| EXP09_TEACHER | exp10.scales.{teacher,teacher_1.5b,teacher_3b,teacher_7b}.{f1_fixed,f1_conv} | exp10 → scales.{key}.{f1_fixed,f1_conv} |

### Figure 6 → OV-Freeze Ablation
| 图脚本变量 | paper_data 读取路径 | 实验产出字段 |
|-----------|-------------------|------------|
| EXP04_OVF_LAYER_ABLATION | exp3.layer_selection.{early,mid,late,all}.{f1,variance_drift_pct} | exp3 → layer_selection.{name}.{f1,variance_drift_pct} |
| EXP10_OVF_STEP_RATIO | exp3.rho_sweep.rho_{0.0..0.5}.{f1,ppl} | exp3 → rho_sweep.{key}.{f1,ppl} |

### Figure 7 → Speculative Decoding
| 图脚本变量 | paper_data 读取路径 | 实验产出字段 |
|-----------|-------------------|------------|
| EXP05_SPECULATIVE | exp6.paper_reference.speculative_speedups (cited) | exp6 → paper_reference.speculative_speedups | 缺失时用内置 speedup 表 |
| SPEC_ALPHA_GENERIC | exp6.diagnostic_B.h100_measured.generic（实测，>0.01 时优先）否则 exp6.paper_reference.alpha_generic (cited) | exp6 → 二者之一 | measured 优先、回退 cited |
| SPEC_ALPHA_TUNED | exp6.paper_reference.alpha_tuned (cited) | exp6 → paper_reference.alpha_tuned |  |
| SPEC_GAMMA_DEPLOY | exp6.paper_reference.gamma_deploy (cited) | exp6 → paper_reference.gamma_deploy |  |

### Figure 8 → Revision Ablations
| 图脚本变量 | paper_data 读取路径 | 实验产出字段 |
|-----------|-------------------|------------|
| FIG8_QUANT | exp11.schemes.int4.f1（同质 INT4）+ exp3.conditions.ov_freeze_full.f1（异质 QAD+OVF）；`bf16_ref`=BF16_F1 常量 | exp11 → schemes.int4.f1；exp3 → conditions.ov_freeze_full.f1 | `delta` 由两 F1 计算 |
| FIG8_ADVFRAUD | exp5.advfraud.{full_pool,curated}.f1 + exp5.bf16_matched_advfraud (cited) | exp5 → advfraud.{full_pool,curated}.f1 + bf16_matched_advfraud | bf16_matched 为自引用常量 |
| FIG8_LDP | exp3.conditions.ov_freeze_full.f1（no-LDP）+ exp5.ldp_tradeoff.eps_1.5.f1 | exp3 → conditions.ov_freeze_full.f1；exp5 → ldp_tradeoff.eps_1.5.f1 | latency 为论文常量 |

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
3. **`decision_threshold`**：exp1 QAD 蒸馏新增字段；旧版结果文件不包含此字段不影响图像脚本（仅 paper 级训后才会使用）。
4. **`exp2.variants.kl_task` 兼容别名**：exp2 的 loss ablation 在科学上已将 `kl_task` 合并到 `kl_only`（OVF 在 exp3 中单独消融），但 `paper_data.py` 的 `EXP03_LOSS_ABLATION` 仍保留 `kl_task` 标签。实验脚本自动将 `kl_only` 复制为 `kl_task`，保证图像脚本无需修改即可读取。
5. **`std` 字段补齐**：exp3 的 `conditions.*` / `layer_selection.*` 以及 exp11 的 `schemes.*` 在单 seed 运行时 `std` 为 `None`（与多 seed 聚合结构一致）；`None` 表示单 seed 无测量标准差。

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
| 2026-08-05 | 重构后对齐修复：exp2 增加 `kl_task` 兼容别名；exp3 smoke 补齐 `conditions` / `layer_selection` 的 `std`；exp11 smoke 补齐 `schemes` 的 `std` / `n_seeds`；新增 `metrics/`、`runner/`、`config/`、`realeval/io/` 子包 |
| 2026-08-13 | 文档审计修正：移除已删除的 smoke 路径相关描述；exp1 回退值更新（f1=0.7974，Fig4 锚点统一为 `None` 显式报缺）；exp5 LDP 改读 `ldp_tradeoff.eps_1.5.f1`；exp6 移除不存在的 `domain` 键；exp8 改读 `latency_detail.*.{p50_ms,p99_ms}`；exp2/exp10 variant/scale 键名修正 |
| 2026-08-14 | 第三轮审计登记（P2-18 发现）：Fig3/Fig7/Fig8 来源表与代码不符、exp5 fallback 过时、缺 exp4/7/9/12/13 章节 |
| 2026-08-14（修订） | 按 P2-18 修订本文档：§一 Fig3 表（`EXP01_QUANT_QUALITY`/`BF16_F1` 标注为论文常量、`QAT_QAD_OVF` 明确跨 exp11/exp1/exp3/exp14）、Fig7 表（`EXP05_SPECULATIVE` 读 speculative_speedups、`SPEC_ALPHA_GENERIC` measured 优先）、Fig8 表（`FIG8_QUANT`=exp11.int4+exp3.ov_freeze_full、`FIG8_LDP` 含 exp3 no-LDP）；exp5 fallback 更新为 0.1238/None；顶部约束澄清 `paper_data.py` 为桥接层；补 exp4/7/9/12/13 契约章节 |


---

## 每个实验结果 JSON 的必填顶层字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `experiment` | `str` | 短 ID，如 `"exp1"` |
| `computation` | `str` | 执行路径，如 `"h100_real_qwen"`（paper 路径） |

---

## 实验与图像脚本参数对齐映射

### exp1 → Fig 4（loss 收敛曲线）

| paper_data.py 读取路径 | 实验产出字段 | 回退值 |
|------------------------|-------------|--------|
| `_get("exp1", "f1")` | `result["f1"]` | `0.7974` |
| `_get("exp1", "trajectory")` | `result["trajectory"]` (list of `{"step","kl","ce","drift_pct","snr_db"}`) | `[]` |
| `_get("exp1", "kl_plateau")` | `result["kl_plateau"]` | `None`（显式报缺） |
| `_get("exp1", "kl_converged")` | `result["kl_converged"]` | `None`（显式报缺） |
| `_get("exp1", "ovf_activation_step")` | `result["ovf_activation_step"]` | `None`（显式报缺） |
| `_get("exp1", "total_steps")` | `result["total_steps"]` | `None`（显式报缺） |
| `_get("exp1", "snr_min")` | `result["snr_min"]` | `None`（显式报缺） |
| `_get("exp1", "snr_max")` | `result["snr_max"]` | `None`（显式报缺） |

> 注：Fig4 锚点回退值统一为 `None`，表示显式报缺——不再用论文常量冒充实测；真实 exp1 结果存在时仍正常读取（fig4 缺数据时因 `None` 报错属预期行为）。

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
| `_get("exp5", "advfraud", "full_pool", "f1")` | `result["advfraud"]["full_pool"]["f1"]` | `0.1238` |
| `_get("exp5", "advfraud", "curated", "f1")` | `result["advfraud"]["curated"]["f1"]` | `None`（显式报缺） |
| `_get("exp5", "bf16_matched_advfraud")` | `result["bf16_matched_advfraud"]` | `0.882` |
| `_get("exp5", "ldp_tradeoff", "eps_1.5", "f1")` | `result["ldp_tradeoff"]["eps_1.5"]["f1"]` | `None`（显式报缺） |

### exp6 → Fig 7（推测解码）

| paper_data.py 读取路径 | 实验产出字段 | 回退值 |
|------------------------|-------------|--------|
| `_get("exp6", "diagnostic_B", "h100_measured", "generic")` | `result["diagnostic_B"]["h100_measured"]["generic"]` | `0.78` |
| `_get("exp6", "paper_reference", "alpha_generic")` | `result["paper_reference"]["alpha_generic"]` | `0.78` |
| `_get("exp6", "paper_reference", "alpha_tuned")` | `result["paper_reference"]["alpha_tuned"]` | `0.86` |
| `_get("exp6", "paper_reference", "gamma_deploy")` | `result["paper_reference"]["gamma_deploy"]` | `5` |
| `_get("exp6", "paper_reference", "speculative_speedups")` | `result["paper_reference"]["speculative_speedups"]` | 内置表 |

### exp8 → Fig 7 / Table 7（延迟基准）

| paper_data.py 读取路径 | 实验产出字段 |
|------------------------|-------------|
| `_get("exp8", "latency_detail", "int4", "p50_ms")` | `result["latency_detail"]["int4"]["p50_ms"]`（单位 ms P50） |
| `_get("exp8", "latency_detail", "int4", "p99_ms")` | `result["latency_detail"]["int4"]["p99_ms"]`（单位 ms P99） |
| 同上，key = `fp16` / `bf16` | 同结构 |

> 注：权威来源为结构化的 `latency_detail.<scheme>.{p50_ms,p99_ms}`；扁平的 `latencies.<scheme>` 仅存 P50 标量，不可用于 P99（会静默读到 P50 值）。

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

### exp4 → 经典基线（不直接进图，consistency/contract 校验）

| 契约字段 | 实验产出字段 |
|---------|-------------|
| `classifiers.logreg.f1` / `xgb.f1` / `mlp.f1` / `qwen_base.f1` | `result["classifiers"][{name}]["f1"]` |

### exp7 → 隐私验证（不直接进图，contract 校验）

| 契约字段 | 实验产出字段 | 备注 |
|---------|-------------|------|
| `pii_report` / `asv_eer_pct` / `speaker_id_accuracy` / `n_speakers` | 对应顶层键 | 真实测量 |
| `glo_reconstruction_corr` | 顶层键 | **DEMO-only**：`glo_reconstruction_is_demo=True` 时为随机投影沙盒值，非独立测量（见 P1-M4） |

### exp9 → CoT 消融（contract 校验）

| 契约字段 | 实验产出字段 |
|---------|-------------|
| `with_cot.{f1,fpr}` / `without_cot.{f1,fpr}` | `result[{with_cot,without_cot}][{f1,fpr}]` |

### exp12 → FraudFusion 基线 + 存储分解（contract 校验）

| 契约字段 | 实验产出字段 | 备注 |
|---------|-------------|------|
| `competitor_comparison_real.QAD_MultiGuard_INT4.f1` | 同结构 | FraudFusion_pruned_INT4.f1 为 cited（None，无发布权重） |
| `storage_decomposition_point8.{footprints_mb,quantization_alone_x,param_scale_alone_x,total_advantage_x}` | 同结构 | footprints_mb 缺磁盘模型文件时各 advantage 为 None（键仍存在） |

### exp13 → 融合策略（不直接进图，contract 校验）

| 契约字段 | 实验产出字段 | 备注 |
|---------|-------------|------|
| `strategies.{softmax,sigmoid,transformer}.{f1,accuracy,latency_ms}` | `result["strategies"][{name}][...]` | `fusion_degraded=True` 时为纯文本回退（见 P2-2） |

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

- `paper_data.py` 对所有字段均配有硬编码论文常量作为回退值（部分字段按审计结论改为 `None` 显式报缺，详见各实验映射表）；
- 禁止修改 `docs/figure_scripts/` 下任何文件；实验侧主动适配图像脚本期望。
