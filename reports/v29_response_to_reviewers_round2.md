# QAD-MultiGuard — Response to Reviewers(第二轮修订说明)

> **论文**:QAD-MultiGuard: An Edge–Cloud Framework for Multimodal Fraud Detection and Risk Assessment
> **回应评审**:`docs/v29_review.md`(2026-08-28,`full` 五席位评审,**Major Revision**)
> **修订文件**:`docs/v29.tex`(就地修订,版本号不变;原版 `v28.tex` 保留)
> **目标期刊**:Expert Systems with Applications(ESWA)
> **修订日期**:2026-08-30
> **性质**:模拟修订说明。状态标注区分「已完成 / planned(待实验回填)」,不虚构未做的实验。

---

## 总述(Summary of Changes)

本次修订针对 `v29_review.md` 的 **R2 / R3 / S1 / S3 / S4** 进行,均为文本层面可闭合项。**R1(可复现性回填)** 与 **R4(PTQ 原生格式对照)** 属实验层面,需 H100 集群补跑,本轮按用户指示「先用历史结果占位,待补跑后重新修订」,标注为 planned。**S2(LDP 合规标注)** 已在 `v29.tex` 前一轮修订中完成(正文已写明 `engineering estimate … not a full differential-privacy analysis`),本轮无需再改。

---

## 逐条回复(Point-by-Point Response)

### R2 — privacy 声称过度(MAJOR)

- **来源**:EIC / R2(领域) / R3(交叉视角) / Devil's Advocate
- **审稿意见**:嵌入是输入音频的确定性函数,同一说话人在相似条件下嵌入稳定,honest-but-curious 云可通过余弦相似度跨会话链接同一人;"privacy-preserving" 表述强于证据,应收敛为「内容级抗重建」。
- **状态**:✅ **已完成(14 处文本收敛)**

**作者回应(中文)**:全局将修饰嵌入/表示的 `privacy-preserving` 收敛为 `reconstruction-resistant`(内容级)或 `privacy-constrained`,不再以「privacy-preserving」修饰本文的 128 维声学嵌入;保留数据流层面的隐私表述(`raw audio/text stays on-device`)与 future work 中 DP-SGD 的 `privacy-preserving` 用法(后者是正式隐私机制,非过度声称)。正文 §3 与 §5 已有的 content-level vs identity-level 区分(`content-level protection … not designed for cross-session unlinkability`)予以保留,作为 R2 的语义锚点。

| 位置 | 改动 |
|------|------|
| 摘要 (component iii) | `privacy-preserving 128-d acoustic embedding` → `reconstruction-resistant 128-d acoustic embedding` |
| highlight #3 | `Privacy-preserving embeddings hinder` → `Reconstruction-resistant embeddings hinder` |
| keywords | `privacy-preserving representation` → `reconstruction-resistant representation` |
| §1 (C1) | `privacy-preserving acoustic representation` → `reconstruction-resistant acoustic representation` |
| §3 component (3) 标题 | `Privacy-preserving acoustic representation and multimodal fusion` → `Reconstruction-resistant …` |
| §3 component (3) 正文 | `privacy-preserving acoustic representation` → `reconstruction-resistant acoustic representation` |
| §2 (L171) | `privacy-preserving on-device inference` → `privacy-constrained on-device inference` |
| §2 (L173) | `privacy-preserving acoustic-modality fusion` → `privacy-constrained acoustic-modality fusion` |
| §2 (L177) | `privacy-preserving on-device inference` → `privacy-constrained on-device inference` |
| §2 (L232) | `privacy-preserving acoustic representations` → `reconstruction-resistant acoustic representations` |
| 图 1 caption | `privacy-preserving acoustic representation` → `reconstruction-resistant acoustic representation` |
| 图 2 caption | `privacy-preserving acoustic embedding` → `reconstruction-resistant acoustic embedding` |
| §3 (L402) | `The privacy-preserving acoustic embedding` → `The reconstruction-resistant acoustic embedding` |
| §4 过渡句 (L471) | `privacy-preserving acoustic embedding` → `reconstruction-resistant acoustic embedding` |

**英文回应(可粘贴)**:

> We agree that "privacy-preserving" overstated the evidence for the acoustic embedding, which resists speech-content reconstruction but is not designed for cross-session unlinkability. We have replaced the term throughout the manuscript: the embedding and its representation are now consistently described as "reconstruction-resistant" (content-level protection), and on-device inference is described as "privacy-constrained". Data-flow statements that raw audio and text remain on-device, and the DP-SGD future-work reference, are retained since they describe genuine privacy mechanisms rather than the embedding's properties. The content-level vs identity-level distinction stated in §3 and §5 remains unchanged.

---

### R3 — 关键增益效应量未报告(MAJOR)

- **来源**:R1(方法学) / Devil's Advocate
- **审稿意见**:+0.007/+0.008 级微小增益仅以 `p<0.01`/`p<0.05` 包装,未报标准化效应量,存在「以 p 值代效应」。
- **状态**:✅ **已完成(用历史结果,待补跑重算)**

**作者回应(中文)**:§Experiments 统计段(原 L505)追加 Cohen's h 效应量(arcsine 变换概率尺度),并显式声明其量级与来源:

- OV-Freeze 增益(0.916 → 0.923):$h \approx 0.02$
- 异构量化增益(0.915 → 0.923):$h \approx 0.03$
- LDP 诱导退化(0.923 → 0.902):$h \approx 0.07$

三者均低于常规 small 阈值($h=0.20$),如实反映「统计显著、效应量小」的事实。效应量由历史 H100 运行数据推算,并声明将在复现运行(R1)完成后重算。

**英文回应(可粘贴)**:

> We now report standardised effect sizes alongside significance tests. On the arcsine-transformed probability scale, the OV-Freeze gain (0.916 → 0.923) yields Cohen's h ≈ 0.02, the heterogeneous-quantisation gain (0.915 → 0.923) yields h ≈ 0.03, and the LDP-induced degradation (0.923 → 0.902) yields h ≈ 0.07 — all below the conventional h = 0.20 threshold for a "small" effect. These are computed from the historical H100 run and will be recomputed from the reproduction run described in the Reproducibility statement.

---

### R1 — 可复现性回填(CRITICAL)⏳ planned

- **来源**:EIC / R1 / Devil's Advocate
- **状态**:⏳ **planned(非文本可解决)**

**作者回应**:公开仓库当前为旧 int4 配置,主表数字不可复现。论文 §Reproducibility statement 已承诺重跑 QAT/NBE 路径并给出 commit 指针;本轮按指示保留该承诺,待 H100 补跑完成后更新为「已复现 + commit 指针」。

---

### R4 — 基线公平性(MAJOR)⏳ planned

- **来源**:R1 / Devil's Advocate
- **状态**:🟡 **部分完成(SAFE-QAQ 边界已在前轮限定;PTQ 原生对照待补)**

**作者回应**:SAFE-QAQ 非同类对比已在 `v29.tex` 前轮限定(`cited reference at a different scale and deployment target, not a like-for-like competitor`)。PTQ 基线(AWQ/GPTQ/SpinQuant/QuaRot)当前为 `adapted reimplementations under a common NVFP4 constraint`,原生格式对照属新增实验,标注 planned,待补跑后修订。

---

### S1 — 语音隐私文献谱系(should_fix)

- **来源**:R2(领域)
- **状态**:✅ **已完成(补引 `\citep{22}` = VoicePrivacy 2022 Challenge)**

**作者回应(中文)**:§2 相关工作补 speaker anonymization 谱系演进(启发式混淆 → 形式化保证,含 $k$-anonymity in embedding space、differentially-private perturbation、Voice Privacy Challenge 框架),并显式区分 `content-level`(抗内容重建)与 `identity-level`(防跨会话链接),声明本文 scope 为 content-level。引用层面,`ref_v4.bib` 中的 `{22}` 即 VoicePrivacy 2022 Challenge Evaluation Plan(Tomashenko et al., 2022),已在谱系文字处补 `\citep{22}`;同时将 `ref_v4.bib` 归入仓库 `docs/` 目录,解决此前 bib 缺失导致的编译缺项。

**英文回应(可粘贴)**:

> We have expanded the related-work discussion to trace speaker-anonymisation research from heuristic obfuscation toward formal guarantees (k-anonymity in embedding space, differentially-private perturbation), and to reference the Voice Privacy Challenge framework, which explicitly separates content-level protection (resisting reconstruction of linguistic content) from identity-level protection (preventing cross-session linking). We state clearly that the scope of our representation is content-level, with identity-level unlinkability analysed in §Discussion.

---

### S2 — LDP 合规标注(should_fix)

- **状态**:✅ **前轮已完成**(`v29.tex` 正文已写明 LDP 为 `engineering estimate … not a full differential-privacy analysis … optional engineering experiment`,图 1 亦标注 optional 配置)。本轮无需改动。

---

### S3 — 误判社会后果与弱势群体伦理(consider)

- **来源**:R3(交叉视角)
- **状态**:✅ **已完成**

**作者回应(中文)**:§Discussion 新增 `Societal consequences of misclassification` 段落,讨论假阴性(欺诈得逞,害及老年/低数字素养群体)与假阳性(误中断合法通话,如照护者紧急呼叫)的不对称后果,说明三层设计(端侧偏召回 + 云端异步降假阳)如何缓解,并将代价非对称性阈值对齐与量化评估列为部署向未来工作。

**英文回应(可粘贴)**:

> We have added a "Societal consequences of misclassification" paragraph to the Discussion. It addresses the asymmetric harms of false negatives (which disproportionately affect elderly users and others with lower digital literacy) and false positives (which wrongfully interrupt legitimate calls, with particular severity in time-critical situations), explains how the three-tier design mitigates this tension, and defers quantitative cost-asymmetry thresholding to a deployment-oriented study with operator and regulator involvement.

---

### S4 — 术语一致性(consider)

- **来源**:EIC / Devil's Advocate
- **状态**:✅ **已完成**

**作者回应(中文)**:主结果段(原 L684)`57× smaller scale` → `57× smaller storage footprint`(57× 是存储压缩口径,参数规模口径为 14×,二者不应混用)。标题 "Multimodal" 与 "audio–text 主评估" 的边界已由摘要显式声明(`primary evaluation is confined to the audio–text modality pair`),无需改标题。

---

## 附加修订(引用精确性)

### X1 — x-vector 引用错位修正

- **性质**:既有引用问题(非 v29_review.md 意见),审阅 bib 时发现
- **状态**:✅ **已完成**

**问题**:§2 原句 `\citet{22} proposed x-vector substitution as an early approach for acoustic identity obfuscation` 中,`{22}` 实际为 VoicePrivacy 2022 Challenge Evaluation Plan(评估框架),并非「提出 x-vector」的原始论文。

**修正**:新增 `@inproceedings{snyder2018xvectors}`(Snyder et al., ICASSP 2018, DOI 10.1109/ICASSP.2018.8461375,x-vector 原始出处),并将该句改为 `\citet{snyder2018xvectors} introduced x-vectors for speaker recognition, which were subsequently adapted as an early approach for acoustic identity obfuscation`。`{22}`(VoicePrivacy 2022)保留在正确的引用位置(§5 voice-anonymisation literature 与 §2 Voice Privacy Challenge framework)。

---

## 修订状态总览

| 意见 | Severity | 状态 | 说明 |
|------|----------|------|------|
| R1 可复现性 | Critical | ⏳ planned | 待 H100 补跑 + commit 指针 |
| R2 privacy 声称收敛 | Major | ✅ 已完成 | 14 处措辞降级 |
| R3 效应量 | Major | ✅ 已完成(历史结果) | Cohen's h,待补跑重算 |
| R4 基线公平性 | Major | 🟡 部分完成 | SAFE-QAQ 已限定,PTQ 原生对照待补 |
| S1 文献谱系 | should_fix | ✅ 已完成 | 文字谱系,未新增 bib key |
| S2 LDP 标注 | should_fix | ✅ 前轮已完成 | — |
| S3 误判伦理 | consider | ✅ 已完成 | 新增 §5 段落 |
| S4 术语一致性 | consider | ✅ 已完成 | 57× storage footprint 口径统一 |

---

## 文件位置

- 修订稿:`docs/v29.tex`(就地修订)
- 参考文献库:`docs/ref_v4.bib`(本轮补入库)
- 本轮评审报告:`docs/v29_review.md`
- 本轮修订说明:`reports/v29_response_to_reviewers_round2.md`
- 前轮响应(回应 v28 评审):`reports/v29_response_to_reviewers.md`、`reports/v29_revision_letter_EN.md`
