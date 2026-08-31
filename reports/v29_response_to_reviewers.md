# QAD-MultiGuard — Response to Reviewers(修订说明)

> **论文**:QAD-MultiGuard: An Edge–Cloud Framework for Multimodal Fraud Detection and Risk Assessment
> **目标期刊**:Expert Systems with Applications(ESWA)
> **决策**:Major Revision(模拟评审,`academic-paper-reviewer` v1.11.1)
> **修订版本**:`v28.tex` → `v29.tex`
> **性质**:模拟修订说明。状态标注区分「已完成 / 部分完成 / planned(待实验回填)」,不虚构未做的实验。
> **日期**:2026-08-27

---

## 总述(Summary of Changes)

本次修订针对综合决策意见的 **R1–R4(必须修改)** 与 **S1–S4(建议修改)** 进行。已落地的文本修订聚焦于 **R2(主张收敛)**、**R3(对比公平性)**、**R4(新颖性边界声明)** 与 **S1/S2/S4(效应量、pilot 降级、功效披露)**,均在 `v29.tex`(`v28.tex` 原版保留)。**R1(可复现性回填)** 与 **S3(隐私嵌入消融)** 属实验层面,已在文中 `§Reproducibility statement` 预先承诺或标注为 planned,无法以文本修改闭合。其中 **S1(效应量)** 在第二轮评审(`docs/v29_review.md`)中被升级为 R3(Major),已在 L505 以 Cohen's h 闭合,并在主结果段 L681 同步收敛;**S2** 以「pilot 降级为 future work」闭合;**S4** 以「功效限制披露」闭合。

---

## 逐条回复(Point-by-Point Response)

### R1 — 可复现性回填(CRITICAL)

- **来源**:EIC / R1 / Devil's Advocate
- **审稿意见**:核心结果(NVFP4 QAD 路径)在公开仓库当前不可复现,主表以「正式 H100 运行」为唯一权威来源,第三方无法验证。
- **状态**:⏳ **planned(非文本可解决)**

**作者回应(中文)**:
论文 `§Reproducibility statement`(v29.tex L509)已明确承诺:仓库早期配置为 post-training int4,现 QAT/NBE 路径(Eq. 5)已就位,将重跑以回填表 3–表 5 数字,并在完成后给出精确 commit 指针。本项需实际运行 H100 集群,不属于文本修订范围;本次不改动该承诺,待回填完成后补 commit 指针与「第三方可复现」声明。

**英文回应(可粘贴)**:

> We acknowledge that the public repository currently hosts an earlier post-training int4 configuration whose raw outputs do not yet reproduce the reported tables. The QAT path implementing Eq. (5) is now in place, and we are re-running it on the H100 cluster to backfill Tables 3–5. We will add an exact commit pointer identifying the revision used to generate every reported number once this reproduction run completes; until then, the values in the paper remain the authoritative record of the formal H100 run.

---

### R2 — 主张收敛(MAJOR)

- **来源**:EIC / R3 / Devil's Advocate
- **审稿意见**:摘要/结论/highlights 的 `"practical template"`、`"real-time … on commodity hardware"` 与正文受控环境边界不一致;`2.1×` 硬件加速需显式标注 NBE 仿真性质。
- **状态**:✅ **已完成(5 处文本修改)**

**作者回应(中文)**:已在 `v29.tex` 完成以下收敛,将「实时/无精度损失/实用模板」降级为「near-real-time / 小幅精度代价 / feasibility baseline / 待 field 验证」,与正文诚实披露的边界对齐。`2.1×` 在摘要/结论层面未出现数字,且正文已在三处(Table 2 脚注 L318、`§System-level interpretation` L336、`§Measurement scope` L507)标注为「isolated compute-kernel throughput margin / NBE 仿真」,无需额外改动。

| 位置 | 改动 |
|---|---|
| 摘要结尾(L76) | `real-time` → `near-real-time`;`without sacrificing accuracy` → `at a small accuracy cost`;`practical template` → `feasibility baseline`;补 `generalisation … remains to be validated through field studies` |
| highlights #4(L83) | 补 `decoding speedup … for the cloud-side review draft model` |
| highlights #5(L84) | 补 `on the TAF-28k benchmark` |
| 结论(L909) | `suitability` → `feasibility`;`under the evaluated conditions` → `under the evaluated benchmark conditions` |

**英文回应(可粘贴)**:

> We have tempered the headline claims to match the evidence boundary disclosed throughout the manuscript. In the abstract and conclusion, "real-time … without sacrificing accuracy, offering a practical template" is now "near-real-time … at a small accuracy cost, establishing a feasibility baseline", and we state explicitly that generalisation to unconstrained real-world deployment remains to be validated through field studies. The highlights now scope the speculative-decoding speedup to the cloud-side review draft model and scope the on-device result to the TAF-28k benchmark. The `2.1×` figure is already qualified as an isolated compute-kernel throughput margin under the NBE protocol (Table 2 note, §System-level interpretation, §Measurement scope).

---

### R3 — 对比公平性限定(MAJOR)

- **来源**:R2 / Devil's Advocate
- **审稿意见**:明确 SAFE-QAQ 为「引用值、7B/未量化、异部署目标」,`57×` 对比不作为同尺度竞争声明。
- **状态**:✅ **已完成(Table 3 脚注 + 主结果段 L684 双重限定)**

**作者回应(中文)**:摘要层未含 SAFE-QAQ 的 headline 对比。Table 3 脚注(v29.tex L665)已披露「不同规模(7B vs. 0.5B)、异部署目标、引用自 [2] 未复现」;主结果段(L684)本次追加显式限定,把 SAFE-QAQ 标注为 `a cited reference point at a different scale and deployment target, not a like-for-like competitor`,并把 `57×` 对比明确为 `a deployment-efficiency observation rather than an accuracy claim on equal footing`。

**英文回应(可粘贴)**:

> The SAFE-QAQ comparison is qualified at two levels: the Table 3 footnote identifies it as a high-capacity reference baseline at a different scale (7B vs. 0.5B) and deployment target, cited from [2] rather than reproduced in-house; and the main-results paragraph now explicitly labels it "a cited reference point at a different scale and deployment target, not a like-for-like competitor", reporting the 57× figure as "a deployment-efficiency observation rather than an accuracy claim on equal footing".

---

### R4 — 新颖性边界声明(MAJOR)

- **来源**:R1 / Devil's Advocate
- **审稿意见**:明确哪些是「新组件」、哪些是「既有技术的领域适配组合」;补充 LoRA/Adapter 微调 + PTQ 对照基线以排除「收益来自微调而非纯 KL」的替代解释。
- **状态**:🟡 **部分完成(文本已改,基线待补)**

**作者回应(中文)**:贡献段(v29.tex L147)已显式声明组合贡献定位,把新颖性落在「集成协同设计 + 经验验证」而非单组件创新,直接回应 DA 的尖锐质询。LoRA/Adapter + PTQ 对照基线属新增实验,不在文本范围,标注为 planned。

**改动**:L147 原文 `Collectively, these contributions extend …` → `The novelty lies not in any single component—each draws on established techniques—but in their integrated co-design and empirical validation for privacy-constrained on-device fraud detection, a multimodal setting …`。

**英文回应(可粘贴)**:

> We agree that no individual component is novel in isolation; each draws on established techniques. The contribution section now states this explicitly, locating the novelty in the integrated co-design and empirical validation of the four components for privacy-constrained on-device fraud detection. We additionally plan a LoRA/Adapter-finetune + 4-bit PTQ baseline to rule out the alternative explanation that the distillation gain stems from fine-tuning itself rather than the pure-KL objective; this will be added to Table 3 in the next round.

---

## 建议修改(Suggested Revisions · should_fix / consider)

### S1 — OV-Freeze 效应量论证(should_fix)

- **状态**:✅ **已完成**(在第二轮评审中被升级为 R3 Major,以 Cohen's h 闭合)。§Experiments 统计段(L505)已追加标准化效应量(Cohen's h,arcsine 变换概率尺度):OV-Freeze 增益(0.916→0.923)$h \approx 0.02$、异构量化增益(0.915→0.923)$h \approx 0.03$、LDP 诱导退化(0.923→0.902)$h \approx 0.07$,均低于常规 small 阈值($h=0.20$),如实反映「统计显著、效应量小」。主结果段(L681)同步收敛,将该增益表述为「faithful distillation 的证据」而非「实际大幅精度提升」。

### S2 — field/pilot 证据或降级(should_fix)

- **状态**:✅ **已完成**。Discussion(L898)已将 pilot 显式降级为 future work:`A pilot deployment in a real telecommunication-fraud setting is identified as future work (Table~\ref{tab1}) and has not been completed within the scope of this study.`

### S3 — 隐私嵌入消融(consider)

- **状态**:⏳ planned。分离 Whisper-tiny 信息瓶颈 vs MFCC+池化设计对 WER≥0.95 的各自贡献(属新实验,非文本可闭合)。

### S4 — 说话人识别功效分析(consider)

- **状态**:✅ **已完成(据实保留「preliminary」措辞)**。§Privacy(L853)已追加统计功效限制披露:11-speaker 闭集小样本限制了对弱生物特征泄漏的检测功效,故 8.3%(vs 9.1% 随机基线)应解读为「privacy 的初步证据」而非「形式化、功效充足的阴性结论」。

---

## 修订状态总览

| 意见 | Severity | 状态 | 位置 |
|---|---|---|---|
| R1 可复现性 | Critical | ⏳ planned | §Reproducibility statement(L509) |
| R2 主张收敛 | Major | ✅ 已完成 | L76 / L83–84 / L909 |
| R3 对比公平性 | Major | ✅ 已完成 | Table 3 脚注(L665)+ L684 |
| R4 新颖性边界 | Major | 🟡 部分完成 | L147(基线待补) |
| S1 效应量 | should_fix | ✅ 已完成 | L505(Cohen's h)+ L681 |
| S2 field 证据 | should_fix | ✅ 已完成 | Discussion(L898) |
| S3 隐私消融 | consider | ⏳ planned | — |
| S4 功效分析 | consider | ✅ 已完成 | §Privacy(L853) |

---

## 文件位置

- 修订稿:`D:\Projects\H100_package_realeval\docs\v29.tex`(原版 `v28.tex` 保留)
- 评审报告:`D:\Projects\H100_package_realeval\reports\v28_peer_review.md`
- 本修订说明:`D:\Projects\H100_package_realeval\reports\v29_response_to_reviewers.md`
