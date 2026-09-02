# A 路执行报告（R1–R6 must_fix 补证据，不降级）

> 日期：2026-09-02
> 范围：执行 [revision_checklist_v29_round2.md](2026-09-02_history_archive.md)（已归档）六条 must_fix 的 **A 路**选项
> 原则：**补端到端证据，不把 headline 数字降级为「不可复现/代理」**。

---

## 一、论文文本改动（已完成，[v29.tex](docs/v29.tex)）

### R5 — 删合规宣称（A 路）
6 处措辞替换，收敛为「privacy-oriented / motivated by / data-minimisation practices」，与正文已有的
「technical assessment, not legal compliance」保持一致，不再出现 `compliant / complying / mandated by / aligning with` 残留。

| 位置 | 改动 |
|---|---|
| 摘要 | `privacy-compliant` → `privacy-oriented` |
| 引言 | `while complying with` → `under constraints informed by` |
| 引言 | `privacy compliance` → `privacy preservation` |
| C1 | `mandates that acoustic processing occur on-device` → `motivates on-device acoustic processing` |
| C1 | `device boundary mandated by PIPL` → `device boundary motivated by PIPL's data-minimisation principle` |
| §sysarch | `aligning with PIPL data-minimisation requirements` → `aligning with data-minimisation practices` |

### R4 — 四模态→双模态诚实化（A 路）
2 处限定：Tier-3 融合段明确「仅 text/acoustic 权重在 TAF-28k 上经 L-BFGS 学习，URL/metadata 权重为 carry-forward
deployment parameters (Eq. w-deploy)」；§4.5「fusion weights」→「text and acoustic fusion weights」。

### R2 — 维度矛盾 + ASV-EER 改标（A 路文本部分）
- §6.2 speaker-ID 段：`128-dimensional MFCC-based` → `128-dimensional acoustic embeddings
  (the concatenation of the 64-dimensional temporally-averaged FBANK and 64-dimensional Whisper-projection
  components, Eq. f-v)`；`temporal MFCC averaging` → `temporal FBANK averaging`（与 Eq.(5) 64 维一致）。
- 表 4 加注：`ASV-EER 测于 reconstructed embeddings，量化的是重建攻击的失败程度而非 F_v 本身的说话人泄漏`。

> **2026-09-02 审计修正**：上述 R2 文本编辑把 §6.2 写成了「MLP 训练在真实拼接 F_v 上」，与 §sec:acoustic 第 410 行的诚实口径（experiments 用 proxy embeddings、拼接 F_v 端到端评估留待 reproduction）**矛盾**，且与落盘代理 `chifraud.npz`（20 维 MFCC tile-128）不符。已回退：§6.2 改回「proxy acoustic embeddings (temporally averaged 20-dim MFCC tiled to 128) + 端到端留待 reproduction」，`FBANK averaging` → `MFCC averaging`。真实 F_v 的 speaker-ID/ASV-EER 数字待 H100 产出 `chifraud_fv.npz` 后写回。详见 [2026-09-02_script_design_consistency_audit.md](2026-09-02_script_design_consistency_audit.md)。

### R6 — 陈述部署模型（A 路）
- §sysarch 新增 `\paragraph{Deployment model.}`：明确 on-device 隐私性质以「检测软件运行于数据主体终端」为前提。
- Discussion 新增 `Deployment-model limitation` 段：不分析运营商侧部署、data-controller 认定、PIPL 合法依据，
  留给「与运营商/监管方协作的部署导向工作」。

---

## 二、代码改动（已完成，全部通过 `py_compile`）

### R2 — 真实 F_v 构造 + GLO 端到端接线
新增/修改：
- **[realeval/acoustic_embedding.py](realeval/acoustic_embedding.py)**（新）— 真实 F_v 构造函数：
  - `time_averaged_fbank` / `whisper_pooled_hidden` / `build_fv_from_wav`（64-FBANK ⊕ ψ(W_proj·h̄_w)）
  - `fbank_identity_proj_fn` — GLO 的诚实 `proj_fn`：FBANK 半段以明文存储（恒等映射，攻击者可精确恢复，corr→~1.0），
    Whisper-proj 半段为逐样本常量、非 FBANK 的函数。
  - `griffin_lim_fbank` — 从时均 FBANK 反演波形（供 WER/PESQ/STOI/MOS 端到端评分）。
  - 所有可选依赖（librosa/whisper/W_proj）缺失时返回显式 `unavailable`，**绝不伪造**。
- **[data/scripts/build_chifraud_fv.py](data/scripts/build_chifraud_fv.py)**（新）— 产出真实 F_v 的
  `chifraud_fv.npz`（含 `embedding_kind=["fv"]` 溯源标记 + W_proj 来源）；speaker bucketing 与旧
  `build_audio_npz.py` 完全一致（唯一变量 = 代理嵌入 → 真实 F_v）。
- **[experiments/exp7_privacy_verification.py](experiments/exp7_privacy_verification.py)**（改）— 嵌入加载链改为
  `chifraud_fv.npz → taf28k_fv.npz → chifraud.npz(proxy)`；仅当 `embedding_kind=="fv"` 时给 GLO 传真实
  `proj_fn`，`glo_is_demo` 自动翻为 False（GLO 纳入真实测量），proxy 路径保留诚实 demo 标志。

### R3 — 单模态消融
- **[experiments/exp15_modality_ablation.py](experiments/exp15_modality_ablation.py)**（新）— 同一泄漏安全
  TAF-28k test 集上报告 text-only / audio-only / fused F1 + 边际贡献 delta。
- **[metrics/contract.py](metrics/contract.py)**（改）— exp15 字段纳入 MEASURED 合约（消融数字必须真实产出）。

### R1 — 可复现 QAD 训练 + sha256
- **[cluster/reproduce_qad.py](cluster/reproduce_qad.py)**（新）— 走 exp1 同一代码路径
  （`real_qad_distill_train`, nvfp4 QAT/NBE, pure-KL, OV-Freeze），固定 seed，产出 checkpoint 后计算 sha256 +
  超参快照 + git commit pointer，写入 `repro_manifest.json`。

---

## 三、H100 执行命令清单（需在 GPU 上运行，产出新数字）

> 前置：数据就位（`data/TAF28k/taf28k.jsonl + taf28k.npz`）、ChiFraud 音频（`data/ChiFraud/audio/`）、
> Qwen 权重、Whisper-tiny、librosa、`pesq`/`pystoi`/`jiwer`。

### R2 — 真实 F_v 端到端
```bash
# 1) 构建真实 F_v（W_proj 可先无训练：固定 seed 随机正交；若要训练 W_proj 见 §四）
PYTHONPATH=/workspace /workspace/venv/bin/python \
  data/scripts/build_chifraud_fv.py --w-proj /workspace/data/acoustic/w_proj.npy

# 2) 重跑 exp7：GLO 用真实 proj_fn（glo_is_demo=False）+ speaker-ID/ASV-EER 落在真实 F_v 上
PYTHONPATH=/workspace /workspace/venv/bin/python -m experiments.runner --exp 7 --paper --config config/experiments.yaml

# 3) 波形反演 + WER/PESQ/STOI/MOS（把重建波形写回 reconstruction.npz 供 harness 评分）
#    —— 见 acoustic_embedding.griffin_lim_fbank + exp7 的 _load_reconstruction_assets 路径
```

### R3 — 单模态消融
```bash
PYTHONPATH=/workspace /workspace/venv/bin/python -m experiments.runner --exp 15 --paper --config config/experiments.yaml
```
验收：`marginal_contribution.fused_minus_text_only / fused_minus_audio_only` 与融合权重
`w_audio=0.30 < w_text=0.40` 对齐（声学为次要贡献者时 audio-only F1 应低于 text-only，fused 略高于二者）。

### R1 — 可复现 QAD + sha256
```bash
PYTHONPATH=/workspace /workspace/venv/bin/python cluster/reproduce_qad.py
```
验收：`outputs/models/exp1_qad/repro_manifest.json` 有 sha256 + commit + F1≈0.923（容差内）。
（PTQ 侧 LoRA adapter 由既有 `cluster/train_lora_manual.py` 复现，见 §四。）

---

## 四、遗留项（非本轮 six must_fix，建议跟进）

1. **line 265「empirically achieves WER ≥ 0.95」**：A 路补端到端后，若真实 F_v 的 WER 数字 ≠ 0.95，
   需更新该威胁模型句（目前暂留原样，等 §三 R2 产出的 WER 数字对齐）。威胁模型的诚实结论是：
   **隐私来自时均（FBANK 半段）摧毁时间动态，而非投影不可逆** —— GLO 对 FBANK 半段的恢复 corr 收敛到 ~1.0。
2. **W_proj 训练**：`w_proj.npy` 目前无训练来源（fig2 用的是随机示意）。若论文坚持「trained acoustic head」，
   需补一个训练 W_proj 的脚本（Whisper-tiny 冻结 + 64×384 投影头）。否则应把 W_proj 描述为「frozen/seeded
   projection」，与 `build_chifraud_fv.py` 记录的 provenance 一致。
3. **LDP 灵敏度 config/代码不一致**（审计附注，非 must_fix）：[privacy.py:291](realeval/privacy.py#L291)
   `gaussian_ldp` 内部 `sensitivity = 2.0 * clip_bound`（=6.0，数据无关裁剪是正确做法），但
   [experiments.yaml](config/experiments.yaml) `privacy.sensitivity: 1.0` 是死配置。修 S12（ε=1.5 措辞）时
   一并处理：删掉死字段，或让字段真正生效并据此重算 ε。

---

## 五、验收判据对照

| must_fix | A 路产出 | 状态 |
|---|---|---|
| R1 可复现 | `reproduce_qad.py` + sha256 manifest（待 H100 跑出） | 代码✅ / 数字⏳ |
| R2 F_v 端到端 | `acoustic_embedding.py` + `build_chifraud_fv.py` + exp7 接线（待 H100 跑出 WER/speaker-ID/ASV-EER） | 代码✅ / 数字⏳ |
| R3 单模态消融 | `exp15` + 合约字段（待 H100 跑出） | 代码✅ / 数字⏳ |
| R4 双模态诚实化 | v29.tex 2 处 | ✅ |
| R5 删合规宣称 | v29.tex 6 处 | ✅ |
| R6 部署模型陈述 | v29.tex 2 段 | ✅ |
