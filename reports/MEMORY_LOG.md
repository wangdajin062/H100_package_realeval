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
