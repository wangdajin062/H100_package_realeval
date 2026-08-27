# LoRA/Adapter + 4-bit PTQ 对照基线 — 实验设计(R4)

> **对应评审项**:R4(新颖性边界 · must_fix)中的「补充 LoRA/Adapter 微调 + PTQ 对照基线,排除替代解释」。
> **对应论文位置**:`§Experiments → Baselines`(v29.tex L488 附近)与 Table 3。
> **状态**:设计完成,待跑实验回填结果。

---

## 1. 目的与待排除的替代解释

**Devil's Advocate 的质询**(v28 评审 DA 部分):「文中未对照『直接对 BF16 0.5B 做 LoRA/Adapter 微调 + 4-bit PTQ』这一更廉价的基线,无法排除『蒸馏收益其实来自微调本身而非纯 KL』这一替代解释。」

主表已证明:QAD(F₁=0.916)> QAT(0.844)≈ PTQ(0.838)。但 QAD 训练过程本身包含在 TAF-28k 上的领域适配,因此一个合理的质疑是:收益可能来自「在领域数据上训练过」这件事本身,而非「用 KL 蒸馏」这一机制。本基线用**同样做领域适配、但用参数高效微调(PEFT)监督学习 + 后训练量化**的对照组来隔离这一变量。

**判据**:若 LoRA/Adapter + PTQ 的 F₁ 仍接近 PTQ 基线(≤ 0.85),则证明收益来自纯 KL 蒸馏;若其 F₁ 接近 0.91,则收益部分来自领域微调,需重新审视贡献主张。

---

## 2. 对照组设计(3 组)

| 组 | 训练方式 | 量化 | 预期(若纯 KL 是关键) |
|---|---|---|---|
| A. LoRA + PTQ | BF16 骨干 + LoRA(rank 8,作用于 q/k/v/o 投影)领域微调,hard-label 交叉熵 | 微调后对骨干做 NVFP4 QDQ PTQ(Eq. 5) | F₁ ≤ 0.85,接近 PTQ |
| B. Adapter + PTQ | BF16 骨干 + 瓶颈 Adapter(hidden 64)领域微调,同 CE 目标 | 同上 | F₁ ≤ 0.85 |
| C. Pure-KL QAD(ours,参照) | 纯 KL 蒸馏(主实验配置) | NVFP4 QDQ | F₁ = 0.916(已知) |

---

## 3. 控制变量(与主实验严格对齐)

| 变量 | 取值 | 说明 |
|---|---|---|
| 训练数据 | TAF-28k train split(8:1:1) | 与 QAD 同 |
| 训练预算 | ~2000 steps / ~65M tokens(或等价 token 预算) | 排除「训练更多」的混淆 |
| 量化协议 | NVFP4 QDQ(NBE,Eq. 5) | 与主实验同 |
| 评估 | TAF-28k test split,F₁/Precision/Recall/FPR/Recovery | 与 Table 3 同 |
| 随机性 | 5 seeds,mean ± std,paired bootstrap 10⁴ | 与主实验同 |
| PEFT 参数量 | 报告 LoRA rank / Adapter hidden 及可训练参数量 | 保证可复现与可比 |

**关键**:LoRA/Adapter 引入的额外可训练参数需显式报告(它们叠加在 BF16 骨干之上),以说明「收益差异」不是「参数规模差异」造成的。

---

## 4. 预期结论(写进论文时)

- **若 A/B ≤ 0.85**:纯 KL 蒸馏是收益来源,替代解释被排除;正文据此加固「pure-KL 是关键」的论断(已有 loss ablation 的独立支持:纯 KL 的 KL=0.005 vs QAT CE=0.311)。
- **若 A/B ≈ 0.91**:收益部分来自领域微调;需把贡献表述从「纯 KL 蒸馏」降级为「领域适配 + 蒸馏的联合作用」,并相应修改 R2 已完成的相关措辞。

---

## 5. 可写入论文的英文段落(Baselines 子节)

> To rule out the alternative explanation that the QAD gain stems from domain fine-tuning itself rather than the pure-KL distillation objective, we additionally compare against two parameter-efficient fine-tuning (PEFT) baselines that perform supervised domain adaptation on TAF-28k before post-training quantisation: (i) **LoRA** (rank 8, applied to the attention projection layers) fine-tuned with a hard-label cross-entropy objective, followed by NVFP4 QDQ post-training quantisation; and (ii) a bottleneck **Adapter** (hidden size 64) trained identically, followed by the same NVFP4 quantisation. Both baselines use the same training budget (~2000 steps / ~65M tokens), the same quantisation protocol (Eq. (5)), and the same five-seed evaluation as the QAD pipeline. If fine-tuning alone were responsible for the QAD advantage, these baselines would match the QAD accuracy; instead, they attain F₁ = [X] (LoRA) and F₁ = [Y] (Adapter), versus QAD F₁ = 0.916 and PTQ F₁ = 0.838, confirming that the pure-KL objective, rather than domain adaptation per se, is the source of the recovery.

>（结果 [X]/[Y] 待实验回填;若回填值与 PTQ 接近,则本段论断成立,否则需按第 4 节第二种情形改写。)

---

## 6. 落地清单

- [ ] 实现 LoRA(rank 8)+ CE 微调脚本
- [ ] 实现 Adapter(hidden 64)+ CE 微调脚本
- [ ] 对齐训练预算与主实验(~2000 steps)
- [ ] 对微调后骨干执行 NVFP4 QDQ PTQ(Eq. 5)
- [ ] 5 seeds + paired bootstrap,产出 F₁/Precision/Recall/FPR/Recovery
- [ ] 回填 Table 3 两行 + 英文段落结果
- [ ] 同步更新 revision letter 的 R4 状态(planned → done)
