# AGENTS.md — 项目工作约定

## 记忆日志（强制）

**每次任务/会话结束前，必须把工作摘要追加到 `reports/MEMORY_LOG.md`**，格式：

```
## YYYY-MM-DD [会话主题]
- 目标：本次要做什么
- 完成：实际做了什么（关键文件/提交哈希）
- 验证：测试/检查结果
- 遗留：未完成或需注意的事项
```

规则：
- 只追加，不改写历史条目；条目按时间倒序之后的顺序（新的追加在文件末尾）。
- 开始任务前先读 `reports/MEMORY_LOG.md` 最后 1–2 条恢复上下文。
- 记录提交哈希时以 `git log --oneline -1` 为准，不要凭记忆填写。

## 关键项目约定

- `outputs/` 整体 gitignored（生成物），结果文件通过 scp/同步脚本回收，不要 `git add outputs/`。
- `docs/figure_scripts/` 的 fig 脚本尽量不改；数据桥接走 `paper_data.py` 的 `_from_result()`（实测值为 None 时显式报缺，禁止静默回退硬编码常量）。
- 无 smoke 路径：`run_with_mode` 只跑 paper 路径，`--smoke` 已删除，不要在脚本/文档中引用。
- 实验种子：实验内多 seed 用 `seed_base_from_config(config)`（默认 1000），不要硬编码 `set_seed(1000+s)`，否则 claim_engine 的 seed 注入失效。
- 测试隔离依赖 `REALEVAL_OUTPUT_ROOT`；新增写输出的代码必须走 `realeval/io/paths.py`，不要手写 `outputs/...` 路径。
- 验证基线：`pytest tests/ -q` 应全绿（当前 65 passed）；`python -m experiments.consistency_check` 在 GBK 控制台也必须能跑完（只用 ASCII 输出）。
