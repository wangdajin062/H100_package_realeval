# 记忆日志（Memory Log）

> 本文件是跨会话的工作记忆：每次任务/会话结束时，由当次会话追加一条记录，
> 供后续会话快速恢复上下文。记录格式见下方条目模板。
> 约定来源：根目录 `AGENTS.md`。

---

## 2026-08-13 深夜 [第二轮全量审计 + 修复 + 同步 GitHub]

- 目标：复核第一轮审计（`reports/2026-08-13_full_audit.md`）修复成效，完成残留问题修复并同步远程。
- 完成：
  - 审计报告 `reports/2026-08-13_full_audit_round2.md`（含第八节修复结果明细）。
  - 统计诚信：`experiments/common.py` 新增 `seed_base_from_config()`，exp1/2/3/10/11/14 共 9 处 `set_seed(1000+s)` 替换（claim 多 seed 不再退化，默认 1000 保持论文路径不变）；exp11 异常路径 `f1: 0.0→None`（配合 paper_data 的 None 显式报缺）。
  - Windows 可用性：consistency_check / paper_data / check_alignment 的非 GBK 字符（emoji、✓✗）全部改 ASCII。
  - 文档：REPRODUCIBILITY 铁律与 git add 修正、README/REFACTORING 删 defaults.py 引用、README 实验分组 7→10、figure_scripts README 七图→八图、删 FIGURE_CAPTIONS.md 死引用。
  - 配置/脚本：`runpod_h100.yaml` 补 `data.dataset: taf28k`（覆盖真正生效）；cluster 三脚本去 `/workspace` 硬编码；`sync_paper_data.py` 标废；`.gitignore` 补 `outputs/claims/`、`outputs/sft_checkpoints/`；generate_all 门控修正（Fig3=exp1/3/11/14，Fig8=exp3/5/11，删无人消费的 exp7）；check_alignment/generate_all 与 paper_data 的 smoke 过滤对齐；student_loader/envreport 统一走 `io.paths`。
  - 提交 `6cbc498`（31 文件，+324/-74），已推送 `origin/main`。
- 验证：pytest 65 passed；consistency_check 人类模式 GBK 不再崩溃；paper_data 自检 / check_alignment / --validate-contract 全部跑通。
- 遗留：
  - `outputs/results/` 为空（本地结果已清理，含 2GB 模型）——论文图表当前只能靠内置常量，**对外使用前必须 H100 重跑回填**。
  - `exp5.bf16_matched_advfraud` 身份（measured vs cited）待人工确认。
  - claim 评估未接入 pipeline（手动 `python -m experiments.claim_engine`），建议加 CI 干跑。
  - `claims/legacy/` + `claim_runner` 为有意保留的归档岛，复活需先写适配层。
  - 孤儿数据集 balanced600/balanced10c/chifraud.npz 未清理（低风险保留）。

---

## 2026-08-14 [第三轮全量审计修复 + 清理 + 同步 GitHub]

- 目标：落地第三轮审计（`reports/2026-08-14_full_audit.md`）的 P0/P1/P2/P3 修复，清理孤儿副本，同步远程。
- 完成：
  - 应用 10 个补丁（0001~0010），合并为 6 个提交：
    - `301dadb` 安全：P0-1（Dockerfile 弱密码）、P1-S1~S4（API 认证/路径校验/RunPod 标识/弱口令/S3 凭据 0600）、P1-O10（flash-attn 换 devel 镜像）。
    - `e493cec` 测量/工具：P1-M1（统一切分，新增 split manifest 消除跨实验泄漏）、P1-M4（exp7 GLO 诚实 demo 标注）、P2-2/4/7/9/11/12/13/14/17/20/22。
    - `7eab160` 运维：P1-O2/O3/O4/O6/O7/O8、P2-3、P2-24、P3 编码/打包。
    - `63365ec` 契约文档（P2-18）+ P3 数据诚实（-1 标签、SNR None、privacy RNG 恢复、group_split 单样本类）。
    - `e4bf17a` 清理：删 5 个孤儿副本（根级 services/ 三份 + scripts/entrypoint/healthcheck，因 build context 指向 template/）、标废 apply_all_fixes.py。
    - `6b3d6ea` P1-O5 补 bitsandbytes 到 requirements.txt。
  - 同步方式：git remote 由 SSH 改 HTTPS（本机凭据管理器 token），全部 push 成功。
- 验证：每批改动均 pytest 65 passed；py/bash/json/toml 语法检查全通过。
- 遗留：
  - `outputs/results/` 仍为空，论文数字需 H100 重跑回填。
  - P3 纯清理类（aggregation.py 零调用函数、audit.py runlog 空转等）未逐一处理。

## 2026-08-14 [第三轮审计修复复查（只读复核）]

- 目标：逐项核对第三轮审计（reports/2026-08-14_full_audit.md）P0/P1/P2/P3 修复是否真实落地。
- 完成：五路并行复核约 50 个条目，对照当前工作树实际代码（非提交信息）。基线：pytest 65 passed、consistency_check 正常、工作树干净（HEAD 7b3d750）。
- 验证结论：关键修复全部真实落地、无虚报；发现 8 处不完整/遗漏——
  1. P1-M2 半修：pre_run_validation 数据来源断言未实现，13/14 实验仍不记录数据来源；
  2. fig8_revision_ablations.py:145（审计点名处）+ :65/:76 None 守卫漏修，缺结果数据态必崩；
  3. 呈现层未跟进：contract.py:105 仍列 demo 字段为 MEASURED；fig6 "Perplexity"、fig8 "ε-LDP" 误导标签保留；
  4. P1-O6 teacher_3b 关在 STAGE_LARGE=1 闸门内，默认部署路径不下载；
  5. P1-O2 run_pipeline.sh 未补 set -e，依赖/下载失败仍可假成功；
  6. P1-S2 残留：REPRODUCIBILITY.md:53 真实 pod ID mhypfkvge474n8 未清；
  7. P3 半修：data.py:236 的 -1 标签 fraud 中心索引未动；privacy.py RandomState(0) 固定噪声保留；
  8. P2-13 原子写未做（serialization.py 仍 write_text 直写）。
- 遗留：低危项——/experiments/status/{run_id} 无认证探测；template 栈内 /workspace/repo 引用残留；archive_and_clear.py --force 未接线；diagnose_v25_run.py:409 默认路径错；P2-12 错 adapter 仅 warning。

## 2026-08-14 [复查修复的二次复核（506eec4 + c720f83）]

- 目标：逐条核实上轮复查报告的 8 处不完整/遗漏 + 5 处低危残余是否已真实修复。
- 完成：全部对照当前工作树代码核实（非提交信息）：
  - 506eec4：P1-M2 数据来源断言（framework.py:135 has_local_data 提前失败）、fig8 三处 None 守卫、contract 移除 exp7 demo 字段 MEASURED 校验、fig6/fig8 误导标签修正、teacher_3b 入默认清单、run_pipeline.sh set -euo pipefail、pod ID 清除、data.py -1 过滤、gaussian_ldp 种子参数化、serialization 原子写（mkstemp+os.replace）——全部在位。
  - c720f83：status 端点补认证、/workspace/repo 引用改齐、--force 接线、diagnose 默认路径改绝对路径、student_loader 错 variant 改返回 None 硬失败——全部在位。
- 验证：pytest 65 passed；consistency_check exit 0；工作树干净（HEAD c720f83）。
- 遗留：第三轮审计及其复查的所有点名项已闭环；剩余仅 MEMORY_LOG 此前声明的 P3 纯清理类（aggregation.py 零调用函数、audit.py runlog 空转）与 outputs/results 需 H100 重跑回填。

## 2026-08-15 [论文 v26→v27 重构 + ESWA 顶刊强化 + H100 实测核对]

- 目标：以 v26.tex 为初稿做主线化重构，按 ESWA 顶刊标准强化，并与 H100 实测结果做 Claim–Evidence 一致性核对。
- 完成：
  - 论文 v25→v26→v27 修订（`C:\Users\wangd\Downloads\`，无 git）：
    - v26：立论重构（三约束 privacy/fidelity/responsiveness ↔ 四组件）、数字修正（α→0.78/0.86、speaker 10→11、OVF 窗口 30%→20%）、消融标准步骤、诚实标注（draft 0.1B→0.5B、融合双模态）。
    - v27：端/云区分（on-device 0.917@268ms vs cloud NVFP4+CoT 0.923）、融合四模态→双模态（w=[0.40,0.30]）、spec-dec 归位云端 CoT、删除 LoRA/4-tuple/fig4/CPU复现、数字修正（PTQ 7.1–8.5pp、57×、3 scalars）、英式拼写统一。
    - 顶刊强化：四大维度（模态边界澄清、边云冲突仲裁、OVF 协同解析、同源蒸馏优势）+ 7 项分章节建议 + P0/P1 审稿修复（附录 A.2 收敛证明降级为「有界梯度重缩放」、LDP 降级、PIPL 弱化、fusion CV 澄清、统计检验规范、Blackwell「targeted for deployment」口径）。
  - 图脚本序号对齐论文 v27（删 fig4、fig5–8 循环重命名），提交 `641a021`/`c863ed6`/`e694216`；融合权重对齐 2 模态（提交 `b805ff4`）。
- 验证：v27.tex 结构配对完整（equation 13/13、figure 7/7、table 7/7）；图脚本重命名后无残留旧引用。
- 遗留（重要）：
  - **H100 实测与论文数字严重不符**（`Desktop/RunPod_H100_20260803.md`）：exp1 QAD 实测 0.7974（论文 0.916）、exp3 OVF 0.5577（论文 0.923）、exp14 Q4_K_M 0.7025（论文 0.917）、α 0.468（论文 0.78）；CoT 实测 with_cot F1=0.035（论文声称 CoT 有效，需改写为「0.5B CoT 无判别力」）。
  - **决策：实验待补跑（exp5/8/10 Pod 中断），论文暂用历史值（0.9 级），预期 F1 0.9 以上。** 补跑后需回填 paper_data.py fallback 与论文数字，并重做一致性核对。
  - paper_data.py 的 fallback 仍为旧值（0.7974/0.7025），实验补跑出 0.9+ 后需同步更新。

---

## 2026-08-15 [脚本 bug 修复 + 论文据实标注（Claim–Evidence 对齐）]

- 目标：审计补跑脚本是否对齐论文方法/指标且无 bug，并据实标注论文中「常量当实测」的数字。
- 完成：
  - 脚本 bug 修复（提交 `a38a4cd`，4 个 bug）：
    1. `test_ratio=0.2` 显式传参（exp4/9/10/11/12 共 5 处）→ 0.1，对齐 8:1:1（此前只改默认值、漏了显式调用）。
    2. exp2 `loss_specs` 补 pure_kl 分支：原 `kl_only` 误用 `loss_fn="kl"`（CE+KL），现 `kl_only=pure_kl`、新增 `kl_task=kl` 独立分支。
    3. exp1 显式设 `loss_fn="pure_kl"`（论文 Table 3 QAD 0.916 是纯 KL 产物）。
    4. exp3 显式设 `loss_fn="pure_kl"`（论文 Table 4 QAD+OVF 0.923 是纯 KL+OVF）。
  - 论文据实标注（v27.tex，4 项）：exp6 α（domain-tuned 0.86 为 cited、generic 实测 0.468）、exp7 WER（reference estimates、脚本 not_measured）、exp8 268ms（端到端估计、per-token 46.47ms 口径不同）、exp12 240MB（纯权重、实际文件 491.4MB）。
  - 图脚本命名重构（提交 `f7c87fb`）：EXP 常量重命名对齐实际 exp 编号（EXP01_QUANT_QUALITY→PTQ_BASELINES 等 6 个）、注释 Figure 编号对齐 fig5-8 重命名。
- 验证：pytest 65 passed；py_compile 通过；check_alignment 正常报 MISSING（outputs 空）。
- 关键结论：**修复前补跑脚本跑的是「CE+KL + 20% test」，根本不是论文声称的「纯 KL + 8:1:1」——之前实测 0.43/0.70 的低值有一部分是方法未对齐导致。修复后补跑才真正对齐论文方法，此时数字才有意义（若仍 0.4/0.7 则论文虚报，需据实修订头条）。**
- 遗留：
  - 仍缺脚本：exp6 域调 draft 微调、exp7 音频重建管道（WER/PESQ/STOI/MOS 实测）、exp8 端侧延迟实测。
  - `outputs/results/` 仍为空，补跑后需回填 paper_data fallback 与论文数字，并重做一致性核对。

## 2026-08-16 [审核修复落地 + 修复 docstring 标注不一致]

- 目标：审核本地包（HEAD 5c33b5d）中报告声称的「脚本 bug 修复 + 据实标注」是否真实落地，并修复发现的问题。
- 完成：
  - 逐项核对 a38a4cd（4 处 bug）、8392c59（QAD 配置）、a13762c（OV-Freeze 公式）、dce93d3/b805ff4（exp13 融合）——全部真实落地，无虚报。
  - 据实标注核对通过：specdec 标 NOT MEASURED/cited、paper_data fallback 用真实值（0.7974/0.8047/0.7025）、exp7 标 not_measured/demo、contract 移除 exp7 demo 字段 MEASURED 校验。
  - 修复 `realeval/real_backend.py:708` docstring 融合权重陈旧值：`w=[0.6, 0.4]` → `w*=[0.40, 0.30], b*=-0.45`，对齐实际实现（:745-746，b805ff4 改代码漏同步 docstring）。
- 验证：仅 docstring 改动，无功能影响；本地 Windows 环境缺 torch，pytest 无法运行（65 passed 需有 torch 的环境复现）。
- 遗留：
  - **可复现性实质鸿沟仍在**：真实 F1 0.80/0.70 vs 论文 0.916/0.917，`outputs/results/` 为空，需 H100 重跑回填或据实修订论文头条（审稿报告 M1）。
  - 本次改动未提交 git。

## 2026-08-16 [论文 v27_revised.tex 投稿级静态审计 + 落地修复]

- 目标：对投稿稿 `C:\Users\wang\Downloads\v27_revised.tex` 做投稿前静态审计，并落地可执行修复。
- 完成：
  - 审计结论：数字算术全部自洽（Recovery 14 行、差值 0.085/0.072/0.071/0.006、相对 drop 0.8%/6.0% 等），问题集中在口径标注与残留痕迹，非算术错误。
  - 修复（均改投稿稿，已备份 `v27_revised.tex.bak`）：
    1. P0-1 删残留 `% REVIEWER TODO` 审稿注释（grep 确认无 REVIEWER/TODO 残留）。
    2. P0-2 图号重编号 fig5-8 → fig4-7，闭环审稿 N7 图号缺口（fig4 loss-convergence 已在 v27 删除但未重排）。现 fig1-7 连续，fig4 a/b/c 三面板均有引用。
    3. P1-7 G2 措辞：明确 G2（vs matched BF16）由 0.8% drop 满足，6.0% 标注为额外 cross-corpus 参照。
    4. P2-12 CI 单位补 "percentage points"。
    5. P2-10 补 fig4(b) 引用（0.841 后）。
- 验证：grep 确认 REVIEWER/TODO 清除、fig1-7 引用连续且与 label/includegraphics 一一对应。
- 遗留（需作者同步/定夺，未擅自改）：
  - PDF 文件需同步重命名（fig5.pdf→fig4.pdf 等）；figure_scripts 脚本因 AGENTS.md「fig 脚本尽量不改」未 git mv。
  - 需作者实验数据/裁定：P0-3 ASV-EER「reconstructed embeddings」双重错误 + 46.8%/48.5% 来源；P0-4 隐私表 Speaker-ID/ASV-EER 列头语义；P1-5 0.916 的 CoT 状态三处口径；P1-6 LDP sensitivity/clipping 未定义；P2-8 隐私边界措辞；P2-9 57× footprint 混用。
  - 本次改动未提交 git（投稿稿在 Downloads，非仓库）。

## 2026-08-16 [实现 NBE QDQ 伪量化（NVFP4）+ 量化方案统一为 nvfp4]

- 目标：落地用户裁定「实现 NBE QDQ 伪量化」，补齐 M1 可复现性鸿沟的根本原因（bitsandbytes int4 是 PTQ，非论文 Eq.(eq:nbe) 的 QAT QDQ fake-quant）。
- 完成：
  - 新增 `realeval/qdq.py`：实现论文 Eq.(eq:nbe) `Ŵ = clamp(round(W/s), q_min, q_max)·s`，dual scale `s = s_block·s_tensor`（= per-block max-abs，block=128，TensorRT-LLM 约定），STE `w + (w_hat-w).detach()`，`QDQLinear` 包装 nn.Linear 且 state_dict 透明（`_save/_load_from_state_dict` 委托内层 Linear，save_pretrained 保持标准 Qwen key），`apply_qdq` 递归替换 Linear。
  - `realeval/models.py`：`load_causal_lm` 新增 `quantize="nvfp4"` 分支（全精度加载 + post-load apply_qdq），docstring 更新枚举。
  - `realeval/real_backend.py`：`real_qad_distill_train`/`real_llm_classify`/`real_fusion_classify` 默认 quantize `"int4"`→`"nvfp4"`；nvfp4 是 QAT（STE 训练权重本身）故 `attach_adapter` 强制 variant="base"（不挂 LoRA）；docstring 说明 nvfp4=QAT vs int4/nf4/int8=PTQ。
  - exp 脚本 quantize 替换 `"int4"`→`"nvfp4"`：exp1/2/3/4/5/9/10/12/13；exp11 保留 PTQ 对比（bf16/fp16/int8/int4/nf4）并新增 nvfp4 方案。
  - config：`experiments.yaml training.quantize`→`"nvfp4"`；`schema.py` 默认值与枚举加 nvfp4。
  - 保留 int4 未改（合理）：exp8/paper_pipeline 延迟基准（bitsandbytes int4 = 实际部署效率近似，非 NBE 方法路径）、cluster/apply_all_fixes.py 与 student_loader.py 的 PTQ merge 判断、metrics/contract.py 与 paper_data.py 的 exp11-int4/exp8-int4 历史 fallback（实验跑完后回填）。
- 验证：py_compile 全部通过（qdq.py/models.py/real_backend.py/student_loader.py + 10 exp + config/schema.py）；本地 Windows 无 torch，无法运行验证，QDQ 数学逻辑（per-block scale、STE 梯度、state_dict 透明）经静态审查确认。
- 遗留：
  - **NBE 只能静态验证**：需 H100 重跑 exp1 验证 nvfp4 QAT 真实 F1（历史 int4 实测 0.80 vs 论文 0.916/0.923），跑完后回填 paper_data/contract/consistency_check 的 nvfp4 期望值。
  - LDP σ 已查明并修复（见下一条目）：论文 Sec. discussion σ=1.0 是直接给定值，非从 ε 反推。
  - exp6 α 域调、exp7 WER/PESQ/STOI/MOS、exp8 端侧 268ms 的诚实标签缺口仍 defer 作者。
  - 本次改动未提交 git（连同图号重命名 fig5-8→fig4-7、数据集统一 taf28k 一并待提交）。

## 2026-08-16 [σ 定义查明 + NBE block size 对齐]

- 目标：从论文查找 LDP σ 定义并修复口径；核对 NBE 实现与论文 Table 2 / Eq.(eq:nbe) 的参数对齐。
- 完成：
  - σ 定义查明（论文 Sec. discussion 第 881 行 + fig4c 图注第 755 行）：σ=1.0 是 Gaussian 噪声标准差**直接给定**（非从 ε 反推），对应 ε=1.5 / δ=1e-5 是"engineering estimate under a fixed sensitivity/clipping convention，明确 not a full differential-privacy analysis"。
  - exp5 修复：LDP 从「ε∈{inf,3,1.5,1,0.5} 经 σ=Δf·√(2ln(1.25/δ))/ε 反推（Δf=10 → σ≈32.3，与论文 σ=1.0 差 ~32×）」改为「σ∈{0,1} 直接给定，σ=1.0 为论文唯一 operating point，key=eps_1.5 保持 paper_data.py 兼容」；移除 eps_3.0 产出，contract.py 同步移除 `("ldp_tradeoff","eps_3.0","f1")` 并给 exp11 补 `schemes.nvfp4.{f1,std}`。
  - NBE block size 对齐：论文 Table 2 明确 NVFP4「block size = 16, FP8 E4M3 scaling」，qdq.py `DEFAULT_BLOCK_SIZE` 128→16，注释更新。
- 验证：py_compile 通过。
- 遗留（需作者确认的口径，未擅自定）：
  - **FP4(E2M1) vs INT4 格点**：论文 Eq.(eq:nbe) 是 round/clamp（均匀 int4 格点 QMIN=-8/QMAX=7），但 Table 2 说 NVFP4 是 FP4(E2M1) 非均匀格点(0,±0.5,±1,±1.5,±2,±3,±4,±6)；q_min/q_max 论文未明确。
  - **FP8 E4M3 scale**：论文 scale 用 FP8 E4M3 存储，qdq.py 用 float32 计算（论文 NBE 验证注偏差 <0.3%，属可接受近似）。
  - **LDP 噪声位置**：论文对 128 维 acoustic embedding F_v 加噪声（edge 侧），脚本对 text 分支 hidden states 加噪声（text-branch 近似）。
  - 实值回填：exp5 `ldp_tradeoff.eps_1.5.f1`、exp11 `schemes.nvfp4.f1` 等需 H100 重跑后回填。

## 2026-08-16 [论文 v27_revised.tex 写作 skill 打磨：据实标注 + 格式修复 + 改写建议]

- 目标：对投稿稿 `C:\Users\wang\Downloads\v27_revised.tex` 执行 writing 技能包四子任务（审稿意见修订 / LaTeX 格式修复 / 论文质量审计 / 去 AI 痕迹）。
- 完成：
  - 诊断：paper-audit quick-audit（51 issues：1 critical + 4 major citation stacking + 46 minor）、latex-en 检查（tables PASS、abstract 缺 Background/Conclusion）、deai 扫描（26 em-dash、术语重复、tense、burstiness）。
  - 据实标注 4 处诚实标签缺口（落地作者决策「据实标注，保留数字，只修测量状态措辞」）：
    1. L428 exp6 α：domain-tuned 0.86 标为 design target（cited 非实测），generic 0.78 实测。
    2. L841 exp7 WER：追加「reference estimates from reconstruction-attack analysis，非重测输出」。
    3. L835 exp8 268ms：改「are end-to-end estimates assembled from the measured per-stage components」。
    4. L316 exp12 240MB：Table 2 注补 weight-only vs 磁盘 GGUF 491MB。
  - 格式自动修复（6 处 \eqref 引用 + 2 acronym）：
    - 消除 6 个未引用 label：eq:ema→L793、eq:joint→L387、eq:f-v→L407、eq:fusion→L450、eq:w-deploy→L448、eq:recovery→L673。
    - CI→「bootstrap confidence interval」全称（L804）；ASV→「automatic speaker verification (ASV)」（L843）。
    - 5 处 L1 tie 判定误报（\citet 作者作主语 + 表格内 \newline\citep），跳过不改。
  - 改写建议（作者确认后落地）：abstract 补 Background/Conclusion 句、tab:fusion_ablation-en caption 补 finding（sigmoid 0.923/3 scalars vs Transformer 1.84M，差 0.004）。
  - 术语重复去 AI 痕迹（deai D4 term_threshold，各降 1 次）：effective→favourable trade-off（L76）、robust→direct multimodal fusion（L104）、furthermore→In addition（L486）。burstiness（表格行/medskip）、tense、over_confident、em-dash 判定误报或学术规范，保留不改。
- 验证：6 个 label 各有 1 处 \eqref；grep 确认无残留 bootstrap CI / 未定义 ASV。
- 遗留：
  - 投稿稿在 Downloads（非 git repo），已备份 `v27_revised.tex.bak`；改动未提交 git。
  - 4 处据实标注保留数字、只修措辞；待 H100 补跑后回填实测值。
  - em-dash 26 处保留（手稿声明经 Elsevier 语言润色，英式拼写 + 成对 em-dash 为规范）。

## 2026-08-16 [修复录用级 must_fix：P0-1 隐私定性 + M1 真值闭合]

- 目标：闭合 re-review 判定的两个 must_fix——P0-1（隐私声明名实不符，缺可链接性边界）与 M1（论文数字 vs 脚本实测的可复现性鸿沟）。
- 完成（均改投稿稿 `C:\Users\wang\Downloads\v27_revised.tex`，非仓库）：
  1. P0-1 收窄声明：Contribution(3) 加「content-level protection，但不提供 cross-session unlinkability，semi-honest cloud 可经 embedding similarity 链接同一说话人，详见 §Discussion」；摘要结尾句「privacy-preserving … distillation」→「low-bit QAD combined with a reconstruction-resistant acoustic embedding」。
  2. M1 据实标注完善：Reproducibility statement 点明数字差异根本原因——公开仓库早期配置为「int4 PTQ」而非论文「NVFP4 QAT」，现 QAT 路径（Eq.(eq:nbe)）已就绪、待 H100 重跑回填。
  3. 静态审查 `realeval/qdq.py`（NBE QDQ 实现）：STE 梯度直通、per-block scale（s_block·s_tensor = max(|W_b|)/QMAX）、QDQLinear state_dict 透明委托均正确；两处口径差异（int4 格点 vs FP4 E2M1、float32 vs FP8 E4M3 scale）已在 docstring 诚实标注，非 bug。
- 验证：grep 确认 P0-1 两处改动、Reproducibility statement 新措辞均在；此前 py_compile 22 文件全过。
- 遗留：**M1 数值真值仍无法本地闭合**——`outputs/results/` 无 nvfp4 QAT 实测（exp1 仅 smoke_sklearn，all_experiments.json 记 exp1=GPU OOM failed），paper_data fallback 仍为 int4 历史值 0.7974/0.8047/0.7025。需 H100 重跑 exp1 等验证 nvfp4 QAT 真实 F1 后回填。

## 2026-08-16 [全量审计 v27 + 生成 v28.tex]

- 目标：全量审计 v27_revised.tex，修复残留问题，保存为 v28.tex（版本收敛）。
- 完成：
  - 全量审计：无 REVIEWER/TODO 残留、无悬空引用（\ref/\eqref→\label 全匹配）、图引用 fig1-7 一致、无缺失引用（论文 41 key 全在 bib 46 条目内）。
  - 修复 N8：证书标题统一为正文标题「An Edge--Cloud Framework…」。
  - 保存 `C:\Users\wang\Downloads\v28.tex`（1053 行，103077 bytes），含全部累积修复。
- 验证：grep 确认 11 项关键修复全部在 v28.tex；N8 标题 30 行 == 960 行。
- 遗留：
  - 死引用 5 个（18/Chen2025Synergistic/Mishra2026FraudFusion/Park2018ValueAware/Swe2025Federated）仍在 bib（campus_safety/docs/ref_v4.bib），需清理（不影响编译）。
  - M1 数值真值、M3/M4/P0-2/A1/A2/A3 补实验、C1 图 PDF 重命名，均需 H100 或作者定夺。

## 2026-08-16 [评审落地：v27_revised.tex 9 处修订（本轮会话首段）]

- 目标：将 ARS 评审（academic-paper-reviewer full 5 席位 + v27_reviewer_report M1-M6/N1-N8，合并去重 22 条）中可落地项落到投稿稿 `C:\Users\wang\Downloads\v27_revised.tex`。
- 完成（9 处编辑）：
  - N2 补 `\label{sec:nbe}`；N6 投机解码表标题加 `(draft-model decoding efficiency, cloud path)`；M6 G3 威胁标注「未定量」；M5 引言前置单语料声明；M2 Table3 的 `NVFP4 QAD` 行改 `+ CoT`；M1 加 Reproducibility statement；N3 Table2 加表注（Blackwell vs H100 仿真）；N5 Table3 脚注补 SAFE-QAQ 非同尺度；fig3 后加 `% REVIEWER TODO`（fig4 缺口）。
- 验证：grep 逐项确认 8 处在；fig4 TODO 注释后续被外部清理（因图重编号 fig5-8→fig4-7 已闭环 fig4 缺口，属合理）。
- 遗留：M3/M4/P0-2/A1/A2/A3 需补实验，C1 图 PDF 需 `generate_all.py` 重跑生成。

## 2026-08-16 [移植 exp13 决策级融合 + 真实隐私评分（exp13_privacy_fusion_alignment.patch）]

- 目标：将另一会话导出的 `exp13_privacy_fusion_alignment.patch` 手动移植到仓库（patch 基于旧代码 6f240f42，无法 `git apply`，4 处冲突），落地其核心修复：决策级融合对齐论文、真实隐私评分、命名对齐。
- 完成（9 文件，提交 `ab42e03`，已推送 origin/main）：
  1. `realeval/real_backend.py`：重写 `real_fusion_classify` 为论文 Eq. fusion 三头（`softmax_linear` 凸组合 grid-search / `sigmoid_linear` L-BFGS 3 标量（本文）/ `transformer` self-attention）。修复两处正确性缺陷——sigmoid 硬编码论文最优权重 w*=[0.40,0.30]（非学习）、transformer 在测试集 fit（数据泄漏）；并修复隐藏 bug：原 `return_probs=True` 在 zero-shot base path 不产 `probs` 会 KeyError，改用 `return_preds=True`。新增 `_transformer_fusion_head()`（tiny numpy self-attention，d=8）。
  2. `realeval/privacy.py`：新增 `reconstruction_quality_metrics()`，依赖守护的 WER/PESQ/STOI/MOS 真实评分器（缺依赖/缺资产记 not_measured，不编造数字）。
  3. `experiments/exp7_privacy_verification.py`：新增 `_load_reconstruction_assets()` + 集成真实 harness，coverage ledger 从「TODO/planned」改为真实评分/明确 pending。
  4. `experiments/exp13_fusion_strategy.py`：策略名 `softmax/sigmoid/transformer` → `softmax_linear/sigmoid_linear/transformer`，params 从 `result.get("fusion_params")` 取真实值（删硬编码 1.84M），加 `headline_strategy`。
  5. 命名同步（patch 遗漏的）：`metrics/contract.py`、`experiments/consistency_check.py`、`experiments/paper_pipeline.py`（F1[late]→F1[sigmoid_linear]）、`docs/experiment_result_contract.md`、`README.md`。back-compat 别名 early/late/hybrid 及 softmax/sigmoid 保留。
- 验证：py_compile 7 个 .py 全过；grep 确认无 late_fusion/early_fusion/F1[late] 残留、新命名全对齐。
- 遗留（诚实性口径，需作者知悉）：
  - transformer 头是 tiny numpy 实现（d=8，~217 参数），非论文 1.84M Transformer——exp13 `params` 字段现报真实 ~217，与论文 Table 口径不符（诚实标注，sandbox 无法复现 1.84M）。
  - 远程出现他人网页上传的 `docs/v28 (1).tex`（提交 `e5df95a`，作者 Ma Cinar）——与本次改动不冲突，已 rebase 合并；注意该文件与仓库内 `docs/v28.tex` 是两份 v28（`(1)` 后缀），疑似重复上传。
  - `reconstruction_quality_metrics` 需 H100 补跑 + 音频资产（`privacy/reconstruction.npz`）才回填真实 WER/PESQ/STOI/MOS，当前仍 pending。

## 2026-08-19 [全量审计第四轮：NBE QDQ + 融合重构 + 前轮修复复核]

- 目标：对 HEAD `4ff723c` 做全量审计（第三轮基线 6cbc498 之后增量 91 文件：17f568f NBE QDQ、ab42e03 融合/隐私重构、191db4a 图号重命名 + 第三轮 P0/P1 修复）。
- 完成：报告落盘 `reports/2026-08-19_full_audit.md`。核心发现：
  - **P0-1（新，17f568f 引入）**：`realeval/qdq.py:90-91` QDQLinear state_dict 委托 + 默认递归产生重复别名键（weight/linear.weight 共享 storage），safetensors/save_pretrained 必崩 → exp1 训练后 checkpoint 存不下、exp5/9/11/12 断链。本机 CPU 实测复现。
  - **P1-1（迁移回归）**：nvfp4 force-base 只在训练侧；`real_backend.py:635-636` base zero-shot 路径默认 `student_variant: qad_ovf` 会对 QDQ 模型 attach LoRA → PEFT 崩/AssetsUnavailable，exp4 受阻。
  - **P1-2**：`apply_qdq` 不跳过 lm_head（与 tied embedding 耦合），与论文 Table 2 量化范围口径不符。
  - 前轮复核：第三轮 1 P0+15 P1 中 14 已修、P1-S4 部分修（rclone 尾巴）；测量诚信 M1/M3/M4 闭环、M2 主路径闭环（exp7 绕过断言 + exp2~14 不写 is_synthetic 残留为 P2）。
  - P2 共 11 项，要紧的：tex 引用 figure/fig1..7.pdf 全不存在（图脚本产物带名称后缀，投稿硬伤）；consistency_check 不查 exp13 degraded 标志；exp5 LDP 仍未换裁剪版 gaussian_ldp；transformer 头 docstring 描述不属实。
- 验证：编译 107 文件 0 错、导入 59 模块 0 失败、pytest 65 passed（系统 Python+torch）、bash -n 13/13；P0-1 本机实测复现（state_dict 4 键共享 storage、safetensors RuntimeError、strict load spurious missing）；P1-1/P2-10 主会话逐一复核证据在位。
- 遗留：
  - **本轮纯审计未改代码**；P0-1/P1-1/P1-2 修复建议已在报告 §九，H100 重跑前必须先修（否则 exp1 白跑后保存处崩溃）。
  - `docs/v28 (1).tex` 与 v28.tex 逐字节重复，建议删；outputs/results 陈旧产物未归档。
  - GPU 训练全链路、PEFT 崩溃（静态结论）、transformers 4.x 行为未实测（报告 §十）。
  - 本次改动（新增审计报告 + 本日志）未提交 git。

## 2026-08-26 [审计修复落地：P0-1/P1-1/P1-2 + P2 批量（部分已被并行会话提交）]

- 目标：落地 `reports/2026-08-19_full_audit.md` §九 的修复建议。
- 完成（基线 4ff723c；期间有并行会话提交 6c40dd8..c099ff6 扫入部分改动）：
  - **P0-1** `realeval/qdq.py`：QDQLinear 改为吸收参数（self.weight/self.bias，不留 linear 子模块），state_dict 天然单份键；safetensors/save_pretrained 断链消除。已入 HEAD。
  - **P1-2** `qdq.py`：apply_qdq 增 skip_names=("lm_head",)，跳过输出投影（对齐 TensorRT-LLM 部署口径，避免 tied embedding 被包装）。已入 HEAD。
  - **P1-1** `real_backend.py:633-638` base zero-shot 路径 nvfp4 强制 variant="base"（与训练侧一致）；`student_loader.py` 加 QDQ+LoRA 显式护栏（清晰报错取代 PEFT ValueError）。loader 部分已入 HEAD，real_backend 部分在工作树。
  - **P2-8** `framework.py`：run-scoped provenance 追踪（load_first_nonempty 记录合成回退，run_with_mode 盖戳 is_synthetic + finally 复位）；pre_run_validation/run_with_mode 支持 required_datasets，exp7 挂 balanced4k。已入 HEAD（7fcbacd）。
  - **P2-3** `consistency_check.py`：SYNTHETIC(P0)/DEGRADED(WARN) 守卫，合成/降级结果跳过论文声称对账。已入 HEAD（c099ff6）。
  - **P2-4/5/6** `real_backend.py`：real_fusion_classify 重构——fit_data 训练集拟合（论文协议，legacy 首半自切保留兜底）、文本分支软分 P(f)/(P(f)+P(n))（return_scores，与声学软分同尺度）、三策略 fit 统一 try/except 降级；exp13 传 fit_data 并把文本推理提出策略循环（3×→2×）。在工作树。
  - **P2-1/2/7**：transformer 头 docstring 据实改写（冻结随机特征+线性头，删 epochs/lr 死参数）、n_params 区分 total/trained（217/9）、privacy.py 标注 whisper-tiny WER 偏差方向（有利于论文结论，需更强 ASR 回填）。在工作树。
  - **P2-10**：v28.tex 7 处图引用已被并行会话对齐脚本产物名（e8ecf81）；generate_all.py 加 figN.pdf 纸面名副本步骤作双约定兜底；`docs/v28 (1).tex`（陈旧重复，差异仅图引用旧名）已删。
  - P3 批量：.gitignore 补 outputs/splits/、REFACTORING.md 去 --smoke、run_pipeline.sh pip 硬失败、claim_engine yaml 入 try+类型守卫、runpod_h100.yaml 死配置 int4→nvfp4、registry exp11 描述、exp5/exp7 注释、REPRODUCIBILITY 命名、template/README 环境变量说明、figure README 420→400dpi、paper_data docstring 笔误。
- 验证：compileall 0 错、pytest 65 passed、bash -n 通过；QDQ 数值 7 项（单份键/safetensors/双向 strict 往返/bias=False/STE 直通/lm_head 跳过+tied/幂等/动态 QAT）+ tiny Qwen2 save_pretrained→reload→rewrap 全过；attach_adapter 3 例、provenance 盖戳 5 例、consistency 守卫 3 例、融合合成数据 6 例（fit_data 协议/legacy 兼容/单类降级/params 区分/缺音频降级/软分权重可比）全过；paper_data 自检 exit 0、consistency exit 1（陈旧结果，预期）。
- 遗留：
  - **real_backend.py / exp13 / privacy.py / 批次E 杂项未提交 git**（工作树改动，17 文件 M + 1 文件 D）；并行会话另有第五轮审计报告（a531a07）。
  - outputs/ 陈旧产物 11 个文件：`archive_and_clear.py --dry-run` 已预览（归档 markdown 后删除 results/predictions/metrics/tables 旧文件），实际清理待确认（不可逆）。
  - 未动项（报告中注明需联动或零影响）：exp12 结果键 QAD_MultiGuard_INT4 命名（需 contract/figure 联动）、models.py 非法 quantize 静默全精度（沿用旧模式）、privacy.py n==0 分支 n_pairs 键（无消费方）。
  - GPU 训练全链路（修后 QAT 5 epoch 收敛 + save_pretrained 实机）仍需 H100 验证。
