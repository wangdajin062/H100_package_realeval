# 记忆日志（Memory Log）

> 本文件是跨会话的工作记忆：每次任务/会话结束时，由当次会话追加一条记录，
> 供后续会话快速恢复上下文。记录格式见下方条目模板。
> 约定来源：根目录 `AGENTS.md`。

## 条目模板

```
## YYYY-MM-DD [会话主题]
- 目标：本次要做什么
- 完成：实际做了什么（文件/提交哈希）
- 验证：测试/检查结果
- 遗留：未完成或需注意的事项
```

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
