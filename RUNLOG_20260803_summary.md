# RUNLOG 2026-08-03 汇总（修复 + 跑测，按时间）

> 本日完整工作链：同步容器产物 → 代码修复（CoT + F1 调优）→ 容器清理 → 全量跑测（14 实验）→ 结果回拉。
> 时间均为 UTC；本地 = UTC+8。

## 时间线

| 时间 (UTC) | 事件 |
|---|---|
| 00:33 | RUNLOG 早先收尾：exp5/8/10 中断（Pod container not found），GGUF 导出为 f16 |
| 08:15 | **全量 pipeline 启动**（`paper_pipeline --paper`，PID 4537），14 实验顺序跑 |
| 08:38–09:21 | exp1/exp4/exp11/exp2 结果落盘 |
| ~10:00–11:00 | **同步容器产物到本地**：results 4 JSON + logs 10 个 + models/exp1_qad + GGUF 994MB + audit/archive（全部 sha256 校验） |
| 10:38–10:39 | 容器上生成 exp9.patch / real_backend.patch（exp9 CoT 方法论重做） |
| ~10:45 | git pull 7 个远端提交（exp1 F1 多 seed、OVF 修正、PeftModel 加载、LDP 等） |
| ~11:00–12:00 | **代码修复**：exp9 CoT 头分支移植 + F1 调优 WIP bug 修复（详见下） |
| 13:12–13:17 | exp3/8/6/7/5/13/12 结果落盘（exp3 最长 ~3.9h） |
| 14:27 | exp10 落盘（1.5B/3B/7B 教师训练 ~1.1h） |
| **14:32** | **pipeline 完成**：exp9/exp14 落盘 + all_experiments.json + metrics/表格 |
| ~14:35 | 全部 14 实验结果回拉本地（sha256 校验通过） |

## 修复记录（均已提交 GitHub，远端 main=`cc0459c`）

| commit | 内容 |
|---|---|
| `9c8ff5c` | 新增 `scripts/sync_from_runpod.py`：RunPod 经 base64-PTY 分块同步回本地（sha256 校验，scp 不可用） |
| （pull 7 提交） | 307c679 系统重构、3268f97 exp1 F1 多 seed、b15b7e3 QAD 评估路径、f67663c OVF 混淆修正、a9e5db6 LDP+PeftModel、5cf9c86 exp5 适配 |
| `3c3df69` | 抑制 bitsandbytes MatMul8bitLt 警告刷屏（同步容器改动） |
| `1549499` | **F1 调优 + exp9 CoT 重做**：双层分类头(128)+Kaiming/Xavier、label smoothing 0.1、cosine LR warmup、阈值校准（val_frac 0.15 + `_best_f1_threshold` + ckpt 存阈值）；exp9 with/without CoT 双分支都用微调模型+头；real_backend 微调头路径 `use_cot` 分支（先推理后打分）；config 新键 |
| `7bf093d` | 修复 NameError：LR scheduler 移到 `actual_batches_per_epoch` 定义之后 |
| `cc0459c` | 修复 head 加载：`real_llm_classify` 按 state_dict 检测双层/单层头，兼容旧 ckpt |

**其他**：容器清理（删 6 个 8/2 旧日志 ~7MB + `.ipynb_checkpoints/`；保留 experiments.log/GGUF/权重）。

## 全量跑测结果（14:32 落盘，`h100_real_qwen`）

| 实验 | 关键 F1 | 说明 |
|---|---|---|
| exp1 (QAD 蒸馏) | **0.5121** | acc 0.6996，std 0.1826，5 seed，int4 |
| exp2 (损失消融) | kl_only 0.5577 / mse=ce 0.7667 | KL 同架构蒸馏弱于 CE/MSE |
| exp3 (OV-Freeze) | 各条件 **均 0.5121** | ⚠️ 所有条件 drift=0.0，**OVF 消融未响应**（异常） |
| exp4 (基线) | qwen_base 0.9061 / mlp 0.9488 / logreg 0.9342 | ChiFraud 平衡集 |
| exp5 (跨数据集) | taf28k 0.6647 / chifraud 0.6298 | 泛化尚可 |
| exp6 (投机解码) | **NOT MEASURED** | ⚠️ H100 实测 alpha 0.468 ≠ paper 参考 0.78，verdict 未测 |
| exp7 (隐私) | PII: email 0 / phone 101 / id_card 3 | speaker_id/ASV 指标已出 |
| exp8 (延迟) | bf16 27ms / int4 47ms / int8 133ms | 批量基准 |
| exp9 (CoT) | with_cot **0.035** / without_cot 0.6172 | ⚠️ with_cot 仍是 base-generate 假象（旧代码，CoT 重做未进本轮） |
| exp10 (教师尺度) | 0.5B 0.9149 / 1.5B 0.5116 / 3B 0.7676 / 7B 0.7038 | ⚠️ 0.5B 教师(0.91) >> QAD 学生(0.51)，且尺度非单调（异常） |
| exp11 (量化) | fp16 0.5328 / int8 0.5441 / **int4 0.6172** / nf4 0.3117 | int4 最优 |
| exp12 (Fusion 对比) | QAD_MultiGuard_INT4 **0.0603** | ⚠️ 异常低 |
| exp13 (融合策略) | late_fusion **0.9275** / early 0.7164 / hybrid 0.6939 | late 最优 |
| exp14 (GGUF) | bf16 **0.1609** / q4km **0.0014** | ⚠️ 严重回退（RUNLOG 8/2 曾 0.59/0.70） |

## ⚠️ 异常与待处理

1. **exp3 OVF 消融失效**：所有条件 drift=0.0、F1 相同——OVF 响应未测出，需排查（Fig.7a 依赖此结果）。
2. **exp14 严重回退**：bf16 0.16 / q4km 0.0014 vs 8/2 的 0.59/0.70——需查 head.pt/评估路径是否被 F1 调优改动破坏（本轮用旧代码跑的，但 exp1_qad 模型可能被覆盖）。
3. **exp12 QAD_MultiGuard 0.06**：异常低，需查。
4. **exp6 未测**：H100 实测 alpha 与 paper 参考不一致。
5. **exp9 with_cot 假象**：0.035 仍是 base-generate（本轮加载旧代码）；**CoT 重做需容器 pull 后重跑**才有真实数字。
6. **F1 调优未验证**：阈值校准/双层头改动从未在 GPU 跑过——需容器 `git pull` 后重跑 exp1，验证 F1 是否从 0.51 提升。
7. **exp10 0.5B 教师 (0.91) vs QAD 学生 (0.51)**：架构同源却差 0.4，方法学上需说明或排查。

## 容器状态（14:32 后）

- 训练进程 PID 4537 已结束，全部交付物（results/metrics/tables/CSV）落盘。
- 容器 git HEAD=5362b59（落后 GitHub `cc0459c`），**待训练结束后 `git pull` 对齐**。
- 保留文件：`experiments.log`、audit.log、export_gguf*.log、`exp1_qad_q4km.gguf.f16`(949M)、26G 模型权重。
