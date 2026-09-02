# 实验脚本 ↔ 论文实验设计 一致性审计（A 路修订落地后）

> **日期**：2026-09-02
> **范围**：A 路 six must_fix（R1–R6）修订全部落地后，核对三线一致性 —— (1) 实验脚本、(2) 论文实验设计（`docs/v29.tex`）、(3) 结果文件（`outputs/results/`）。
> **方法**：静态核对（脚本源码 + 结果文件落盘状态 + v29.tex 全文），不运行 GPU/H100 实验（本机无数据/权重/GPU）。
> **口径**：诚实优先 —— 论文不得宣称尚未产出的测量；「补端到端证据」≠ 把「代码已就绪但未跑」的数字当作「已测得」写入正文。

---

## 一、核心发现（MAJOR，已修复）：proxy vs 真实 $\bm{F}_v$ 自我矛盾

A 路 R2 的**文本**修订此前把 §6.2 speaker-ID 段写成「MLP 直接训练在拼接后的真实 $\bm{F}_v$（64-FBANK ⊕ 64-Whisper-投影）上」，与 §sec:acoustic 第 410 行既有诚实口径**直接矛盾**：

| 落点 | 措辞 | 语义 |
|---|---|---|
| v29:410（2026-09-01 诚实降级，未动） | 「the released experiments evaluate its two components through their respective **proxy embeddings** … rather than through the **jointly trained concatenated** $\bm{F}_v$, whose end-to-end construction … remain part of the ongoing reproduction effort」 | 实验用**代理嵌入**，真实拼接 $\bm{F}_v$ 尚未端到端评估 |
| v29:855（A 路 R2 编辑，现已回退） | 「was trained directly on the **$128$-dim acoustic embeddings (the concatenation of the 64-dim FBANK and 64-dim Whisper-projection, Eq. f-v)**」 | MLP **训练在真实拼接 $\bm{F}_v$** 上 |

**矛盾性质**：前者说「从未用拼接 $\bm{F}_v$ 评估」，后者说「就是用拼接 $\bm{F}_v$ 训练」—— 二者互斥。且后者与事实不符：落盘的 `data/ChiFraud/chifraud.npz` 是 `build_audio_npz.py` 产出的 **20 维 DCT-MFCC 时序平均后 tile 到 128** 的代理嵌入（无 FBANK、无 Whisper、无投影），并非 $\bm{F}_v$。

**已修复（v29.tex）**：
- 第 855 行回退为：`was trained on the 128-dimensional proxy acoustic embeddings (temporally averaged 20-dimensional MFCC features tiled to 128 dimensions) … the end-to-end speaker-identification evaluation of the jointly trained concatenated F_v (Eq. f-v) remains part of the ongoing reproduction effort (Section sec:acoustic)`。
- 第 857 行回退：`temporal FBANK averaging` → `temporal MFCC averaging`（代理是 MFCC，非 FBANK）。

修复后第 855/857 行与第 410/420 行（MFCC temporal averaging / proxy）口径统一。注意：**这一回退不是「降级」，而是纠正过度声明** —— 真实 $\bm{F}_v$ 的 speaker-ID/ASV-EER 数字要等 H100 产出 `chifraud_fv.npz` 并重跑 exp7 后才能写回正文（见 §三）。

---

## 二、six must_fix 逐条一致性状态

| 项 | 代码 | 文本（v29.tex） | 数字 | 一致性结论 |
|---|---|---|---|---|
| **R1** 可复现 QAD + sha256 | ✅ `cluster/reproduce_qad.py`（同 exp1 代码路径 + 固定 seed + `_sha256_dir`） | ✅ 无新宣称（R1 是流程项） | ⏳ `repro_manifest.json` 未产出 | 代码与设计一致；数字待 H100 |
| **R2** 真实 $\bm{F}_v$ 端到端 | ✅ `acoustic_embedding.py` + `build_chifraud_fv.py` + exp7 接线（`chifraud_fv.npz → taf28k_fv.npz → chifraud.npz(proxy)`） | ✅ 第 855/857 已回退为诚实代理口径（本次修复）；表 4 ASV-EER 注保留 | ⏳ `chifraud_fv.npz` 未产出 → exp7 当前仍回退到 proxy；表 4 数字仍是 proxy 值 | 代码与设计一致；数字待 H100，正文**不得**先宣称真实 $\bm{F}_v$ 已测得 |
| **R3** 单模态消融 | ✅ `exp15_modality_ablation.py` + 合约字段（`text_only`/`audio_only`/`fused`/`marginal_contribution`） | ⚠️ Discussion 第 908 行仍写「single-modality baselines are not reported … left to future work」—— 与「已补 exp15」形成文本滞后 | ⏳ 无 exp15 结果文件 | 代码就绪；数字 + 文本需在 H100 跑出后同步更新 |
| **R4** 四模态→双模态诚实化 | —（纯文本） | ✅ 2 处（Tier-3 融合段 + §4.5 fusion weights） | — | 已对齐 |
| **R5** 删合规宣称 | —（纯文本） | ✅ 6 处（privacy-oriented / motivated by / data-minimisation practices） | — | 已对齐 |
| **R6** 陈述部署模型 | —（纯文本） | ✅ 2 段（§sysarch Deployment model + Discussion Deployment-model limitation） | — | 已对齐 |

---

## 三、结果文件 vs 实验设计（数字 ⏳ 清单）

当前 `outputs/results/` 仅含 2026-08-13 的陈旧文件：

```
outputs/results/all_experiments.json          # 仅 exp1
outputs/results/exp1_20260813_105315.json
outputs/results/exp1_20260813_110527.json     # error 文件
outputs/results/integration_test_20260813_105308.json
outputs/results/test_exp_20260813_105312.json
```

**缺失的全部 A 路产物**（需在 GPU 上运行 `reports/2026-09-02_a_road_execution.md` §三 命令清单）：

| 产物 | 产出命令 | 论文对应落点 |
|---|---|---|
| `data/ChiFraud/chifraud_fv.npz`（真实 $\bm{F}_v$，`embedding_kind=fv`） | `build_chifraud_fv.py --w-proj …` | 支撑 §6.2 speaker-ID 写回真实 $\bm{F}_v$ 数字 |
| exp7 真实 $\bm{F}_v$ 重跑（GLO `glo_is_demo=False` + speaker-ID/ASV-EER） | `runner --exp 7 --paper` | 表 4 六行数字的最终替换源 |
| `outputs/models/exp1_qad/repro_manifest.json`（sha256 + commit + F1≈0.923） | `cluster/reproduce_qad.py` | R1 可复现声明 |
| exp15 消融结果（`text_only`/`audio_only`/`fused`/marginal delta） | `runner --exp 15 --paper` | R3；随后更新 Discussion 第 908 行 |

**关键结论**：在以上数字落盘之前，论文正文**不能**写「真实拼接 $\bm{F}_v$ 已被端到端评估」（本次已回退第 855/857 行正是为此）；表 4 现有数字的诚实口径仍是「代理嵌入 + reference estimates」（第 849 行已如实标注）。

---

## 四、遗留不一致（非本轮 six must_fix，建议跟进）

1. **line 265「empirically achieves WER ≥ 0.95」**：威胁模型句目前沿用 0.95。真实 $\bm{F}_v$ 的 WER 跑出后需对齐。诚实结论已定：**隐私来自时均（FBANK 半段）摧毁时间动态，而非投影不可逆** —— GLO 对 FBANK 半段的恢复 corr 收敛到 ~1.0（`fbank_identity_proj_fn` 恒等映射）。此句是唯一需要在 H100 后核对是否仍成立的威胁模型表述。

2. **W_proj 训练来源**：`w_proj.npy` 无训练来源（fig2 用随机示意）。`build_chifraud_fv.py` 用固定 seed 随机正交 `W_proj` 作 fallback。若论文坚持「trained acoustic head」需补训练脚本；否则应将 W_proj 描述为「frozen/seeded projection」与 provenance 一致。

3. **LDP sensitivity 死配置**：[config/experiments.yaml:77](config/experiments.yaml#L77) `privacy.sensitivity: 1.0` 与 [realeval/privacy.py](realeval/privacy.py#L291) `gaussian_ldp` 内部 `sensitivity = 2.0 * clip_bound`（=6.0）不一致 —— 该字段是死配置，`gaussian_ldp` 仅被单测调用，exp5 走未裁剪 `noise_sigma` 路径。修 S12（ε=1.5 措辞）时一并删除或激活该字段。

4. **R4 讨论段第 908 行**：`Modality-contribution limitation` 现写「single-modality baselines are not reported … left to future work」，与已落地的 exp15 冲突。exp15 跑出数字后，该段应从「future work」改为「reported in Section X（引用 exp15 结果）」，并据此校准「acoustic branch is secondary contributor」的强度。

---

## 五、结论

- **三线一致性已收敛到可投稿口径**：脚本层（R1–R3 代码）与论文设计层（R4–R6 文本）均已落地；本次审计修复了唯一一处由 A 路文本编辑引入的**过度声明**（proxy vs 真实 $\bm{F}_v$ 自我矛盾），使第 855/857 行与第 410 行诚实口径重新统一。
- **「数字 ⏳」仍是投稿前的硬门槛**：表 4（speaker-ID/ASV-EER/GLO 真实 $\bm{F}_v$）、R1 sha256、R3 消融、Discussion 第 908 行 —— 均依赖 H100 重跑，本机无法验证，需在 `reports/2026-09-02_a_road_execution.md` §三 命令清单执行后回填。
- **诚实红线保持不变**：在数字落盘前，论文不得宣称「真实拼接 $\bm{F}_v$ 已被端到端评估」；现有表 4 数字继续以「代理嵌入 + reference estimates」口径呈现（第 849 行）。
