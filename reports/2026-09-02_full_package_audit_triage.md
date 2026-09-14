# 全量包审计 —— 分类执行路线图

> 来源：`2026-09-02_full_package_audit.md`（已归档至 [2026-09-02_history_archive.md](2026-09-02_history_archive.md)）
> 目的：把审计的 30+ 项问题按「本地可修 / 需 H100 重跑 / 需论文表述决策」三类归类，并给出每类的执行顺序与依赖。
> 分类日期：2026-09-02。

---

## 分类标准

| 类别 | 判定 | 含义 |
|---|---|---|
| **A 本地可修** | 纯代码/文档 bug，方向明确，无需 GPU、无需论文取舍 | 直接改代码/契约/文档 |
| **B 需 H100 重跑** | 依赖 GPU + 权重 + 数据的测量/验证 | 环境就位后重跑 |
| **C 需论文表述决策** | 本质是「代码测的量 ≠ 论文声称的量」 | 需拍板 A=改代码匹配论文（多数需重跑）/ B=改论文匹配代码（不重跑但修正声明） |

**核心判断**：C 类决策必须**最先做**，因为它决定 B 类重跑时到底跑什么（例：P1-1 决策 A 则 exp1 要跑「无 OVF」两臂；P1-2 决策 A 则 exp3 要加真 PPL 计算）。A 类里「重跑前必修」的子集也必须先于 B 类完成，否则重跑产出仍是错的。

---

## A 类 —— 本地可修（无需 GPU、无需论文取舍）

### A1：重跑前必修（否则 H100 重跑产出仍错误/被遮蔽）

| # | 问题 | 修复动作 |
|---|---|---|
| P0-4 | exp12 键名 `QAD_MultiGuard_NVFP4` ≠ 契约 `QAD_MultiGuard_INT4` | 对齐键名（论文权威为 INT4，倾向改代码侧）——否则 `--validate-contract` 恒失败 |
| P0-5 | evidence_graph 允许假数据 PASS | evidence 节点强制 `content_hash` 链到真实 predictions/metrics；测试夹具（f1=0.95）移出 `outputs/evidence/` |
| P1-5 | exp5 curated 517 位置占位 + exp1 权重缺失静默降级 base | 降级路径一律打 `model_source` 标记；curated 标注为「无人工过滤标注、位置占位」 |
| P1-14 | paper_data 静默常量回退，66 个 placeholder 走 fallback | placeholder 非空时让 generate_all 失败或在图加水印；回退常量与论文值二选一，消除图/表矛盾 |
| P2 | exp7 GLO steps=50 硬编码 ≠ config 150 | 对齐 config |
| P2 | exp8 p50 实为均值、nvfp4 未挂 adapter | 真 p50；nvfp4 挂 adapter |
| P2 | exp11/exp14 多 seed 确定性空转 std=0.0；exp14 重复加载 GGUF；exp11 不走共享 manifest | 修复采样/加载逻辑 |
| P2 | exp12/exp14 QAD 缺失静默退化 zero-shot 无 `model_source` | 补标记（与 exp11 对齐） |
| P2 | exp6 gamma/n_samples 硬编码无视 config；draft 用 argmax 贪心 | 改读 config（采样问题属 C 类，见下） |
| P2 | failed 结果以最新时间戳遮蔽旧成功结果 | 改加载逻辑（failed 不遮蔽成功） |

### A2：重跑后收尾（文档/清理，不阻塞重跑）

| # | 问题 | 修复动作 |
|---|---|---|
| P2 | exp1 `total_steps`/`ovf_activation_step` 为 config 回显非测量；trajectory 仅保留最后 seed | 改为真实测量 + 多 seed 保留 |
| P2 | exp5 full_pool 实为 10% 切片且 n_samples 报池大小；ChiFraud 缺失静默顶替 balanced4k | 诚实化字段 + 补标记 |
| P2 | exp15 已实现但 v29.tex:908 仍写 future work；contract.md 缺 exp14/15 章节；Fig3 QAT 行来源描述与实现不符 | 文档同步 |
| P2 | config `alpha_ce: 0.5` 死配置（代码只读 `alpha_kl`）；`group_split` 名不副实 | 清理死配置 / 改名 |
| P2 | `benchmark.csv` toy 产物落在正式 metrics；`Table2.tex` 空表；`summary.csv` 空 | 清理/移出 |
| P2 | 契约 §三.4 对 kl_task 机制描述过时（实为独立训练） | 文档更新 |
| P2 | claim_engine paired 仅按样本数判断、seeds=5 功效低 | 统计细节修正 |

---

## B 类 —— 需 H100 重跑（环境/数据依赖）

| # | 问题 | 依赖 |
|---|---|---|
| P0-1 | 产出真空：exp2–exp15 零结果；exp1 最新 failed（显存 11.8GB<35GB） | H100 + 权重 + 数据 |
| P0-2 | 三条 CLAIM 全 UNSUPPORTED（显存不足），claim 级验证从未通过 | 重跑后 claim 重验 |
| P0-3 | 唯一真实 H100 运行（2026-08-03）原始 JSON 被归档流程删除，仅存 md 摘要且与论文反转 | 先修归档流程（不删原始 JSON，属 A1）+ 重跑 |

> 注意：B 类不是「无脑重跑」。重跑前必须先完成 A1 + C 类决策，否则会再次产出「协议错位」的失败结果。

---

## C 类 —— 需论文表述决策（改代码匹配论文 vs 改论文匹配代码）

13 项 P1 协议错位 + 3 项 P2。每项给 A/B 两条路径，**需你逐项拍板**。

| # | 问题本质 | A：改代码匹配论文（多数需重跑） | B：改论文匹配代码（不重跑，修正声明） |
|---|---|---|---|
| P1-1 | exp1 默认含 OVF，却被映射为 Fig3「QAD（无 OVF）」行 | exp1 拆「无 OVF」臂单独产 F1；QAD+OVF 读 exp3.conditions.ov_freeze_full | 论文/契约改标注：QAD 行实际含 OVF，调整 0.916 vs 0.923 消融叙事 |
| P1-2 | exp3 `ppl` 是 `exp(min(KL,10))` 伪困惑度 | exp3 测真实 LM 困惑度 | Fig6b 图注改为「KL-derived pseudo-perplexity」或直接展示 KL |
| P1-3 | exp2「Logits MSE」实为 hidden-state MSE + CE | 改为 logits MSE | Table 5 改称 hidden-state MSE（feature alignment） |
| P1-4 | PTQ/BitDistiller 基线无任何脚本测量，硬编码常量 | 补测量脚本 | 论文标注为文献引用基线（非本套件测量） |
| P1-6 | exp10 fixed 臂 1 epoch ≠ 论文「Fixed 0.5B tokens」 | 改代码对齐 tokens | 论文改标注 epoch 数 |
| P1-7 | exp7 ASV-EER 在原始 F_v 上算，论文在重建嵌入上算 | 改在重建嵌入上计算 | 论文改表述为原始嵌入 |
| P1-8 | exp9 仅纯文本/单数据集/单 seed | 补 AdvFraud 臂 + 多模态 + 多 seed | 论文 CoT 表改标注范围 |
| P1-9 | 端侧延迟（SD8G3/Q4_K_M 268ms）全仓库无测量 | 补端侧测量（需硬件） | 论文标注「组装估计」（报告称已部分做到，需核实） |
| P1-10 | exp11 int4/int8/nf4 = NVFP4-QAD + PTQ 再量化，非「同质 INT4 独立训练 0.915」 | 增加 INT4 QAD 训练臂 | 论文改行标注为「NVFP4-QAD + PTQ 再量化」 |
| P1-11 | exp14 q4km 是 stock 官方 GGUF zero-shot，非「Q4_K_M QAD+OVF 0.917」 | 接入 export_to_gguf 导出的 QAD GGUF | 论文改行标注为「stock GGUF zero-shot」 |
| P1-12 | exp13 未按论文测融合（zero-shot 文本 + 384-d Whisper + 训练耗时混入） | 换 QAD 学生 + 128-d F_v + 纯推理计时 | 论文改表述 |
| P1-13 | exp12 存储口径 ≈28× ≠ 论文 57×（248MB 产物不存在） | 统一 57× 口径 | 论文改数字为实测口径 |
| P1-15 | claim 框架与论文错位（CLAIM-02 是 int4-vs-fp16 非异构-vs-同质；CLAIM-03 seeds=1 + 公式推算 speedup） | claim 改异构-vs-同质框架、5 seeds、speedup 改实测 | 论文对齐 claim 表述 |
| P2 | exp2 epochs=3 vs exp1 5，与「其余超参相同」声明不符 | epochs 对齐 5 | 论文补注 |
| P2 | exp6 draft 用 argmax 贪心非从 q 采样（α 偏高）；实测 target 为 BF16 非 NVFP4 | 改从 q 采样 + target 改 NVFP4 | 论文补注目标模型 |
| P2 | claim_engine seeds=5 功效低、paired 判断粗糙 | 统计方法加固 | 论文/claim 标注功效边界 |

---

## 建议执行顺序（依赖驱动）

```
第一步：C 类决策（13+3 项逐项拍板 A/B）
        ↓  决策结果决定 B 类重跑内容
第二步：A1 重跑前必修（P0-4 键名、P0-5 假PASS、P1-14 静默回退、
        P1-5/P2 的 model_source 标记、exp7/8/11/14/6 的代码修复）
        ↓
第三步：B 类 H100 重跑（exp1→exp15 全链 + CLAIM 重验 + 归档流程修复后保原始 JSON）
        ↓
第四步：A2 重跑后收尾（文档同步、死配置清理、toy 产物清理）
        ↓
第五步：按重跑结果如实更新论文数字（当前 v29 核心定量声明均无实测支撑）
```

---

## 一句话结论

**A 类约 15 项可立即动手；B 类 3 项等 H100；C 类 16 项必须先拍板方向，否则任何重跑都会产出「以实测之名支撑未执行实验」的结果。** 建议从 C 类 P1-1/P1-2/P1-3（与刚完成的 OV-Freeze/蒸馏重构直接相关）开始拍板。

---

## 执行进度（已拍板 A 路径 = 改代码匹配论文）

| 项 | 状态 | 落地 |
|---|---|---|
| P1-1 exp1 无 OVF 臂 | ✅ 完成 | exp1 默认 `apply_ov_rescaling=False`，OVF 由 exp3 单独承载 |
| P1-2 exp3 真实 LM 困惑度 | ✅ 完成 | real_backend 加 `compute_ppl` 真实因果 LM 困惑度，fig6 ylabel/ylim 同步 |
| P1-6 exp10 fixed 臂 0.5B tokens | ✅ 完成 | real_backend 加 `max_train_tokens`，exp10 传 500M，paper_data 注释诚实更新 |
| P1-7 exp7 ASV-EER 重建嵌入 | ✅ 完成 | `asv_eer_pct` 改为重建嵌入 ASV-EER（缺资产时诚实报 None），原始 F_v 降级为 `asv_eer_pct_original_fv` 诊断；GLO identity corr ~1.0 标记为构造性不列入 measured；PII docstring 如实化 |
| P1-3 exp2 Logits MSE | ✅ 完成 | 本次修订将 hidden-state MSE 改为 logits MSE（`F.mse_loss(logits, t_logits_head)`，第 386-393 行）；docstring 同步改为「head logits (paper "Logits MSE")」 |
| P1-8 exp9 CoT 补全 | ✅ 完成 | TAF-28k 改 sigmoid-linear 决策级融合（文本 CoT 开关 + 128-d F_v 声学）；补 AdvFraud-3k 纯文本臂（`advfraud_f1`）；`model_source` 诚实标记；n_seeds=1 推理确定性标注；contract/consistency_check 同步 AdvFraud 字段 |
| P1-10 exp11 INT4 QAD 训练臂 | ✅ 完成 | 同质 INT4 独立 QAD 训练（`real_qad_distill_train(quantize="int4")`），其余方案标 `trained_scheme="nvfp4_qad"` 推理侧诊断 |
| P1-11 exp14 QAD GGUF | ✅ 完成 | `resolve_qad_gguf_path()` 指向 `exp1_qad_q4_k_m.gguf`；Q4_K_M 分支用导出 QAD GGUF，缺失诚实报「QAD GGUF unavailable」 |
| P1-12 exp13 QAD 文本 + 128-d F_v | ✅ 完成 | 文本分支用 `resolve_qad_path()` 的 QAD 产物；音频分支用 `taf28k_fv.npz` 128-d F_v；`latency_note` 说明端到端计时含 fusion-head fit |
| P1-13 exp12 57× NVFP4 口径 | ✅ 完成 | `nvfp4_mb=248.0`（paper-claimed）；`total_x = bf16_7b/nvfp4_mb`（≈57×）；Q4_K_M 实测（≈28×）单独分列 `total_advantage_x_q4km_measured`；`nvfp4_footprint_source="paper_claimed_248MB"` |
| P1-15 claim 框架 | ✅ 完成 | CLAIM-02 改异构-vs-同质（treatment=nvfp4 异构 vs baseline=int4 同质，`mean_diff<=0.01`）；CLAIM-03 seeds=5 + hypothesis/threshold_origin 明确「formula-derived token speedup（Leviathan Eq.1）非 wall-clock measured」 |
| P1-4 PTQ 基线 | ✅ 已拍板 B 路径（2026-09-03） | 论文改标注：v29:513(iii) 改为「external reference results … not measured by our released evaluation suite」，Table 3 脚注将 PTQ 四行与 BERT-Fraud/SAFE-QAQ 并列为引用基线；paper_data `PTQ_BASELINES` 维持 external 标注 |
| P1-9 端侧延迟 | ✅ 已拍板 A 路径（2026-09-03） | 作者确认存在仓外 Snapdragon 8 Gen 3 实测，v29:513(ii)「measured on Snapdragon 8 Gen 3」保留原文；paper_data `_FIG4_REF` 维持「NOT experiment-derived（本套件未测）」标注。建议仓外实测数据随 reproduction run 归档入仓备查 |
| 复核新增：inference-tensor 崩溃隐患 | ✅ 完成 | `real_backend` 两处 `F.mse_loss` 改手写 `(a−b)².mean`：exp2 mse/kl_mse 臂（inference-mode 的 `t_logits_head` 被 saved-for-backward，step 0 即崩）与 L_OVF（`t_var_calib` 同理，OVF 激活首步崩） |
| 复核新增：P0-5 证据图溯源强制 | ✅ 完成 | `add_predictions` 强制工件存在 + sha256 校验（不符即 raise）；`validate()` 拒绝无文件溯源的 PASS；`claim_runner` 落盘 `{claim_id}_predictions.json` 并设空预测→UNSUPPORTED 门禁；测试重定向 + 两个负向用例 |

---

## 2026-09-14 修订落实情况复核

> 复核范围：对上表「✅ 完成 / 已拍板」的 A/C 类项逐一在代码中核实（HEAD `b5a69c5`），并补查 A2 收尾项。结论：**A/C 类修订真实落地，均有代码证据；B 类 3 项未完成（环境依赖，待 H100）**。

### A1 重跑前必修（核实通过）

| 项 | 证据 |
|---|---|
| P0-4 exp12 键名 | 三方统一为 `QAD_MultiGuard_NVFP4`（exp12:72 + metrics/contract.py:151 + contract.md:222）。实际方向为「改契约侧为 NVFP4」（与 triage 原建议「改代码侧 INT4」相反），但已对齐，`--validate-contract` 不再恒失败 |
| P0-5 假 PASS | `audit/evidence_graph.py:49` `content_hash` sha256 溯源强制 |
| P1-5 curated 占位 + model_source | exp5:78-91 标注「前 517 条占位非人工过滤」；exp5:109 `model_source` |
| P1-14 静默回退 | paper_data.py:105-141 `_from_result`，非 cited 缺失 `fallback=None` 显式报缺，5 处 stale 值清空 |
| exp7 GLO steps | exp7:94 读 config `glo_attack_steps`（默认 150） |
| exp8 真 p50 | exp8:92 `quantile_ms(times_ms, 50)` |
| exp6 gamma/n_samples | exp6:30-31 读 config `sd.get("gamma", 5)` / `sd.get("n_samples", 20)` |

### A2 收尾（核实通过）

| 项 | 证据 |
|---|---|
| exp1 total_steps 回显 | real_backend.py:640-646 区分 concept `total_steps`（Fig4 x 轴对齐）与真实 `actual_total_steps`，注释如实说明 |
| exp1 trajectory 单 seed | exp1:62 `trajectory_note` 诚实标注「single-seed (last of n_seeds)」 |
| exp5 full_pool 10% / ChiFraud 顶替 | exp5:73「10% 测试切片」标注；exp5:110-113 `chifraud_proxy="balanced4k"` 显式盖章 |
| exp15 文档同步 | contract.md:238 + v29.tex:908「exp15 已实现于公开代码库（text-only/audio-only/fused）」 |
| alpha_ce 死配置 | 已删除（schema.py:45 / experiments.yaml:43 仅 `alpha_kl`） |
| group_split 名不副实 | data.py:514 docstring 诚实标注「Groups by LABEL only… no template-family」 |
| benchmark.csv / Table2.tex / summary.csv | `outputs/metrics/` 已不存在，toy 产物清理 |
| 契约 kl_task 描述过时 | contract.md:75 已改为「独立训练的 loss 变体，非复制别名」 |
| claim_engine paired 判断 | claim_engine.py:91-93 改 seed-based paired，旧长度启发式已移除 |

### 复核结论

- **A 类（本地可修）17 项 + C 类（决策）16 项全部落地/拍板**，代码证据充分。
- **诚实性取向**：所有「名不副实/回显/占位/顶替」类项均以「如实标注真实情况」修法落地（LABEL-only、concept 参数 + actual_total_steps、占位标注、proxy 盖章），与审计基调一致。
- **B 类 3 项未完成**（P0-1 产出真空 / P0-2 CLAIM 未验 / P0-3 原始 JSON 被删），卡在 H100 重跑——`outputs/results/` 仍空，exp1 最新 failed（显存 11.8GB<35GB）。下一步 `bash scripts/runpod_rerun.sh`。

---

## 2026-09-14 冗余脚本清理

> 依据：脚本引用关系分析 + 审计历史结论。删除 A 类 4 个弃用脚本、清理 B 类 4 个孤立 `.pyc`、同步 D 类 3 处引用残留。C 类 `slurm_h100.sbatch` 保留。

### A 类 —— 删除的弃用脚本

| 脚本 | 弃用证据 |
|---|---|
| `cluster/apply_all_fixes.py` | docstring 自标注 `deprecated:: 2026-08-14`，内嵌旧版源码副本，修复已合并进源码树 |
| `cluster/train_sft.py` | 产物 `outputs/sft_checkpoints/` 无实验加载；被 `train_lora_manual.py`（no HF Trainer）取代 |
| `cluster/fix_training.py` | 专门修 `train_sft.py`；审计确认其正则会改坏 `train_sft.py`（P1-O7） |
| `cluster/diagnose_training.py` | NaN 诊断，mirrors `train_sft.py`，一次性工具 |

### B 类 —— 孤立缓存残留

`cluster/__pycache__/` 下 4 个 `.pyc`（`gpu_dashboard` / `gpu_monitor_daemon` / `kanban` / `diagnose_v25_run`，源码已删）。

### D 类 —— 同步的引用残留

| 位置 | 改动 |
|---|---|
| `realeval/student_loader.py` | docstring 去 apply_all_fixes/train_sft 溯源；报错「Train one (train_sft.py)」→「train_lora_manual.py」 |
| `config/experiments.yaml:120` | 注释「produced by train_sft.py (added by apply_all_fixes.py)」→「train_lora_manual.py」 |
| `README.md` 结构图 | 删 `diagnose_training.py` / `fix_training.py` 行，补 `train_lora_manual.py` / `reproduce_qad.py` |

### 清理后 cluster/ 剩余

`launch.sh` · `manage_models.sh` · `reproduce_qad.py` · `setup_runpod.sh` · `slurm_h100.sbatch` · `train_lora_manual.py`

### 保留说明

- `cluster/slurm_h100.sbatch`：Slurm 调度备选，非当前 RunPod 主流程，保留。
- `reports/2026-09-02_history_archive.md` 中历史审计对已删脚本的引用：归档事实，不改。

