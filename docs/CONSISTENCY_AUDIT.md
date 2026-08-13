# 一致性审计报告：论文声称值 vs 实验真实产出

> 依据：论文源文件 `v25.tex`（1087 行）、`docs/figure_scripts/paper_data.py`（数据桥接）。
> 审计日期：2026-08-13。

---

## 0. 结论（一句话）

论文图表变量与实验真实产出之间是**系统性结论反转 / 未复现**，而非数值笔误；`paper_data.py` 的
fallback 值是**真实实验产出**（未达论文声称值），不是要「对齐」的 bug。仅有少数几处是真正的
代码 bug（字段复用、过时值），已在本轮修复（见 §4）。

---

## 1. 三层数据源与它们的真实关系

| 层 | 位置 | 值域 | 性质 |
|---|---|---|---|
| ① 论文声称值 | `v25.tex` | F1 0.91–0.93，KL 0.005–0.311 | 待复现的**目标** |
| ② 图表脚本坐标轴/docstring | `docs/figure_scripts/fig*.py` | 与①一致（0.91–0.93） | 按①写死，**禁改** |
| ③ 实验真实产出 | `paper_data.py` fallback | F1 0.56–0.80（调优后核心组件），drift 0–52.45% | **真实跑出来的** |

第③层与①/②不兼容，意味着**复现尚未成功**。这不是把③「改」成①就能解决的——那样是伪造数据；
正确路径是「先改论文结论再改数字」（见 §5 核心原则），或等数据修复链重跑出真实数字。

---

## 2. 逐表差距清单

### 2.1 主结果表（论文 Table 3 / `tab3-en`，对应 Figure 3）

| 行 | 论文声称 | 实验真实产出 | 判定 |
|---|---|---|---|
| BF16（参考） | 0.931 ± 0.005 | 无实验（`BF16_F1` 常量） | 未复现基准行 |
| NVFP4 PTQ | 0.838 | 0.838（外部引用硬编码） | 引用，非实测 |
| NVFP4 QAT (CE) | 0.844 ± 0.014 | fallback `PH_EXP11_INT4_F1`=0.6172（调优前 exp1_qad 下游陈旧值，待重跑） | 未复现 |
| NVFP4 QAD | 0.916 ± 0.007 | fallback `PH_EXP1_F1`=0.7974（调优后，旧 0.5121） | 未复现 |
| NVFP4 QAD + OV-Freeze | **0.923 ± 0.006** | fallback `PH_EXP3_OVF_FULL_F1`=0.8047（调优后） | 未复现 |
| Q4_K_M QAD + OV-Freeze | 0.917 ± 0.007 | fallback `PH_EXP14_Q4KM_F1`=0.7025（=最新 exp14 q4km） | 未复现（值稳定在 0.70） |
| SAFE-QAQ | 0.918 | 引用，非实测 | 引用 |

核心卖点「QAD+OVF = 0.923」真实只到 **0.8047**；`recovery` 列若按 fallback 计算会显示
`0.7974/0.931 = 85.6%`（论文声称 98.4%）。

### 2.2 损失函数消融（论文 Table 5 / `tab5-en`，对应 Figure 6a）— **结论反转**

| 变体 | 论文 F1 | 论文 KL | 真实 exp2 F1 | 真实 exp2 KL | 排序 |
|---|---|---|---|---|---|
| Pure KL | **0.916**（最优） | 0.005 | 0.5577 | 0.34629 | ❌ 真实**最差** |
| Logits MSE | 0.901 | 0.082 | **0.7667**（真实最佳） | 3.34172 | ❌ 反转 |
| CE (QAT) | 0.844 | 0.311 | 0.7667 | 3.34172 | ❌ 反转 |
| 3-term | 0.879 | 0.124 | 0.5577 | 0.34629 | ❌ |
| KL + task | 0.908 | 0.041 | 0.5577 | 0.34629 | ❌ |

**论文核心卖点「Pure KL 最优」被真实实验否定**。根因：学生=教师同架构
（Qwen2.5-0.5B），`mse_loss≈0` → `kl_mse≈kl`、`mse≈ce`，loss 区分度受限。

### 2.3 CoT 消融（论文 `tab:cot-ablation-en`）— **结论反转**

| 配置 | 论文 TAF F1 | 真实 exp9 F1 | 真实 FPR |
|---|---|---|---|
| With CoT | 0.923 | **0.3131** | 0.2608 |
| Without CoT | 0.905 | **0.8047** | 0.0165 |

CoT 重做后：双分支都用微调模型+头，仅 CoT 不同。
结论：**CoT 推理对微调头分类有害**（0.80→0.31），不再是 base-generate 的 0.035 假象。

### 2.4 OV-Freeze 消融（论文 Figure 7，对应 Figure 6a/6b）— **drift 复现 ✅ / F1 未复现**

drift（论文图 7a）—— **机理复现成功**：

| 配置 | 论文 drift | 真实 exp3 drift |
|---|---|---|
| no OVF | +18.2% | **52.45%**（调优后） |
| ov_freeze_quarter | — | 48.186%（调优前，待重跑） |
| ov_freeze_half | — | 35.561%（调优前，待重跑） |
| ov_freeze_full (q,k,v,o) | +1.3% | **0.0%** |

F1（论文图 7a）—— **未复现**：论文称 OVF 使 F1 0.916→0.923；真实 exp3 **f1 恒 0.8047**
（OVF 只降低 drift、不提升 F1）。这直接否定了「OV-Freeze 提升 F1」的方法论主张。

### 2.5 教师选择（论文 Figure 6b）

论文仅定性描述（同源 0.5B 最优，`fig6` 无表格），无精确数值。最新 exp10（调优后）单一 F1：
0.5B **0.9149** / 1.5B 0.5116 / 3B 0.7676 / 7B 0.7038 —— 0.5B 最优、尺度非单调（1.5B 异常低）。
但 `EXP09_TEACHER` fallback 是 `f1_fixed`/`f1_conv` 双维字段，与 exp10 单一 F1 字段契约不匹配；
字段契约本身不匹配（§6.2），本轮按「无实测值改 None」改为 `fallback=None` 显式报缺（见 §4.4）。

### 2.6 推测解码（论文 Table `tab:speculative_decoding-en` / Figure 8）— **基本一致 ✅**

α 0.78→0.86、加速比 2.92×/2.78×→3.49×/3.32×、γ=7: 4.10×/3.90×、γ=10: 4.74×/4.51× 全部一致。

⚠️ 论文自身矛盾：正文/图 caption 写 α **0.78→0.86**，但 `tab:speculative_decoding-en` 表格写
α **0.85→0.91**（加速比数值相同、仅 α 标注不同）。属论文内部不一致，非代码问题。

### 2.7 修订轮消融（论文 Figure 5，对应 `fig8_revision_ablations.py`）

| 面板 | 论文声称 | 真实产出 | 判定 |
|---|---|---|---|
| (a) 同质 INT4 vs 异质 | 0.915 vs 0.923（+0.008） | 同质=exp11 int4 0.6172，异质=exp3 full 0.8047 | 未复现，且修复后 delta 符号/量级均≠论文 |
| (b) AdvFraud full vs curated | 0.841 vs 0.875 | full_pool fallback=0.1238（exp5 中断），curated=0.875 | full 未复现 |
| (c) ε-LDP | 0.923→0.902（−0.021） | no-LDP=0.8047，eps-LDP=0.902（引用） | 未复现 |

### 2.8 隐私表（论文 `tab:privacy_attack-en`）

WER/PESQ/STOI/MOS/Speaker-ID/ASV-EER **全部为论文声称值，无实验产出**。需 exp7（对抗/隐私验证）
跑出真实数字后对照。

### 2.9 延迟口径

- 论文端到端 P50 = 268 ms = 12（特征提取）+ 5（传输）+ 230（NVFP4 CoT 推理）+ 21（融合）。
- `LATENCY_P50_MS` fallback = 46.47 / 34.3 / 28.3（+pad 12），求和 121 ms —— 这是 **exp8 的
  per-token/inference 延迟**，与论文的**端到端/请求**口径不同，两者不可直接比较。
- 属口径差异，非 bug；需明确 exp8 输出端到端分解（12/5/230/21）后才能对图。

---

## 3. 内部矛盾与契约存疑（未修复，需决策）

1. **`PH_EXP11_INT4_F1` 被映射到主结果表的「NVFP4 QAT (CE)」行**：exp11 是量化方案对比
   （fp16/int8/int4/nf4），其 int4 方案是否等价于「QAT」存疑；更接近「PTQ int4」。语义待确认。
2. **`EXP04_OVF_LAYER_ABLATION` 的映射混乱**：fig6a 的 x 轴标签 `no OVF/FFN/q/q,v/q,k,v/q,k,v,o/+FFN`
   混合了 `conditions`（OVF 比例：quarter/half/full）与 `layer_selection`（层：early/mid/late）两套
   字段，`FFN`、`+FFN` 等标签与真实 exp3 字段无一一对应。需在实验脚本侧统一输出契约。
3. **`q,k,v,o +FFN` 行完全复制 `q,k,v,o` 行**（f1、drift 逐字段相同）——真实 exp3 未单独产出
   `+FFN` 点，当前为占位复制，图上看不出「+FFN 无增益」的消融差异。
4. **`PH_EXP1_F1`=0.4256 与最新 exp1 acc=0.7863**：两者不是同一指标（F1 vs accuracy），但都来自
   exp1，需统一 exp1 输出 F1 而非 acc 作为主结果来源。

---

## 4. 本轮修复的真 bug（`paper_data.py`）

> 遵循「不改真实数值、不改成论文值」——只修字段/过时值，不动真实实验产出的语义。

### 4.1 修复 1：`exp1.f1` 字段复用（内部矛盾）

`_f1_homo`（fig8 的「同质 INT4」）此前误读 `exp1.f1`（QAD 字段），与 `PH_EXP1_F1` 的 fallback
（0.4256）相冲突，且 fallback 用了论文声称值 0.915。

- 改为读取 `exp11.schemes.int4.f1`（uniform INT4 的真实字段），与 `PH_EXP11_INT4_F1` 同源；
- fallback 统一为 0.4287（真实早期值），不再使用论文声称 0.915；后于 2026-08-13 同步最新 exp11 int4=0.6185（见 §4.3）；
- placeholder 更名 `PH_EXP1_HOMO_F1` → `PH_EXP11_HOMO_F1`。

### 4.2 修复 2：drift 过时值

exp3 的 drift fallback 此前对 `quarter/half/full` 三档错误地恒填 61.479（`no_reg` 的旧值）。
按实测递减序列更新：

| 占位符 | 旧 fallback | 新 fallback |
|---|---|---|
| `PH_EXP3_NO_OVF_DRIFT` | 61.479 | 61.479（不变） |
| `PH_EXP3_OVF_QUARTER_DRIFT` | 61.479 | 48.186 |
| `PH_EXP3_OVF_HALF_DRIFT` | 61.479 | 35.561 |
| `PH_EXP3_OVF_FULL_DRIFT` | 61.479 | 0.0 |

`layer_selection` 三点（early/mid/late）在最新 run 中未单独记录，暂保留 61.479（已注释说明）。

### 4.3 同步：最新实验产出 → fallback（2026-08-13，调优后）

按调优后实测（F1 调优 + OVF 修复 +
CoT 重做后）的最新真实 F1/KL，更新 `paper_data.py` 中真实数据驱动图表（fig3/5/6/8）的 fallback：

| 占位符 | 旧 fallback | 新 fallback（调优后实测） |
|---|---|---|
| `PH_EXP1_F1`（QAD） | 0.4256 | **0.7974** |
| `PH_EXP3_OVF_FULL_F1`（QAD+OVF） | 0.5577 | **0.8047** |
| `PH_EXP11_INT4_F1` / `PH_EXP11_HOMO_F1` | 0.6185 | 0.6172（陈旧值，待重跑 ~0.8） |
| `PH_EXP3_NO_OVF_F1` | 0.5577 | 0.8047 |
| `PH_EXP3_OVF_HALF_F1` | 0.5577 | 0.8047 |
| `PH_EXP3_OVF_QUARTER_F1` | 0.5577 | 0.8047 |
| `PH_EXP3_NO_OVF_DRIFT` | 61.479 | **52.45** |
| `PH_EXP2_*` 损失消融五组 | （上轮已同步） | 不变（调优前后一致） |

**未更新（保持原值，理由）**：

- `PH_EXP14_Q4KM_F1` 保持 0.7025 —— 调优后 exp14 异常回退（q4km 0.0014 / bf16 0.16，重跑验证中），
  不把已知异常值写进主结果表。
- `PH_EXP1_SNR_MIN/MAX`、`PH_EXP1_KL_PLATEAU/CONVERGED`、`PH_EXP1_OVF_ACTIVATION_STEP`、
  `PH_EXP1_TOTAL_STEPS`—— fig4 是确定性示意图（曲线/坐标轴写死论文值 18.2–19.0、0–0.055），
  此前论文值 18.4/18.9/0.045/0.016/1400/2000 冒充 fallback；本轮已改 `fallback=None` 显式报缺
  （见 §4.4），待真实训练曲线重跑回填。
- 各类 `std` 字段（`PH_EXP*_ERR`）—— 经字段契约审计（§6）确认，exp1/3/11/14 均**产出与脚本
  读取同名的 `std` 字段**（exp14 额外产出 `f1_std` 与 `std` 同值，脚本读 `std`）。此前「exp3/11/14
  产出 `f1_std` 与 `std` 字段名不匹配」的判断有误，予以更正；std 无需改字段名，待对应实验重跑
  出真实 std 后回填即可。
- exp3 `quarter/half` 的 drift —— 调优后完整 exp3（14 配置×5 seed）待跑，暂沿用调优前
  48.186/35.561（已注释说明）。
- `EXP09_TEACHER`（fig5b 教师选择）—— exp10 单一 F1 与 fallback 的 `f1_fixed`/`f1_conv` 双维
  字段不匹配，字段契约本身不匹配（§6.2），本轮按「无实测值改 None」改为 `fallback=None` 显式报缺
  （见 §4.4），不再用论文声称值冒充。

### 4.4 无真实产出字段的论文值 → None（2026-08-13，显式报缺）

按「无实测值字段改 None，显式报缺」原则，清理 `paper_data.py` 中所有以**论文声称值充当
fallback** 的「尚无真实实验产出」字段，统一改为 `fallback=None`（`_from_result` 显式
`fallback=None` 时返回 None、记录进 `_MISSING_PLACEHOLDERS`，不 raise——保证 `paper_data.py`
顶层可 import，fig3 正常出图，仅 fig4/5b/6a 生成时因 None 报 TypeError 显式报缺）：

| 组 | 占位符 | 旧 fallback（论文声称值） | 新 fallback |
|---|---|---|---|
| fig4 训练收敛/SNR | `PH_EXP1_KL_PLATEAU`/`PH_EXP1_KL_CONVERGED`/`PH_EXP1_OVF_ACTIVATION_STEP`/`PH_EXP1_TOTAL_STEPS`/`PH_EXP1_SNR_MIN`/`PH_EXP1_SNR_MAX` | 0.045 / 0.016 / 1400 / 2000 / 18.4 / 18.9 | **None** |
| fig6a layer_selection | `PH_EXP3_LAYER_{EARLY,MID,LATE}_{F1,DRIFT}`（6 字段） | f1 0.466 / 0.6119 / 0.5893，drift 61.479 | **None** |
| fig6a rho_sweep | `PH_EXP3_RHO_{00..05}_{F1,PPL}`（12 字段） | f1 0.4948 / 0.548 / 0.3198 / 0.6229 / 0.6837 / 0.6667；ppl 1.615 / 1.342 / 1.588 / 1.48 / 1.349 / 1.448 | **None** |
| fig5b 教师选择 | `PH_EXP10_T_{05B,15B,3B,7B}_{FIXED,CONV}`（8 字段） | 0.8963 / 0.8775 / 0.7953 / 0.7601 / 0.8611 / 0.42 / 0.5238 / 0.5608 | **None** |

同步两处真实值/估算修正：

- `PH_EXP1_ERR` 0.007 → **0.0133**（exp1 真实 std，5 seed，来自调优后实测）。
- `PH_EXP3_OVF_FULL_ERR`/`PH_EXP11_INT4_ERR`/`PH_EXP14_Q4KM_ERR` **保留**论文估算
  0.006 / 0.014 / 0.007（无实测 std；误差棒非核心结论，改 None 会破坏 fig3 误差棒渲染；注释已
  标注「非实测，待重跑回填」）。

### 4.5 smoke 合成结果过滤（防止 0.9268 污染图表）

`_load_results` 原先不过滤 `computation` 字段，会把 smoke 模式的合成占位值（`f1=0.9268` 等）
当成真实实验产出读取，导致图表画出「复现成功」的假图。现于加载循环中对 `computation` 以
`smoke` 开头的记录跳过（含 `all_experiments.json` 的分实验分支），确保只有 `h100_real_qwen`
（paper 模式）或 failed 记录进入桥接层。

自检输出验证（`python docs/figure_scripts/paper_data.py`）：`Experiments loaded: ['exp1']`
（仅 failed 的 exp1，无任何 smoke 记录）；`all consistency self-checks pass`；65 个非 cited 占位符中，
所有 fig4/fig5b/fig6a 的「论文值」字段均显示 `fallback=None`，无 0.9268 合成值、无 0.91–0.93
论文声称值残留。

---

## 5. 待重跑 / 待改写清单

优先级如下：

| 优先级 | 事项 | 说明 |
|---|---|---|
| 🔴 P0 | Tab.3 主结果全表重跑 | 调优后 QAD=0.7974 / QAD+OVF=0.8047，仍低于论文 0.92 |
| 🔴 P0 | Tab.CoT 结论改写 | 真实 exp9 CoT F1=0.3131 < without 0.8047 → 「CoT 有害」 |
| 🔴 P0 | Tab.5 损失消融结论改写 | Pure KL 真实最差（0.5577），MSE 最佳（0.7667） |
| 🔴 P0 | Tab.4 跨数据集 & 对抗全表重跑 | exp5/exp6 中断，需补跑 |
| 🔴 P0 | Fig.4/5/6/7 数据来源 | 训练收敛/SNR/教师规模/OVF 激活窗需真实数据 |
| 🟡 P2 | BF16 全管线基线 | 真实无此实验，需重跑 |
| 🟡 P2 | 数据修复链 | `transcribe_taf28k.py` → `build_taf28k_npz.py` → 重跑 exp5/10/13（见 `REPRODUCIBILITY.md` §10） |
| 🟡 P2 | 手机端 GGUF 回测 | 领域 LoRA 合并后 F1 是否 > 官方 GGUF 0.7025 |

> 核心原则（重申）：**先改论文结论，再改数字**。在数据修复链走完、真实数字稳定前，不要用
> 论文声称值覆盖 `paper_data.py` 的 fallback——那会把「复现失败」伪装成「复现成功」。

---

## 6. 字段契约审计（2026-08-13）：实验产出字段 vs 图表消费字段

> 系统化审计 14 个实验脚本（`experiments/exp*.py` 的 `run_paper` 路径）实际产出
> 的字段路径，是否与 `paper_data.py` 消费的 65 个字段路径一致。方法：静态追踪脚本代码（非读结果
> JSON——当前 `outputs/results/` 仅存 failed 的 exp1）。

### 6.1 结论

**字段契约层面 100% 对齐**——14 个实验脚本产出的字段路径与 `paper_data.py` 消费的字段路径
全部匹配，**无字段名 / 嵌套结构不匹配**。此前预估的「字段错位疑点」（exp3 层选择 key、exp8
latency 结构、exp10 单/双 F1、exp11 scheme key 名）经代码追踪逐一排除。鸿沟不在「字段」，而在：

1. **数值鸿沟**（真实值 vs 论文声称值，见 §2）——字段对得上，值对不上；
2. **渲染层坐标轴鸿沟**（fig 脚本写死论文值，见 §6.5）——值真实，但画不进按论文值写死的坐标轴。

### 6.2 逐实验字段对齐表

| 实验 | paper_data 读取路径 | 实验实际产出 | 判定 |
|---|---|---|---|
| exp1 | `f1`/`std`/`kl_plateau`/`kl_converged`/`ovf_activation_step`/`total_steps`/`snr_min`/`snr_max`/`trajectory` | 同名顶层字段，paper 路径产出 | ✅ |
| exp2 | `variants.{kl_only,mse_only,ce_only,kl_mse_combined,kl_task}.{f1,kl_final,std}` | 5 个 key 全产出（`kl_task` 为 `kl_only` 深拷贝别名） | ✅ |
| exp3 | `conditions.{4}.{f1,variance_drift_pct}` + `layer_selection.{early,mid,late}.{f1,variance_drift_pct}` + `rho_sweep.{6}.{f1,ppl}` | 同名；`layer_selection` 多出 `all` 冗余 key（未读取，非缺失） | ✅ |
| exp5 | `advfraud.{full_pool,curated}.f1`/`bf16_matched_advfraud`/`ldp_tradeoff.eps_1.5.f1` | 同名，paper 路径产出 | ✅ |
| exp6 | `diagnostic_B.h100_measured.{generic,domain}` + `paper_reference.{4}` | `generic` 有；`domain` 不产出（未实测，见 §6.4） | ⚠️ |
| exp8 | `latency_detail.{int4,fp16,bf16}.{p50_ms,p99_ms}` | 同名嵌套；flat `latencies.{scheme}` 仅 p50 供内部用 | ✅ |
| exp10 | `scales.{teacher,teacher_1.5b,teacher_3b,teacher_7b}.{f1_fixed,f1_conv}` | 同名双字段真实存在 | ✅ |
| exp11 | `schemes.int4.{f1,std}` | 同名（schemes 下 5 键：`bf16/fp16/int8/int4/nf4`） | ✅ |
| exp14 | `models.q4km_0.5b_llama_cpp.{f1,std}` | 同名；`GGUFUnavailable` 异常分支缺 `std` 且 `f1=None` | ⚠️ |

### 6.3 不被消费的实验（孤立数据）

以下 5 个实验的产出字段 `paper_data.py` **完全不读**（全文无 `"exp4/7/9/12/13"` 的 `_get`/`_from_result`）：

| 实验 | 产出字段 | 论文对应位置 |
|---|---|---|
| exp4 | `classifiers.{logreg,xgb,mlp,qwen_base}.{f1,accuracy}` | 基线对比表 |
| exp7 | `pii_report`/`asv_eer_pct`/`speaker_id_accuracy`/`glo_reconstruction_corr`/`coverage` | 隐私表（§2.8，当前全为论文声称值） |
| exp9 | `with_cot.{f1,fpr}`/`without_cot.{f1,fpr}` | CoT 消融表（§2.3） |
| exp12 | `competitor_comparison_real.*`/`storage_decomposition_point8.{footprints_mb,quantization_alone_x,param_scale_alone_x,total_advantage_x}` | 竞品对比 + 存储分解 |
| exp13 | `strategies.{early_fusion,late_fusion,hybrid}.{f1,accuracy,params,latency_ms}` | 融合策略表 |

这些字段当前是**孤立数据**，与图脚本之间无桥接；它们经 `experiments/consistency_check.py` 的
`PAPER_CLAIMS`（暴露 `exp9.with_cot.f1`/`exp13.strategies.late_fusion.f1`/`exp12...total_advantage_x`）
或独立表格脚本消费。若论文这些表要由图脚本驱动，需在 `paper_data.py` 侧补桥接（唯一允许修改的桥接文件）。

### 6.4 边界 / 隐患清单（字段契约层面，非数值）

1. **exp1 trajectory 缺 `ce` 键**：paper 路径（`real_backend.real_qad_distill_train`）每项为
   `{step,kl,drift_pct,snr_db}`。`paper_data` 读
   trajectory 只用 `kl`（plateau/converged fallback），当前不触发，但若下游依赖 paper trajectory 的
   `ce` 会取不到。
2. **exp2 `kl_task` 是 `kl_only` 深拷贝别名**：fig5a 第 5 行「KL+task」展示的实为 KL-only 重复数据，
   非独立「KL+task」测量（独立训练已移除，见脚本注释）。
3. **exp11 异常分支污染**：某 scheme 抛异常时该键变 `{f1:0.0, std:None, error}`，缺
   `accuracy`/`n_seeds`；`f1=0.0` 若被读到会污染图表（当前 int4 正常路径不受影响）。
4. **exp14 `GGUFUnavailable` 异常分支缺 `std` 且 `f1=None`**：静默落到 fallback `0.7025`/`0.007`
   —— 正是 §4.3 记录的「exp14 异常回退」边界。
5. **exp10 异常/缺配分支**：某 teacher 抛异常时变 `{f1_fixed:None,f1_conv:None,error}`；paper 路径
   config 未填某 `teacher_*` 时 `continue` 跳过 → 落到 fallback。
6. **exp6 缺 `h100_measured.domain`**：有意设计（domain-tuned alpha 未实测），
   `paper_data` 正确回退到 `paper_reference.alpha_tuned=0.86`（cited-only）。

### 6.5 渲染层坐标轴鸿沟（fig 脚本写死论文值，禁改）

真实值（调优后）绝大多数落在 fig 脚本写死的坐标轴**之外**：

| 图 | 坐标轴（写死论文值） | 真实值 | 出界 |
|---|---|---|---|
| fig3 F1 | 0.79–0.965 | QAD 0.7974 / QAT 0.6172 / Q4KM 0.7025 | QAT 出界 |
| fig4 KL / SNR | 0–0.055 / 18.2–19.0 | kl 0.346 / SNR 3.4–4.6 | 全出界 |
| fig5a F1 | 0.80–0.96 | exp2 0.5577–0.7667 | 全出界 |
| fig6a F1 / drift | 0.910–0.9265 / 0–22% | 0.8047 / 0–52.45% | 全出界 |
| fig6b F1 / PPL | 0.914–0.9245 / 8.55–8.80 | 0.80 / — | 出界 |
| fig8a F1 | 0.90–0.935 | 0.6172 / 0.8047 | 出界 |

这是独立于字段对齐的**第二层鸿沟**：即使字段契约完全对齐、真实值已回填，图表脚本按论文声称值
（0.91–0.93）写死的坐标轴也无法容纳真实值（0.56–0.80）。脚本禁改，只能靠「重跑出接近论文的值」
或「改论文结论后另立图表脚本」解决。

### 6.6 命名巧合（易误判，勿据此判断消费关系）

`paper_data.py` 中两个变量名形似 exp4/exp9，但与这两个实验**无数据对应**：
- `EXP04_OVF_LAYER_ABLATION`（fig6a）→ 实为 **exp3** 的 OV-Freeze 消融；
- `EXP09_TEACHER`（fig5b）→ 实为 **exp10** 的教师选择。
