# v28 投稿前修订路线图 — 基于模拟同行评审（Major Revision）

> 日期：2026-08-27
> 依据：`reports/v28_peer_review.md`（5 座位 panel，决策 Major Revision）
> 目标：把 R1–R4（must_fix）+ S1–S4（suggested）拆成可执行任务，区分「文本可改 / 需 H100 重跑 / 需新实验」，并排优先级。
> 关键前提：当前 `outputs/results/` 为空，论文图表由 `docs/figure_scripts/paper_data.py` 的 fallback 常量生成，**非实测**。

---

## 一、决策与总览

| 结论 | 内容 |
|---|---|
| 决策 | Major Revision，无 Reject 信号 |
| 阻断项 | R1（复现回填）+ R2（主张收敛） |
| must_fix | R1 / R2 / R3 / R4 |
| suggested | S1 / S2 / S3 / S4 |

**执行分三类**（按可动工性）：

- **A 文本层（现在就能改，不依赖 H100）**：R2、R3、R4-文本部分、S1、S2（微调）、S4（披露部分）
- **B 复现层（需 H100 重跑，最长周期）**：R1
- **C 新实验层（需新增对照/消融实验）**：R4-替代基线、S3、S4（功效计算）

---

## 二、报告证据 vs v28.tex 现状（核对结果）

| 报告锚点 | v28.tex 现状 | 判定 |
|---|---|---|
| §Reproducibility statement 承认「raw outputs do not yet reproduce the reported tables」 | **存在**。v28.tex L509 `\paragraph{Reproducibility statement.}` 明确承认「the public repository currently hosts an earlier development configuration that used post-training int4... its raw outputs do not yet reproduce the reported tables」 | ✅ 报告锚点准确（本表上一版误判为「不存在」，已纠正） |
| Data availability URL `github.com/wangdajin062/QAD-MultiGuard` | 实际仓库为 `H100_package_realeval` | ⚠️ 需对齐（可能作者计划投稿时另建 `QAD-MultiGuard` 仓库，须确认） |
| 「practical template」过度承诺 | 摘要 76 行确含「offering a practical template」+「real-time fraud detection on commodity mobile hardware」 | ✅ 已修复：v29.tex L76 → near-real-time / at a small accuracy cost / feasibility baseline |
| SAFE-QAQ 57× 对比公平性 | Table 3 脚注 665 行**已披露**异规模(7B vs 0.5B)/引用未复现 | ✅ 已修复：v29.tex L684 追加「not a like-for-like competitor」「deployment-efficiency observation」限定 |
| 单主数据集 | 150 行 + 898 行**已主动披露**「controlled re-enactment」「not yet formally validated」 | 🟡 披露充分，摘要/结论措辞是 R2 收口点 |
| 隐私经验性（非形式化） | 883 行 LDP「engineering estimate... not a formal privacy mechanism」、853 行 ASV「empirical... deferred to future work」 | ✅ 已充分披露 |
| 2.1× 硬件加速 | Table 2 脚注 318 + 正文 336 已标注「kernel-level throughput margin」「NBE 仿真非原生 Blackwell」 | 🟡 表/正文已披露，highlights/摘要需收口（R2） |

---

## 三、must_fix 路线图

### R1 — 复现回填（Critical · 需 H100 重跑）

- **现状**：`outputs/results/` 空；`check_alignment.py` 67 处 MISSING；`--validate-contract` exit 2。
- **动作**：
  1. Pod 上跑 `bash scripts/runpod_rerun.sh`（先 exp1 → P0 → P1 → P2，见脚本 8 阶段）。
  2. 回填 `outputs/results/` → 本地核对 `check_alignment.py` + `--validate-contract` 应 PASS。
  3. 用实测值更新 `experiments/consistency_check.py` 的 `PAPER_CLAIMS`（长期守门员）。
  4. 兑现 `§Reproducibility statement`（L509）已承诺的 commit 指针；核对 `Data availability` URL（`QAD-MultiGuard` vs `H100_package_realeval`）。
- **验收**：第三方 clone + 指定 commit 能跑出表 3–5 主数字。
- **依赖**：H100 pod + TAF-28k 数据就绪。

### R2 — 主张收敛（Major · ✅ 已完成于 v29.tex）

- **目标位置**：
  - 摘要 76 行结尾「offering a practical template for privacy-compliant on-device AI」→ 降级为受控环境可行性证据。
  - 摘要 76 行「deliver real-time multimodal fraud detection on commodity mobile hardware」→ 限定「under controlled conditions / evaluated benchmarks」。
  - highlights（79–85）「3.32× speedup」「0.917 at 268ms」——确认是 wall-clock（正文 907 已注明 wall-clock，OK），如需可加「on Snapdragon 8 Gen 3」已含，暂不改。
  - Table 2 311 行「Hardware-Level Acceleration 2.1×」：脚注 318/正文 336 已披露，但 highlights/摘要若再提「硬件加速」需带「kernel-level, NBE-emulated」限定。
- **验收**：无标题级 over-promise；「practical template」字样移除或重写为「evidence of feasibility under controlled conditions」。

### R3 — 对比公平性限定（Major · ✅ 已完成于 v29.tex）

- **目标位置**：正文 684 行「Compared with SAFE-QAQ ... comparable performance with ~57× reduction」「This parity at 57× smaller scale」。
- **动作**：明确 57× 为**存储足迹对比**（248MB vs 14GB），非同尺度性能竞争；SAFE-QAQ 为引用值、7B/未量化、服务器部署目标。脚注 665 已披露，正文「parity」措辞改为「comparable F₁ at a ~57× smaller storage footprint (different scale and deployment target; cited, not reproduced)」。
- **验收**：读者不会把 57× 误读为同尺度性能竞争。

### R4 — 新颖性边界 + 替代基线（Major · 🟡 文本已完成于 v29.tex，基线待补）

- **文本部分（现在做）**：贡献段 147 行明确「组合贡献 vs 组件新贡献」——四组件各自非新（纯 KL 蒸馏/方差匹配/隐私声学特征/投机解码均有先例），贡献在于**诈骗检测场景下的组合与协同验证**。建议 147 行补一句边界声明。
- **实验部分（需新实验）**：补对照基线「BF16 0.5B + LoRA/Adapter 微调 + 4-bit PTQ」，排除「收益来自微调本身而非纯 KL」的替代解释（DA 反论点 1）。
- **验收**：贡献段明确边界；替代基线实验结果（或据实降级为 future work）。

---

## 四、suggested 路线图

| 项 | 状态 | 动作 | 性质 |
|---|---|---|---|
| **S1** OV-Freeze 效应量 | 681 行有 std（0.916±0.007 → 0.923±0.006），缺效应量/CI | 补 Cohen's d 或 bootstrap CI，论证 +0.007 的实质意义 | 文本（现在做） |
| **S2** field/pilot 证据 | **已基本满足**：898 行已「Until field validation becomes available... controlled-environment performance」+「planned pilot deployment」 | 微调：将「planned pilot」明确为 future work，不必新增实验 | 文本（微调） |
| **S3** 隐私嵌入消融 | 未做 | 分离 Whisper-tiny 信息瓶颈 vs MFCC+池化设计对 WER≥0.95 的贡献 | 新实验 |
| **S4** ASV-EER 功效分析 | 853 行已披露 11-speaker 闭集 + defer 形式化保证 | 补样本量功效分析（或据实保留「preliminary/empirical」措辞） | 文本+计算 |

---

## 五、执行顺序（并行推进）

```
现在（文本层，无阻塞）               依赖 H100（阻塞，最长的在 R1）
├─ R2 主张收敛  → 改摘要/highlights/结论
├─ R3 对比公平性 → 改正文 684
├─ R4-文本 贡献段边界 → 改 147
├─ S1 效应量  → 改 681 附近
├─ S2 微调   → 改 898
└─ S4 披露   → 改 853

H100 重跑（R1）→ 回填 outputs/results → 更新 PAPER_CLAIMS → tex 补 commit 指针
新实验（R4-基线 / S3 / S4-功效）→ 需额外 GPU 时间，可排 R1 之后或降级 future work
```

**关键判断**：文本层 6 项现在即可完成且相互独立；R1 是唯一 Critical 阻塞项，周期受 H100 调度 + TAF-28k 数据链约束，应**最早启动**（放后台跑）而非最后。R4-基线、S3 若 GPU 预算紧张，可据实降级为 future work（与 S2 同口径），但 R1 不可降级。

---

## 六、完成标准（投稿门槛）

- [ ] R1：`outputs/results/` 回填，`check_alignment.py` 与 `--validate-contract` PASS，tex 有 commit 指针
- [ ] R2：摘要/结论无「practical template」类 over-promise
- [ ] R3：57× 明确为存储对比
- [ ] R4：贡献段有边界声明（组合 vs 组件），替代基线已有或已降级
- [ ] S1–S4：已处理或据实降级 future work
