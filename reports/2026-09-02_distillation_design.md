# QAD-MultiGuard 蒸馏逻辑与教师-学生模型设计

> 日期：2026-09-02
> 范围：论文 [v29.tex](docs/v29.tex) §QAD（`Pure KL` / `Homologous self-distillation` / `Edge–Cloud Co-Quantisation` / `OV-Freeze`）
> + 实现 [real_backend.py](realeval/real_backend.py) `real_qad_distill_train` + 消融 [exp1](experiments/exp1_qad_production.py) / [exp2](experiments/exp2_qad_loss_ablation.py) / [exp3](experiments/exp3_ov_freeze_control.py)
> 目的：把教师-学生蒸馏设计（论文视角）与实现（代码视角）对齐，逐式逐行核对，诚实标注差异。

---

## 0. 一句话定位

QAD（Quantisation-Aware Distillation）是一种**同源自蒸馏**：用 **BF16 全精度教师** 监督**同架构的量化学生**，目标是纠正低比特量化引入的**输出分布偏移**，而非从异构教师迁移任务知识。Headline 目标是**纯 KL 散度**（T=1，无 CE 项），辅以 **OV-Freeze** 正则对齐教师-学生的激活方差。双轨部署（云端 `NVFP4` / 边缘 `Q4_K_M`）共享同一 BF16 教师分布作为统一优化靶。

---

## 1. 架构总览

```
                 ┌─────────────────────────────────────────────┐
                 │  BF16 Homologous Teacher                     │
                 │  Qwen2.5-0.5B-Instruct (frozen, no grad)    │
                 └───────────────┬─────────────────────────────┘
                                 │ p_teacher(y|x)   (token-level logits)
                                 ▼
                 ┌─────────────────────────────────────────────┐
                 │  Quantised Student (same architecture)      │
                 │  NVFP4 (cloud, QDQ fake-quant QAT/NBE)      │
                 │  Q4_K_M (edge, GGUF block quant, PTQ+LoRA)  │
                 │  + 2-layer classification head (128→2)      │
                 └───────────────┬─────────────────────────────┘
                                 │ p_student(y|x)
                                 ▼
                 L_QAD = KL(p_teacher ‖ p_student)   (Eq. kl-loss)
                 L_OVF = λ Σ ‖Var_EMA(y) − σ²_BF16‖² (Eq. ovf-loss)
                 L_joint = L_QAD + L_OVF              (Eq. joint)
```

---

## 2. 教师-学生架构设计

### 2.1 同源自蒸馏（homologous self-distillation）

- **教师** = **学生骨干** = `Qwen2.5-0.5B-Instruct`（[experiments.yaml:8-9](config/experiments.yaml#L8-L9)）。教师以 BF16 冻结，学生以低比特量化后训练。
- 设计动机（[v29.tex:288](docs/v29.tex#L288)）：QAD 纠正的是**量化造成的分布偏移**，不是异构教师的知识迁移，因此同源教师保证 KL 目标在架构上天然对齐，无需显式特征空间正则。
- 代码里教师与学生的 hidden size 相同时复用同一个 `head`（[real_backend.py:168-171](realeval/real_backend.py#L168-L171)），KL 直接在 2 类 logits 上计算。

### 2.2 加载与分类头

| 组件 | 实现 | 位置 |
|---|---|---|
| 教师加载（冻结） | `load_causal_lm(teacher, bf16=True)`，前向走 `torch.inference_mode()`（无 grad） | [real_backend.py:266-269](realeval/real_backend.py#L266-L269) |
| 学生加载（量化） | `load_causal_lm(student, quantize=quantize, bf16=True)` | [real_backend.py:121](realeval/real_backend.py#L121) |
| 分类头 | 两层 `Linear(hidden→128)→ReLU→Linear(128→2)`，Kaiming init + 末层 Xavier | [real_backend.py:145-166](realeval/real_backend.py#L145-L166) |
| NBE 路径不挂 LoRA | `quantize=="nvfp4"` 时 adapter 强制 `"base"`（QAT 直接训量化权重，无 adapter） | [real_backend.py:125-130](realeval/real_backend.py#L125-L130) |

### 2.3 异构教师（exp10 teacher-scale 消融）

当教师 hidden size ≠ 学生（1.5B/3B/7B 教师）时，构建**独立的可训练教师投影头** `teacher_head`（同结构，hidden→128→2），使 KL 可在 2 类 logits 上计算（[real_backend.py:168-186](realeval/real_backend.py#L168-L186)）。这仅服务于 exp10 消融；主结果走同源路径。

---

## 3. 蒸馏目标：纯 KL 与五个 loss 变体

### 3.1 纯 KL（headline）

论文 Eq. `kl-loss`（[v29.tex:276-280](docs/v29.tex#L276-L280)）：

$$L_{\mathrm{QAD}} = D_{\mathrm{KL}}\!\bigl( p_{\text{teacher}}(y|x)\,\|\,p_{\text{student}}(y|x) \bigr), \quad T = 1$$

代码对应 `loss_fn="pure_kl"` 分支（[real_backend.py:309-319](realeval/real_backend.py#L309-L319)）：

```python
kl_loss = F.kl_div(F.log_softmax(logits, dim=-1),      # student, T=1
                   F.softmax(t_logits_head, dim=-1),    # teacher, T=1
                   reduction="batchmean")
```

关键点：
- **T=1 固定**，训练与推理分布一致（[v29.tex:282](docs/v29.tex#L282)）。
- **无 CE 项**，区别于 hybrid QAT（CE+KL）。论文声称 pure-KL 达到 $D_{KL}=0.005$ vs QAT $0.311$（[v29.tex:284](docs/v29.tex#L284)）。
- exp1 生产训练固定 `loss_fn="pure_kl"`（[exp1_qad_production.py:43](experiments/exp1_qad_production.py#L43)），exp3 各 OV-Freeze 条件也固定 `pure_kl`（[exp3_ov_freeze_control.py:33](experiments/exp3_ov_freeze_control.py#L33)）。

### 3.2 loss_fn 五分支（exp2 消融矩阵）

代码里五种模式（[real_backend.py:363-373](realeval/real_backend.py#L363-L373)），与论文 loss-ablation 表逐项对应：

| `loss_fn` | 联合 loss 构成 | 论文对应项 | 代码注释 |
|---|---|---|---|
| `pure_kl` | `kl_loss`（T=1） | **Pure KL (ours)** | headline，Table 7 |
| `kl` | `ce + alpha_kl·kl`（温度缩放） | KL + task reg | hybrid |
| `mse` | `ce + mse` | Logits MSE | 特征对齐 |
| `ce` | `ce` | Cross-entropy (QAT) | QAT baseline |
| `kl_mse` | `ce + alpha_kl·kl + mse` | Three-term mixture | 3 项混合 |

exp2 精确编码这五变体（[exp2_qad_loss_ablation.py:28-34](experiments/exp2_qad_loss_ablation.py#L28-L34)），并**统一关闭 OVF**（`use_ovf=False`），避免与 exp3 混淆。

### 3.3 KL 计算的温度细节

- `pure_kl`：`log_softmax(logits)` 不除 T（T=1）。
- `kl`/`kl_mse`：`log_softmax(logits/T)` 与 `softmax(t_logits/T)`，乘回 `T²`（[real_backend.py:299-308](realeval/real_backend.py#L299-L308)）——标准 Hinton 温度缩放形式。
- 诊断 KL 与训练 KL 复用教师头 logits（[real_backend.py:382-391](realeval/real_backend.py#L382-L391)）。

---

## 4. OV-Freeze 正则（Output-Variance Freeze）

### 4.1 设计动机

量化（尤其 `Q4_K_M`）会放大投影层激活的方差漂移。论文声称 OV-Freeze 使层间方差偏差从 **+18.2% 降到 +1.3%**（[v29.tex:394](docs/v29.tex#L394)），从而在蒸馏→部署迁移阶段防止表征塌缩。

### 4.2 三个公式的代码实现（2026-09-02 重构为 forward-hook 实现）

| 论文公式 | 代码 | 一致性 |
|---|---|---|
| Eq. `ovf-loss`：$L_{OVF}=\lambda\sum_{\ell\in\mathcal P}\|\mathrm{Var}_{EMA}(y_\ell)-\sigma^2_{BF16,\ell}\|_2^2$ | `ovf_loss = ovf_lambda * Σ_{ℓ∈ovf_layers} F.mse_loss(s_var_ema[ℓ], t_var_calib[ℓ])` | ✅（投影层子集，见 §8-1） |
| Eq. `ema`：$\mathrm{Var}^{(t)}=\rho\cdot\mathrm{Var}^{(t-1)}+(1-\rho)\cdot\mathrm{Var}_{batch}$，$\rho=0.95$ | `s_var_ema[ℓ] = ovf_rho*s_var_ema[ℓ] + (1-ovf_rho)*s_var_batch[ℓ]` | ✅ |
| Eq. `ovf-rescale`：$c_\ell=\mathrm{sg}[\sqrt{\sigma^2_{BF16,\ell}/(\mathrm{Var}_{EMA}+\epsilon)}]$ | `c = (t_var_calib[ℓ]/(s_var_ema[ℓ]+1e-9)).sqrt().detach()`；forward 返回 `output * (1 + rescale_strength*(c-1))` | ✅（前向 stop-gradient rescaling，见 §8-2） |

关键实现细节：
- **forward-hook 捕获**：`register_forward_hook` 挂在 `self_attn.{q,k,v,o}_proj` 各投影层——teacher hook 算 `t_var_calib`（在线 batch 方差），student hook 算 `s_var_batch` 并在 `ovf_active` 且层 ∈ `ovf_layers` 时施加前向 rescaling。
- **方差估计用总体方差** `var(dim=(0,1))`（per-dim 向量，q/o 896 维、k/v 128 维各自独立），避免 batch=1 时 `(n-1)=0` 导致 NaN 反向污染学生权重。
- **投影层子集** `ovf_layers: tuple[str,...]`（默认 `("q","v","k","o")`）控制 L_OVF 与 rescaling 施加到哪些层；EMA 对所有投影层持续跟踪（使 no-OVF 基线仍可测非零 drift）。
- **drift 指标**（`drift_pct_final`）为 **signed** 相对偏差：`mean((s_var_ema − t_var_calib)/t_var_calib)·100`（+ 表示 student 高于 BF16 teacher，对齐论文 +18.2%→+1.3%）。

### 4.3 激活调度（staged activation）

- 论文：OV-Freeze **只在最后 30% 训练激活**（[v29.tex:394](docs/v29.tex#L394)）。
- 代码：concept-step 空间 `concept_total_steps=2000`，`ovf_activation_ratio=0.7` → `ovf_activation_step=1400`；`ovf_active = apply_ov_rescaling and concept_step >= 1400`（[real_backend.py:216-224](realeval/real_backend.py#L216-L224)、[real_backend.py:254](realeval/real_backend.py#L254)）。
- **concept-step 映射**：真实 batch 数被线性映射到 `[0, 2000)` 空间，保证 Fig4 的 OVF 调度 + SNR 范围对齐（[real_backend.py:249-251](realeval/real_backend.py#L249-L251)）。

---

## 5. 联合目标与训练流程

### 5.1 联合 loss

论文 Eq. `joint`（[v29.tex:371-375](docs/v29.tex#L371-L375)）：$L_{joint}=L_{QAD}+L_{OVF}$。

代码（[real_backend.py:375](realeval/real_backend.py#L375)）：

```python
loss = base_loss + rho * ovf_loss   # base 由 loss_fn 分支决定；rho 默认 1.0
```

### 5.2 优化器与 LR 调度

- **AdamW**，weight_decay=0.05；两组参数分层 LR：学生骨干 `backbone_lr=1e-5`、分类头 `head_lr=task_weight=1e-3`（[real_backend.py:198-204](realeval/real_backend.py#L198-L204)）。
- **warmup + cosine**：`LinearLR(0.01→1.0, 100 steps)` → `CosineAnnealingLR`，`SequentialLR` 串接（[real_backend.py:226-240](realeval/real_backend.py#L226-L240)）。

### 5.3 类别加权 + 标签平滑 + focal

- 按逆类频加权 CE（fraud 是少数类）：`cw = counts.sum()/(2*counts)`（[real_backend.py:206-214](realeval/real_backend.py#L206-L214)）。
- 标签平滑 0.1；focal loss 默认关闭（`focal_gamma=0`），配置项 `focal_gamma`（[real_backend.py:281-293](realeval/real_backend.py#L281-L293)）。

### 5.4 阈值校准（F1 的关键杠杆）

- 从 **train 集**切出 `val_frac=0.15` 作为校准 slice（永不碰 test）（[real_backend.py:134-143](realeval/real_backend.py#L134-L143)）。
- 在 val 上 `_best_f1_threshold`（默认 19 格 = 0.05 bins）搜索决策阈值，替代 argmax@0.5（[real_backend.py:411-428](realeval/real_backend.py#L411-L428)）——类别不平衡下 accuracy≫F1 时这是 F1 的最大杠杆。

### 5.5 量化 SNR 轨迹

每个 step 测 SNR = 教师功率 /（学生−教师）² 功率（对齐维度），记录 min/max 供 Fig4（[real_backend.py:324-330](realeval/real_backend.py#L324-L330)）。SNR 无值时返回 `None`（显式缺失），**不伪造**论文的 18.4/18.9（[real_backend.py:454-458](realeval/real_backend.py#L454-L458)）。

---

## 6. 双轨量化（Edge–Cloud Co-Quantisation）

论文 [v29.tex:290-322](docs/v29.tex#L290-L322) 与 Tab2：

| 维度 | 云端 `NVFP4` | 边缘 `Q4_K_M` |
|---|---|---|
| 骨干 | Qwen2.5-0.5B-Instruct | 同 |
| 参数量 | 494M | 494M |
| 量化 | QDQ 伪量化（block=16, FP8 E4M3 缩放），QAT via STE | GGUF 块量化，PTQ + LoRA |
| footprint | 248 MB | 240 MB |
| 目标平台 | Blackwell（NBE 在 H100 仿真） | ARM/Snapdragon |
| 精度恢复 | 99.1% | 98.5% |

代码侧：`quantize="nvfp4"` 走 NBE QDQ 伪量化 QAT（STE 直接训量化权重，无 LoRA）；边缘 `Q4_K_M` 是独立 PTQ 路径（`student_gguf` + `student_variant`），两条轨**共享同一 BF16 教师分布**作为统一优化靶。NBE 协议（Eq. `nbe`）在 [v29.tex:341-348](docs/v29.tex#L341-L348)。

---

## 7. 消融设计

### 7.1 exp2 — loss 消融（5 变体）

见 §3.2 表。统一 `apply_ov_rescaling=False`、`quantize="nvfp4"`、`epochs=3`，扫 5 个 `loss_fn`，多 seed 报 `f1 / f1_list / kl_final / std`。

### 7.2 exp3 — OV-Freeze 控制（投影层子集 + rescale 强度 sweep）

> ✅ 已按 2026-09-02 重构重写（原 freeze_frac/window/rho 三维 → ovf_layers/rescale_strength）。

| 子消融 | 变量 | 实现 |
|---|---|---|
| `conditions`（4 条件） | 投影层子集 `ovf_layers ∈ {(), (q), (q,v), (q,v,k,o)}` | no_reg / quarter / half / full |
| `layer_selection` | 投影层累加 `{q / q,v / q,k,v / q,k,v,o}` | q / q_v / q_v_k / q_v_k_o（对齐 Fig6a q→v→k→o 顺序） |
| `window_sweep` | `rescale_strength ∈ {0.0, 0.2, 0.4, 0.6, 0.8, 1.0}` | 前向 rescaling 强度（Eq.8），1.0 = 完整 $c_\ell$ |

三层语义明确分离：`ovf_rho`（EMA 系数 ρ，Eq.6）保留为 config 字段；`ovf_loss_weight`（$L_{joint}$ 中 OVF 项系数）与 `rescale_strength`（前向缩放强度）为函数参数。

---

## 8. 代码↔论文一致性标注（已修复于 2026-09-02）

以下 6 项是设计文档初版标注的代码↔论文差异，均已按重构修复（除 8-6 为待办）。保留原始发现供追溯。

### 8-1 ✅ 已修复 — OV-Freeze 作用层：投影层激活方差（原为 last hidden state）

- **修复**：real_backend 现用 `register_forward_hook` 捕获 `self_attn.{q,k,v,o}_proj` 各投影层输出，对齐其激活方差（per-dim `var(dim=(0,1))`），与论文 Eq. `ovf-loss` 的 $\mathcal P=\{q,k,v,o\}_{proj}$ 一致。
- **原始差异**：旧实现对齐 last hidden state 方差（`hidden_states[-1]`），与论文声称的投影层统计不符。

### 8-2 ✅ 已修复 — 前向 stop-gradient rescaling

- **修复**：student hook 在 `ovf_active` 且层 ∈ `ovf_layers` 时施加 `output * (1 + rescale_strength*(c-1))`，其中 `c = sg[√(σ²_BF16/(Var_EMA+ε))]`（`.detach()`），实现论文 Eq.8 前向 rescaling + Eq.9 反向流（梯度乘有界 `c`）。
- **原始差异**：旧实现 `scale` 仅用于事后 drift 指标，未施加到 student 前向。

### 8-3 ✅ 已修复 — ρ / rho / window 命名混淆

| 新名 | 语义 | 旧名 |
|---|---|---|
| `ovf_rho`（config） | Eq.6 EMA 系数 = 0.95 | 不变 |
| `ovf_loss_weight`（函数参数） | $L_{joint}$ 中 OVF 项系数 | `rho` |
| `rescale_strength`（函数参数） | 前向 rescaling 强度（Eq.8） | `window` |
| `window_sweep`（exp3） | 扫 `rescale_strength` | `rho_sweep` |

### 8-4 ✅ 已修复 — 投影层子集语义

- **修复**：`ovf_layers: tuple[str,...]` 取代 `freeze_frac`（维度比例）；exp3 `layer_selection` 键 `early/mid/late/all` → `q/q_v/q_v_k/q_v_k_o`（投影层累加，对齐 Fig6a q→v→k→o 顺序）。

### 8-5 ✅ 已修复 — drift 符号（signed）

- **修复**：drift 改为 signed 相对偏差 `mean((s_var_ema − t_var_calib)/t_var_calib)·100`（+ 表示 student 高于 BF16 teacher），对齐论文 "+18.2% → +1.3%"。

### 8-6 ⚠️ 待办 — fallback 默认值陈旧

`temperature` fallback 仍为 2.0（config 权威值 1.0，论文 T=1）。生产路径显式传 config 无运行时 bug，但建议将 fallback 对齐（`temperature`→1.0）。本次重构未触及（超出 OV-Freeze 范围）。

### 8-7 ⚠️ 已知 gap — Fig6 的 FFN / activation-window 维度

- **FFN 扩展**：论文原 Fig6(a) 的 FFN / +FFN 两条 bar 从未在 real_backend 实现（旧代码用 early→FFN 牵强映射）。重构已删除这两条 bar 及论文第 799 行的 FFN 结论，FFN OV-Freeze 标注为待实现。
- **activation window**：论文原 Fig6(b) 的 x 轴标为 "activation step ratio"，但 exp3 实际扫的是 `rescale_strength`（前向缩放强度）。重构已把 Fig6(b) 改为 rescale-strength sweep，`ovf_activation_ratio`（激活时机，最后 30%）的独立 ablation 标注为待实现。

---

## 9. 数字：暂用论文现有 headline 值（待 H100 重跑更新）

按用户决策（2026-09-02）：**数字暂用论文现有 headline 值，待 H100 重跑后如实更新**，本次重构不动任何数字。

| 数字 | 来源实验 | 状态 |
|---|---|---|
| QAD F1=0.916 / KL=0.005（pure-KL） | exp1 | 暂用历史值 |
| 云端 NVFP4 F1=0.923 / 边缘 Q4_K_M F1=0.917 | exp11 / exp14 | 暂用历史值 |
| OV-Freeze drift +18.2%→+1.3% | exp3 | 暂用历史值（重跑后 drift 因 signed 指标变化可能更新） |
| 量化 SNR 18.4 / 18.9（Fig4 panel b） | exp1 trajectory | 暂用历史值（SNR 无值时返回 None，不伪造） |
| loss 消融（Table 5） | exp2 | 暂用历史值 |

运行命令见 [2026-09-02_a_road_execution.md](2026-09-02_a_road_execution.md) §三。

---

## 附：公式↔代码速查

| 论文 Eq. | label | 代码位置 |
|---|---|---|
| $L_{QAD}=KL(p_T\|p_S)$ | `eq:kl-loss` | [real_backend.py:309-319](realeval/real_backend.py#L309-L319) |
| $\widehat{W}=clamp(round(W/s),q_{min},q_{max})\cdot s$ | `eq:nbe` | NBE QDQ 伪量化（student loader） |
| $L_{OVF}=\lambda\sum\|Var_{EMA}-\sigma^2_{BF16}\|^2$ | `eq:ovf-loss` | [real_backend.py:353-355](realeval/real_backend.py#L353-L355) |
| $Var_{EMA}=\rho Var_{EMA}+(1-\rho)Var_{batch}$ | `eq:ema` | [real_backend.py:342-347](realeval/real_backend.py#L342-L347) |
| $L_{joint}=L_{QAD}+L_{OVF}$ | `eq:joint` | [real_backend.py:375](realeval/real_backend.py#L375) |
| $c_\ell=sg[\sqrt{\sigma^2/(Var_{EMA}+\epsilon)}]$ | `eq:ovf-rescale` | [real_backend.py:350-352](realeval/real_backend.py#L350-L352) |
