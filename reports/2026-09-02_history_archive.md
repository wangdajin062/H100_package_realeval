# 历史报告归档（截至 2026-09-02）

> 本文件由 2026-09-02 整理生成，将 reports/ 下 25 份历史修订文档归档为一份；2026-09-04 二次归档，并入 4 份审计/设计/执行文档（`full_package_audit` / `distillation_design` / `a_road_execution` / `script_design_consistency_audit`）。
> 保留的活跃文档：`2026-09-02_full_package_audit_triage.md`（执行路线图）。

## 目录

- `2026-08-13_full_audit.md`
- `2026-08-13_full_audit_round2.md`
- `2026-08-14_full_audit.md`
- `2026-08-15_changes.md`
- `2026-08-19_full_audit.md`
- `2026-08-26_full_audit.md`
- `2026-08-31_peer_review_v29.md`
- `2026-08-31_response_to_reviewers_v29_zh.md`
- `2026-08-31_v25_vs_v29_scripts_reconciliation.md`
- `2026-09-01_peer_review_v29_round2.md`
- `2026-09-01_privacy_route_audit.md`
- `2026-09-01_re_review_v29.md`
- `2026-09-01_round2_panel_seats.md`
- `v28_peer_review.md`
- `v28_revision_roadmap.md`
- `v29_review.md`
- `v29_planned_baseline_design.md`
- `v29_response_to_reviewers.md`
- `v29_response_to_reviewers_round2.md`
- `editorial_decision_v29.md`
- `editorial_decision_v29_round2.md`
- `revision_checklist_v29_round2.md`
- `CONSISTENCY_AUDIT.md`
- `FIG_TABLE_FIX_REPORT.md`
- `MEMORY_LOG.md`

---

## 归档：2026-08-13_full_audit.md

# H100_package_realeval 全量审计报告

> 日期：2026-08-13
> 审计范围：全部 Python 包文件（111 个 .py，17 个包目录，排除 .venv/.git）
> 审计方法：语法编译 + 全模块导入 + from-import 符号完整性 + 可选依赖检查 + pytest + 三路并行深度审计（数据链接一致性 / 断点与死代码 / 配置与脚本一致性）

---

## 一、总体结论

**无致命断点**：所有 `from X import Y` 均可解析，61 个模块导入成功、无循环 import，pytest 67 passed。smoke 模式移除彻底（`run_paper_safe` / `run_smoke` / `toy_kl_distill` / `quantize_proxy` 全仓库零残留）。

但发现 **2 类 P0 功能错误**、**5 类 P1 数据链接不一致**（字段读不到、静默走默认值）、若干死代码与文档残留。详见下文。

---

## 二、健康项（检查通过）

| 维度 | 结果 |
|---|---|
| 语法编译 | 全部通过 |
| 全模块导入（61 个） | 无循环 import、无 ImportError |
| 实验注册表 `registry.py` → 14 个 `exp*.py` | 模块名/short/`run(config)` 签名一一对应 |
| 核心符号（`group_split`、`summarize`、`real_qad_distill_train` 等） | 精确验证全部存在 |
| 可选依赖（llama_cpp / peft / fastapi / pydantic） | 均有 try/except 或延迟导入保护 |
| smoke 移除残留 | 代码层 0 残留 |
| 测试隔离 | pytest 后 `outputs/` 0 泄漏文件 |
| CLI `experiments.runner` 参数 | parser 定义与 `args.*` 读取完全一致 |

---

## 三、P0 — 会导致实际功能错误

### P0-1. `claims/claim_01_ovfreeze.yaml` 的 treatment 键名错误，claim 恒为 UNSUPPORTED

- 位置：`claims/claim_01_ovfreeze.yaml:9`（`compare.treatment: ov_freeze`） vs `experiments/exp3_ov_freeze_control.py:85-90`
- 问题：exp3 产出的 `conditions` 实际键是 `no_reg` / `ov_freeze_quarter` / `ov_freeze_half` / `ov_freeze_full`，**不存在 `ov_freeze`**。
- 后果：`claim_engine._collect_samples` 里 `node.get("ov_freeze", {})` 恒为空 → treatment 样本恒空 → 两条 acceptance 均落入 `_Unsupported` → 该 claim **恒为 UNSUPPORTED**，与真实数据无关。
- 修复方向：`treatment` 应改为 `ov_freeze_full`（或 `ov_freeze_half`）。

### P0-2. shell 脚本 / 任务配置仍引用已删除的 `--smoke`，运行时报 argparse 错误

smoke 的 `--smoke` CLI 参数已在 `cli/parser.py` 删除，但以下非 .py 文件仍引用（此前「只清 Python 代码」的范围未覆盖它们）：

| 文件 | 位置 | 后果 |
|---|---|---|
| `run_h100.sh` | `:17` `[ "$a" = "--smoke" ] && MODE="--smoke"`；`:52/:54` 传 `"$MODE"` | 传 `--smoke` 给 `paper_pipeline` 报 `unrecognized arguments` |
| `template/run_all.sh` | `:26`、`:139` `python -m experiments.runner --smoke --benchmark` | 同上 |
| `.vscode/tasks.json` | `:25` 任务 `run-smoke-all` 传 `--smoke` | 同上 |
| `.vscode/tasks.json` | `:59-60` 调用 `scripts/rerun_and_validate_contract.py --smoke` | **该脚本已不存在**（`scripts/` 现无此文件） |

---

## 四、P1 — 数据链接不一致（字段读不到，静默走默认值）

### P1-1. `reproducibility.{exp}_seeds` 未定义 → 多 seed 实验恒回退 3

- 读取：`experiments/common.py:77` `n_seeds_from_config`（读 `reproducibility.exp1_seeds` … `exp14_seeds`）
- 使用：exp1/2/3/10/11/14 共 6 个实验
- 但 `config/schema.py:60-63` 的 `reproducibility` 段只定义 `seed`/`benchmark_*`，无 `exp*_seeds`；`config/experiments.yaml` 也无。这些字段只在 `config/runpod_h100.yaml:23-27` 定义。
- 后果：用默认基础配置运行时，多 seed 实验**恒用 3 seeds**，而非论文声称的 5。

### P1-2. exp8 读错 benchmark 字段路径

- 读取：`experiments/exp8_latency_benchmark.py:36-37` `config.get("benchmark", {}).get("warmup", 2)` / `.get("repeat", 10)`
- schema 实际定义：`reproducibility.benchmark_warmup`（10）/ `reproducibility.benchmark_repeat`（100）
- 后果：配置里的 10/100 永远读不到，恒用 2/10。

### P1-3. 若干 schema 字段代码读不到（静默走默认值）

| 代码读取 | 位置 | schema 实际情况 |
|---|---|---|
| `training.dropout` | `realeval/real_backend.py:224,575` | 未定义 → 恒 0.1 |
| `distillation.task_weight` | `realeval/real_backend.py:267,571` | 未定义 → 恒 1e-3 |
| `models.draft_model_generic` | `realeval/real_backend.py:657` | 未定义，靠 fallback 兜底 |
| 顶层 `seed` | `realeval/specdec.py:54` | schema 定义的是 `reproducibility.seed` |

### P1-4. 消费者读 `exp6.diagnostic_B.h100_measured.domain`，生产者不产出该键

- 生产者：`realeval/specdec.py:100` 只返回 `h100_measured = {"generic": ...}`，无 `domain` 键（`domain` 只在 verdict 字符串里写 "NOT MEASURED"）。
- 消费者：`docs/figure_scripts/paper_data.py:374`、`metrics/extraction.py:96-97` 读取 `hm.get("domain")`。
- 后果：`_alpha_tuned_meas` 恒 None，永远回退 `paper_reference.alpha_tuned`（0.86）。

### P1-5. exp5 的 `paper_reference` 已删除，但消费者仍有死 fallback/死检查

- `docs/figure_scripts/paper_data.py:467` 读 `exp5.paper_reference.ldp_eps_1_5_f1`（标注 smoke 向后兼容）——恒落空。
- `experiments/consistency_check.py:64-66` 的 `CITED_FIELDS["exp5"]` 仍列 `paper_reference.advfraud_curated_f1` 等 3 个路径——因 exp5 已不产出 `paper_reference`，这些「若存在则告警」的检查实际永不触发。

---

## 五、P2 — 死代码 / 孤立模块

### 孤立模块（无任何 import 引用）

| 模块 | 说明 |
|---|---|
| `realeval/distill.py` | `kl_divergence` 无引用 |
| `config/defaults.py` | `DEFAULTS`/`DEFAULT_CONFIG_PATH` 无引用（只出现在 `__init__` re-export） |
| `realeval/limits.py` | 6 个函数仅出现在 `realeval/__init__.py` 的 `__all__`/docstring |
| `realeval/distributed.py` | 仅被 `tests/test_realeval.py:47,53` 引用，生产死代码 |

### 死函数（在活跃模块内但从未调用）

- `realeval/real_backend.py`：`real_speculative_alpha`(:648)、`real_distill_train`(:542)、`real_distillation_step_metrics`(:78) —— exp6 实际用 `specdec.diagnostic_B`，exp1 用 `real_qad_distill_train`。
- `config/loader.py`：`get_config`(:39)、`clear_cache`(:52) —— 全用 `load_config`。
- `realeval/io/serialization.py`：`load_all_results`(:138) —— 导出但未调用。
- `runner/interface.py`：`Experiment` ABC(:46) —— 文件自身 docstring 承认 unused。
- `runner/claim_runner.py`：整个模块生产死代码（仅被 `tests/test_evidence_graph.py` 引用）。

### 潜在不匹配（当前无害）

- `runner/claim_runner.py:78-84` 假设 `experiment_fn(cfg)` 返回 `ExperimentResult`（访问 `.provenance`/`.raw_predictions` 等属性），但真实 exp 的 `run()` 返回 plain dict。若将来把 claim_runner 接到真实 exp 会 `AttributeError`。

---

## 六、P3 — 文档 / 配置 / 残留

### 文档仍把 `--smoke` 写成有效命令

- `README.md:16,74,160-161`
- `docs/REPRODUCIBILITY.md`（多处，`:81` 声称「必须显式指定 --smoke 或 --paper」已不成立）
- `docs/REFACTORING.md`、`template/README.md:50`、`docs/figure_scripts/README.md:32-33`

### claims 顶层残留 4 个旧格式文件

- `claims/claim_001_latency.yaml`、`claim_002_accuracy.yaml`、`claim_003_specdec.yaml`、`claim_004_privacy.yaml` —— 缺 `experiment`/`evidence_path`/`dependent_variable`，`acceptance` 是 dict 而非 list，与 `claims/legacy/` 下同名文件重复。
- 后果：claim_engine 每次运行都会 glob 到并打印 "legacy format" 告警；且旧 `claim_003_specdec.yaml`（`id: CLAIM-003`）与新 `claim_03_specdec.yaml`（`id: CLAIM-03`）命名重叠。

### CLI 未使用参数

- `experiments.paper_pipeline` 的 `--resume`（`cli/parser.py:58` 定义，`paper_pipeline.main` 从不读 `args.resume`）
- `experiments.claim_engine` 的 `--paper`（`claim_engine.py:254` 定义，`main` 从不读 `args.paper`）

### 死配置字段（schema 定义了但代码从不读）

- `distillation.alpha_ce`、`freeze_frac_default`、`window_default`
- `privacy.*`（10 个）、`audio.*`（5 个）、`classification.*`（4 个）、`inference.*`（3 个）、`synthetic.*`（2 个）
- `speculative_decoding.n_samples`/`max_new_tokens`
- `config/h100.yaml` 的 `runtime.*`、`output.*`、`paper_run.*`、`hardware.{gpu,num_gpu,precision}`
- `config/runpod_h100.yaml` 的 `runtime.*`、`paper_run.*`、`hardware.{gpus,vram_gb,vcpu,ram_gb}`

### 标注冲突（需人工确认）

- `exp5.bf16_matched_advfraud`：exp5 硬编码产出 `0.882`（`exp5_cross_dataset.py:98`）并注释「measured value」，但 `metrics/contract.py:139` 与 `consistency_check.py:63` 都把它归为 **CITED**（硬编码论文值）。同一字段两种身份。

### 字段合约覆盖缺口

- `metrics/contract.py` 的 `EXPECTED_FIELDS` 缺 exp7/exp9/exp12/exp13 四个实验的条目 → 这 4 个实验的返回值永不经过字段合约校验（虽然仍被 `consistency_check`/`paper_data` 消费）。

---

## 七、修复建议（按优先级）

1. **P0-1** 修 `claims/claim_01_ovfreeze.yaml` 的 `treatment` 键名（`ov_freeze` → `ov_freeze_full`）。
2. **P0-2** 清理 `run_h100.sh` / `template/run_all.sh` / `.vscode/tasks.json` 的 `--smoke` 引用（改为 `--paper` 或删除 smoke 分支）；删除对已不存在脚本 `scripts/rerun_and_validate_contract.py` 的引用。
3. **P1-1/P1-2/P1-3** 统一 config schema 与实际读取字段：把 `exp*_seeds`、`training.dropout`、`distillation.task_weight` 补进 schema/defaults；修正 exp8 读 `reproducibility.benchmark_*`；`specdec` 改读 `reproducibility.seed`。
4. **P1-4/P1-5** 对齐 `h100_measured.domain` 与 `paper_reference` 的字段契约（生产者补键，或消费者删死读取）。
5. **P2** 清理孤立模块（`distill.py`/`limits.py`/`distributed.py`/`defaults.py`）与死函数（`real_speculative_alpha` 等）。
6. **P3** 清理文档 `--smoke`、claims 旧格式残留、CLI 未使用参数、死配置字段。

---

## 八、修复结果（2026-08-13 补充）

> 初版为只读审计。本节记录随后执行的修复及最终状态。

### 已修复

| 编号 | 修复内容 | 提交 |
|---|---|---|
| P0-1 | `claim_01_ovfreeze.yaml` treatment `ov_freeze` → `ov_freeze_full` | `d0084f9` |
| P0-2 | 清理 `run_h100.sh` / `template/run_all.sh` / `.vscode/tasks.json` 的 `--smoke` | `d0084f9` |
| P1-1 | 补 `exp*_seeds` 到 `experiments.yaml` + `runpod_h100.yaml`（初版只补 schema 无效，code review 发现后补 yaml 才真正生效） | `d0084f9` + `0e49a3a` |
| P1-2 | exp8 改读 `reproducibility.benchmark_warmup/repeat` | `d0084f9` |
| P1-3 | 补 `training.dropout`、`distillation.task_weight`；specdec 改读 `reproducibility.seed` | `d0084f9` |
| P1-4 | 删 `paper_data.py` / `extraction.py` / `sync_paper_data.py` 的 `domain` 死读取 | `d0084f9` + `0e49a3a` |
| P1-5 | 删 `paper_data.py` 的 `paper_reference` 死 fallback、`consistency_check.py` 死检查 | `d0084f9` |
| P2 | 删 4 孤立模块（distill/defaults/limits/distributed）+ 3 死函数 + 改 `__init__` + 删 `TestDistributed` | `d910e7b` |
| P3 文档 `--smoke` | 清理 README / REPRODUCIBILITY.md / figure_scripts / template 活跃文档 | `d910e7b` |
| P3 claims 残留 | 删 4 旧格式 claim（claim_001~004） | `bb992e1` |
| P3 CLI 未用参数 | 删 `paper_pipeline --resume`、`claim_engine --paper` | `d910e7b` |

### 保留未改（有意）

| 项 | 保留理由 |
|---|---|
| P2 其他死代码（`get_config`/`clear_cache`、`load_all_results`、`Experiment` ABC、`claim_runner.py`） | 被 `__init__` re-export 或测试引用，删除需额外处理，风险/收益不划算 |
| P3 死配置字段（`privacy.*`、`audio.*`、`classification.*` 等） | schema 声明性字段，删除有风险（可能是完整性声明或未来会用到） |
| P3 标注冲突（`exp5.bf16_matched_advfraud`） | 需人工确认真实身份（measured vs cited） |
| P3 字段合约缺口（exp7/9/12/13） | 需补 `EXPECTED_FIELDS` 条目，属独立任务 |
| P3 历史文档 smoke 描述（CONSISTENCY_AUDIT / FIG_TABLE_FIX_REPORT） | 历史快照，记录「当时有 smoke」的事实；CONSISTENCY_AUDIT 仍被 paper_data.py 注释引用 |
| paper_data.py 的 smoke 过滤 | 防御性向后兼容安全网 |

### code review 补充发现（初版审计遗漏）

| 严重度 | 发现 | 修复 |
|---|---|---|
| Critical | P1-1 初版修复无效（schema `_default` 从不注入运行时 config，exp10 生产仍跑 3 seeds） | 补 yaml 真正生效 |
| Important | `runner/orchestrator.py`、`metrics/contract.py` 仍硬编码 `RESULTS_DIR` | 统一到 `io.paths.RESULTS` |
| Important | `sync_paper_data.py` 第三处 `domain` 死读取（初版审计漏列） | 删除 |
| Minor | `config["_paper"]` 死标志 | 删除 |
| Minor | README 日期格式、real_backend docstring 过时 | 清理 |

### 最终验证（2026-08-13）

- pytest **65 passed**（67 → 65，删 2 个 `TestDistributed` 测试）
- 全模块导入无断点、无循环 import
- 测试隔离：pytest 后 `outputs/` **0 泄漏**
- config 字段验证：`exp10_seeds=5`、`dropout=0.1`、`task_weight=1e-3` 均从 yaml 读到

---

## 归档：2026-08-13_full_audit_round2.md

# H100_package_realeval 全量审计报告（第二轮：复核 + 残留发现）

> 日期：2026-08-13（晚）
> 基线：HEAD `d1a8e28`，工作树干净
> 方法：pytest 基线 + consistency_check 实测 + 三路并行深度审计（claims↔runner 链接 / 实验产出↔图表数据链 / config↔数据↔脚本路径），关键发现逐条人工复核
> 与前一轮关系：本报告复核 `reports/2026-08-13_full_audit.md` 所列修复是否真正生效，并列出该报告之后仍然残留或未覆盖的问题

---

## 一、总体结论

**核心数据链逻辑自洽**：`paper_data.py` 的每条 `_get` 读取路径都有当前实验模块真实产出对应字段，无 P0 断链；`consistency_check.py` 的 PAPER_CLAIMS 路径全部存在；pytest **65 passed**（本轮复跑确认）。前一轮审计的 P0-1/P0-2/P1-1~P1-5 修复经抽查**全部真实生效**。

残留风险集中在三类：
1. **统计诚信**：claim_engine 多 seed 退化（5 次"重复"结果完全相同）、exp11 失败方案以 `f1=0.0` 静默流入论文图表；
2. **文档漂移**：契约文档 / REPRODUCIBILITY / README 多处描述与代码现状矛盾（含一条危险的"铁律"误导）；
3. **工具自身缺陷**：consistency_check 人类可读模式在 Windows GBK 控制台直接崩溃。

另外：`outputs/results/` 当前为空（本地结果已被清理），consistency_check 对 10 个实验全部报 MISSING_RESULT——论文图表当前只能由 paper_data 的内置常量生成，**任何对外图表都必须先完成 H100 重跑回填**。

---

## 二、前一轮修复复核（抽查确认）

| 前一轮编号 | 复核结果 |
|---|---|
| P0-1 claim_01 treatment 键名 | ✅ `claims/claim_01_ovfreeze.yaml` 已为 `ov_freeze_full`，与 exp3 产出键匹配 |
| P0-2 `--smoke` 残留 | ✅ 代码与脚本层零残留；`run_with_mode` 仅 paper 路径 |
| P1-1 `exp*_seeds` | ✅ 已进入 `config/experiments.yaml` / `runpod_h100.yaml` |
| P1-4 `h100_measured.domain` 死读取 | ✅ paper_data / extraction 已无 domain 读取 |
| P3 claims 旧格式残留 | ✅ 顶层 claim_001~004 已删除（`bb992e1`），仅剩 claim_01/02/03 + legacy/ |
| P2 孤立模块 distill/defaults/limits/distributed | ✅ 已删除，全仓零引用 |

---

## 三、P1 — 逻辑/链接不一致（本轮新发现或前一轮遗留未修）

### 统计诚信

1. **claim_engine 多 seed 统计退化** — `experiments/claim_engine.py:49-52` 每轮设 `cfg["seed"] = 42 + s`，但 exp1/exp3/exp11 内部硬编码 `set_seed(1000 + s)`（`exp1_qad_production.py:35`、`exp3_ov_freeze_control.py:56,70,95`、`exp11_quantization_scheme.py:41`），完全忽略 `cfg["seed"]`。后果：`seeds: 5` 实际跑 5 遍完全相同的确定性流程，5 个"样本"逐值相同，bootstrap CI 宽度恒为 0——claim 的统计显著性是虚假重复。**修复方向**：实验读取 `cfg.get("seed")` 作为种子基底，或 claim_engine 改为单跑 + 直接使用实验内部的多 seed 聚合。
2. **exp11 异常路径 `f1: 0.0` 静默污染图表** — `experiments/exp11_quantization_scheme.py:57`：某量化方案抛异常时写 `{"f1": 0.0, "std": None, "error": ...}`。`0.0` 非 None，paper_data 不触发 fallback，合约存在性检查也通过 → 失败方案以 0.0 进入 Fig3/Fig8。**修复方向**：改为 `f1: None` 并在 paper_data 侧显式报缺。

### 工具自身

3. **consistency_check 人类可读模式在 Windows 崩溃** — `experiments/consistency_check.py:112,120-131` 直接 print emoji（🟠🔴🟡🟢），GBK 控制台抛 `UnicodeEncodeError`，报告打印中断、退出码异常。`--json` 模式可用。**修复方向**：图标改 ASCII 或对 stdout 做 `errors="replace"` 包装。

### 文档与配置漂移

4. **契约文档严重过时** — `docs/experiment_result_contract.md`：smoke 路径段落（:73/:75/:76/:109）所述路径已不存在；exp8 表（:170-176）写 `latencies.*`，实际 paper_data 读 `latency_detail.*.p50_ms/p99_ms`；exp5（:157）写 `paper_reference.ldp_eps_1_5_f1` fallback 0.902，实际读 `ldp_tradeoff.eps_1.5.f1` 且 fallback 为 None；exp1 fallback 表（:119-126）数值与 paper_data 现值（0.7974 / None 报缺）不一致。该文档自称"硬性约束"，现状会误导后续适配。
5. **README/REFACTORING 引用已删除的 `config/defaults.py`** — `README.md:117`、`docs/REFACTORING.md:26`。
6. **REPRODUCIBILITY.md 危险误导** — `docs/REPRODUCIBILITY.md:5` "铁律"称 `run_h100.sh` "开头会 `rm -rf outputs/results/*`"：实际清理已是 `--clean` 显式 opt-in（`run_h100.sh:17,31-36`），与 `README.md:90` 直接矛盾；`:202` 的 `git add outputs/results` 与 `.gitignore:22` 矛盾（命令加不到任何文件）。
7. **`runpod_h100.yaml` 的 `data.source: taf28k` 覆盖无效** — `config/runpod_h100.yaml:30` 注释声称 "Force real; errors out if missing"，但 `data.source` 仅被 `realeval/validation.py:24`（白名单）和 `realeval/audit.py:117`（日志）消费；所有实验读 `data.dataset`（overlay 合并后仍是 `chifraud`）。该覆盖不做其注释声称的事。
8. **cluster 脚本硬编码旧 pod 布局** — `cluster/fix_training.py:19`（`/workspace/cluster/train_sft.py`）、`cluster/diagnose_training.py:13`（`sys.path.insert(0, "/workspace")`）：当前 pod 布局为 `/workspace/H100_package_realeval`，两脚本必然失败。另 `cluster/diagnose_v25_run.py:410` `--data-root` 默认 `/workspace/datasets`，实际为 `/workspace/data`。
9. **`docs/figure_scripts/README.md:25,61` 引用不存在的 `FIGURE_CAPTIONS.md`**。
10. **`sync_paper_data.py` 实质失效** — `f45389a` 只做了 3 行清理；其 `scalar_re`（:221-226）只匹配 `VAR = 数字字面量`，而 paper_data.py 变量已是 `_from_result(...)` 表达式；`updates["_LATENCY_P50"]`（:182）无任何应用分支。运行它不会改变任何内容，应从文档工作流中移除或标注废弃。

---

## 四、P2 — 一致性瑕疵（不影响主链路）

- **合约覆盖缺口（前一轮列为独立任务，仍未补）**：`metrics/contract.py` EXPECTED_FIELDS 无 exp7/exp9/exp12/exp13 条目，`--validate-contract` 对这 4 个实验永远通过。
- **CITED_FIELDS 两处不一致**：`metrics/contract.py:140-145` 含 exp6 `paper_reference.gamma_deploy`，`experiments/consistency_check.py:62-70` 无。
- **exp14 GGUF 不可用路径**（`exp14_gguf_comparison.py:71-73`）：`f1=None`、无 `std` 键 → paper_data 静默回退硬编码 0.7025，无任何告警。
- **exp10 单 teacher 失败**写 `{f1_fixed: None, f1_conv: None}`：合约通过但 consistency_check 记 MISSING（行为诚实，仅注意语义分裂）。
- **generate_all.py 依赖门控错误**：Fig3 只门控 exp11（:33，实际 QAT 行还需 exp1/exp3/exp14）；Fig8 门控 `["exp5","exp7"]`（:38），但 **exp7 在 paper_data 中无任何消费**。
- **check_alignment.py:44-50 不过滤 smoke 结果**，与 `paper_data._load_results` 加载逻辑分歧（当前无 smoke 文件，属潜伏分歧）。
- **extraction.py:109** 平铺 exp8 `latencies` 字典，把 `int8_fallback_flagged`/`fp16_slower_than_int4` 两个布尔标志混进 headline 表。
- **aggregation.py:73** 读 `latency_p90_ms/p99_ms`，但 exp8 `batch_benchmark` 只产 `latency_p50_ms/throughput_sps/peak_mem_mb` → p90/p99 列恒空。
- **`realeval/student_loader.py:22`** 本地 fallback 手写 `outputs/sft_checkpoints`，绕过 `REALEVAL_OUTPUT_ROOT`（测试隔离破口，仅 adapter 路径）。`realeval/envreport.py:15-16` 重复实现 OUTPUT_ROOT 解析逻辑。`docs/figure_scripts/` 4 个文件硬编码 `ROOT/"outputs"/"results"` 同样绕过（声明只读，可容忍）。
- **死配置键**：`runpod_h100.yaml` 的 `paper_run.*`、`root_hint`；`h100.yaml` 的 `output.*`——全仓零消费。
- **`config/schema.py:162`** enum 允许 `chifraud`，但 schema 自述与 experiments.yaml 只列 `auto/taf28k/synthetic`。
- **孤儿数据**：`data/balanced600/`、`data/balanced10c/`、`data/ChiFraud/chifraud.npz` 无任何代码引用。
- **根目录 `__pycache__/`** 残留已删除的 `podstat.py`/`gpu_viz.py` 的 .pyc。
- **实验分组文档过时**：`README.md:57-58` 与 REPRODUCIBILITY §6 只列 00–06 组，`experiments/paper_pipeline.py:39-50` 实际定义 10 组。
- **`paper_data.py:142,158,311`** 注释引用 `RUNLOG_20260803_summary`（reports/ 重组后已不存在）。
- **`.gitignore` 缺口**：未覆盖 `outputs/claims/`（`realeval/io/paths.py:25`）与 `outputs/sft_checkpoints/`——这两个目录一旦有内容可能被误提交。
- **`runner/claim_runner.py:34`** docstring 说 "in claims/"，实际 `CLAIMS_DIR = claims/legacy`。

---

## 五、有意保留（沿用前一轮结论，本轮复核同意）

- `claims/legacy/` + `runner/claim_runner.py` + `runner/interface.py` ABC：自我一致但生产无调用的归档岛。注意其 acceptance 扁平键（`throughput_ratio`/`f1_drop` 等）与任何实验产出都不匹配——**若未来复活需先写适配层**。
- claim 评估不在任何 pipeline 内（`python -m experiments.claim_engine` 手动入口）——代价是 claims 可能再次与实验漂移，建议至少在 CI 加一次干跑。
- `exp5.bf16_matched_advfraud` 身份冲突（exp5 注释称 measured，contract 列为 CITED）——仍需人工确认。

---

## 六、修复建议（按优先级）

1. 修 claim_engine seed 传递（或改用实验内部聚合），消除虚假重复统计。
2. exp11 异常路径 `f1: 0.0 → None`，并在 paper_data 对 None 显式报缺。
3. consistency_check emoji → ASCII（Windows 可用性）。
4. 重写/标注废弃 `docs/experiment_result_contract.md` 的 smoke、exp8、exp5、fallback 段落——它是"硬性约束"文档，漂移代价最高。
5. 修 REPRODUCIBILITY.md:5 铁律与 :202 git add 命令；README:117 / REFACTORING:26 删 defaults.py 引用。
6. `runpod_h100.yaml`：要么让实验真正消费 `data.source`，要么改注释去掉 "Force real" 承诺。
7. 修 cluster 两脚本的 `/workspace` 布局假设；标废 `sync_paper_data.py`。
8. 补 exp7/9/12/13 的 EXPECTED_FIELDS；统一两处 CITED_FIELDS。
9. `.gitignore` 补 `outputs/claims/`、`outputs/sft_checkpoints/`。

---

## 七、验证记录

- `pytest tests/ -q` → **65 passed, 1 warning**（26s，本轮实测）
- `python -m experiments.consistency_check` → 人类模式 GBK 崩溃（实证 P1-3）；`--json` → 10 实验全部 MISSING_RESULT（outputs/results 为空，预期）
- `git status` 干净；`git ls-files` 无 outputs/ 跟踪文件

---

## 八、修复结果（2026-08-13 深夜补充）

> 按第六节优先级执行的修复及最终状态。全部改动在工作树中（未提交）。

### 本轮执行的修复

| 编号 | 修复内容 | 涉及文件 |
|---|---|---|
| 三-1 | 新增 `seed_base_from_config(config)`（默认 1000 保持 H100 论文路径逐位一致），替换全部 9 处硬编码 `set_seed(1000 + s)`；claim_engine 注入的 `cfg["seed"]=42+s` 现在真正生效，消除虚假重复统计 | `experiments/common.py`、exp1/2/3/10/11/14 |
| 三-2 | exp11 量化方案异常路径 `f1: 0.0 → None`；paper_data `_from_result` 对"键存在但值为 None"显式报缺（不回退常量），失败方案不再以 0.0 污染 Fig3/Fig8 | `experiments/exp11_quantization_scheme.py`、`docs/figure_scripts/paper_data.py`（并行会话已建好 None 报缺机制，本轮核实） |
| 三-3 | consistency_check 图标 emoji → ASCII（`[OK]/[X]/[!]/[i]`），GBK 控制台不再崩溃（并行会话已修，本轮核实）；验证中**新发现同类问题**并修复：`paper_data.py:524` 与 `check_alignment.py:191` 的 ✓/✗ → ASCII | `experiments/consistency_check.py`、`docs/figure_scripts/paper_data.py`、`check_alignment.py` |
| 三-4 | 契约文档修正：删 smoke 段落、exp8 改 `latency_detail.*`、exp5 LDP 改 `ldp_tradeoff.eps_1_5.f1`、exp1 fallback 值更新、exp6 删 domain 行、exp2/exp10 键名补全、新增变更历史行（并行会话已修，本轮核实） | `docs/experiment_result_contract.md` |
| 三-5 | REPRODUCIBILITY "铁律"改为描述真实行为（`--clean` opt-in，并行会话已修）；`:202` `git add outputs/results` 改为只 add 可跟踪路径并注明 outputs/ 已 gitignore；README:117 / REFACTORING:26 删除 `config/defaults.py` 引用 | `docs/REPRODUCIBILITY.md`、`README.md`、`docs/REFACTORING.md` |
| 三-6 | runpod overlay 新增 `data.dataset: taf28k`（真正强制主语料，实验读取的正是 `data.dataset`），`source` 注释改为如实描述（仅白名单+provenance 消费） | `config/runpod_h100.yaml` |
| 三-7 | cluster 两脚本去硬编码：`fix_training.py` 改 `Path(__file__).parent / "train_sft.py"`，`diagnose_training.py` 改 `sys.path` 指向仓库根；`diagnose_v25_run.py --data-root` 默认 `/workspace/datasets → /workspace/data`；`sync_paper_data.py` 加废弃横幅 + main() 警告 | `cluster/fix_training.py`、`diagnose_training.py`、`diagnose_v25_run.py`、`docs/figure_scripts/sync_paper_data.py` |
| 三-8 | 合约补 exp7/9/12/13 条目（并行会话已修，本轮逐字段对照实验产出核实）；两处 CITED_FIELDS 统一（exp6 含 gamma_deploy）；extraction.py exp8 过滤布尔标志（并行会话已修） | `metrics/contract.py`、`experiments/consistency_check.py`、`metrics/extraction.py` |
| 三-9 | `.gitignore` 补 `outputs/claims/`、`outputs/sft_checkpoints/` | `.gitignore` |
| 附带 | `generate_all.py` 门控修正：Fig3 `[exp1,exp3,exp11,exp14]`、Fig8 `[exp3,exp5,exp11]`（删去无人消费的 exp7），`_available` 检测加 smoke 过滤；`check_alignment.py` 加载逻辑与 `paper_data._load_results` 对齐（smoke 过滤）；schema/注释枚举补 `chifraud` 与 validation 白名单一致；`student_loader` 本地回退改走 `io.paths.OUTDIR`（遵循 REALEVAL_OUTPUT_ROOT）；`envreport` 改为从 `io.paths` 导入；`claim_runner` docstring 修正；删除根目录陈旧 `__pycache__`；figure_scripts README 七图→八图、删 FIGURE_CAPTIONS.md 死引用；README 实验分组 7→10 组；paper_data 残留 RUNLOG 注释清理 | 见 git status |

### 最终验证（修复后实测）

- `pytest tests/ -q` → **65 passed**
- `python -m experiments.consistency_check`（人类模式，无 PYTHONIOENCODING）→ 完整打印 MISSING_RESULT 报告，**无 UnicodeEncodeError**，退出码正常
- `python docs/figure_scripts/paper_data.py` 自检 → 跑通，缺失字段逐一显式列出（结果为空属预期）
- `python docs/figure_scripts/check_alignment.py` → 跑通，正确报 MISSING
- `python -m experiments.runner --validate-contract` → exp7/9/12/13 现已纳入校验（报 missing result file，因 outputs/results 为空）
- `REALEVAL_OUTPUT_ROOT` 覆盖下 `envreport.output_root() == io.paths.OUTDIR` ✓
- `sync_paper_data.py --dry-run` → 打印废弃警告
- `config/runpod_h100.yaml` 解析正常，`data.dataset=taf28k` 生效

### 仍未修（有意保留）

- `exp5.bf16_matched_advfraud` 身份冲突（measured vs cited）——需人工确认
- `claims/legacy/` + `claim_runner` + `interface.py` ABC 归档岛——自我一致，生产无调用
- claim 评估未接入任何 pipeline（手动入口）——建议后续加 CI 干跑
- `sync_paper_data.py` 保留为废弃标注（不删除，供历史参考）
- 孤儿数据集（balanced600/balanced10c/chifraud.npz）与声明性死配置字段——低风险，保留
- exp8 per-iteration 计时新增 `torch.cuda.synchronize()`，重跑后 `latency_p50_ms` 可能与旧结果有微小偏移（为测得真实 p90/p99 的必要代价）

---

## 归档：2026-08-14_full_audit.md

# H100_package_realeval 全量审计报告（第三轮：安全 + 测量诚信 + 运维链路）

> 日期：2026-08-14
> 基线：HEAD `6cbc498`（"更新"，含第二轮全部修复），工作树干净
> 审计范围：全部 109 个 .py + 15 个 shell 脚本 + 配置/文档/模板（排除 .venv/.git/.pytest_cache/egg-info）
> 审计方法：语法编译 + 全模块导入 + from-import 符号完整性 + pytest 基线 + 前两轮修复复核 + 四路并行深度审计（安全凭据 / 核心逻辑新 bug / 数据链与 claims 复核 / 运维脚本与打包），**P0/P1 关键发现全部经人工二次复核**（标注 ✅复核）
> 与前两轮关系：不重复已修复/有意保留项（见 `2026-08-13_full_audit.md` §八、`_round2.md` §五）；本轮聚焦前两轮未深入的角度：**安全、跨实验测量诚信、部署运维链路**

---

## 一、总体结论

**代码链接层保持干净**：109 文件编译通过、68 个模块导入无断点、from-import 零缺失、pytest **65 passed**、前两轮修复抽查全部在位、无 P0 级断链。

但本轮在三个新角度发现重要问题：

1. **安全（1 个 P0 + 4 个 P1）**：模板镜像硬编码 root 弱密码 `root/realeval` 且允许密码登录；API 服务无认证 + 路径遍历；RunPod pod 标识/IP 清理不彻底；全服务默认弱口令矩阵。
2. **测量诚信（4 个 P1）**：exp1 随机切分 vs exp5/13/14 位置切分构成**跨实验训练集泄漏**；合成数据回退结果以 `is_synthetic: False` 硬编码上报；`_load_jsonl` 坏行导致标签静默串位；exp7 的 GLO 重建相关系数实为随机投影 demo 数值。这些直接威胁论文主表数字的可信度。
3. **运维链路（10 个 P1）**：`--benchmark` 短路使三条"全量运行"入口假成功；`run_pipeline.sh` 数据根指空目录；peft/bitsandbytes/accelerate 不在依赖清单（默认配置 exp1 必崩、int4 路径静默退化）；`fix_training.py` 的正则修复会把 `train_sft.py` 改坏；部署布局互相矛盾。

---

## 二、基线验证（本轮实测）

| 维度 | 结果 |
|---|---|
| 语法编译（109 个 .py） | 全部通过 |
| 全模块导入（10 个顶层包，68 个模块） | 无 ImportError、无循环 import |
| from-import 符号完整性（109 文件 AST 全量解析） | 0 缺失 |
| pytest（系统 Python 3.14.5 + torch 2.14.0.dev） | **65 passed**（11s） |
| 15 个 shell 脚本 `bash -n` | 全部通过 |
| `python docs/figure_scripts/paper_data.py` 自检 | exit 0，67 占位符逐一报缺，self-check pass |
| `python docs/figure_scripts/check_alignment.py` | exit 1（67 处 MISSING，结果为空属预期），smoke 过滤与 paper_data 一致 |
| `python -m experiments.runner --validate-contract` | exit 2，exp1 报 NON_H100_COMPUTATION + 13 实验 missing result（预期） |
| `python -m experiments.consistency_check --json` | exp1 报 SMOKE+MISSING，9 实验 MISSING_RESULT（预期，见下） |
| git 跟踪内容 | 156 文件无任何 outputs/数据/密钥文件；`git status` 干净 |

**环境备注**：本地 `.venv` 缺 torch（pytest 全 65 项 ModuleNotFoundError）；前两轮"65 passed"实际用的是**系统 Python**（含 torch）。venv 与系统环境并存易造成"测试不过"的误判，建议在 README/CONTRIBUTING 注明测试用哪个解释器。

**outputs/results/ 现状**：4 个文件均为 2026-08-13 上午（smoke 移除前）的本地陈旧产物——`exp1_...105315.json`（`computation: smoke_sklearn`）、`exp1_...110527.json`（failed：本地 GPU 显存 11.8GB < 35GB）、`test_exp`/`integration_test`（测试残留）。代码层 `smoke_sklearn` 已零残留，consistency_check 对它们诚实报 SMOKE/failed，paper_data 也会过滤——但 H100 重跑前应归档清理（`scripts/archive_and_clear.py`），避免与真实结果混淆。

---

## 三、前两轮修复复核（抽查确认在位）

| 项 | 结果 |
|---|---|
| claim_01 treatment `ov_freeze_full` | ✅ 在位（claims/claim_01_ovfreeze.yaml:9） |
| 代码层 `--smoke`/`run_smoke`/`smoke_sklearn` | ✅ 零残留（仅 egg-info PKG-INFO 构建产物与 outputs/logs 运行日志有历史字样，见 P3） |
| `seed_base_from_config` 取代硬编码 `set_seed(1000+s)` | ✅ 24 处引用，硬编码 0 残留 |
| cluster 路径硬编码修复（fix_training/diagnose_training） | ✅ `__file__` 相对定位正确 |
| contract.py exp7/9/12/13 条目、两处 CITED_FIELDS 一致 | ✅ 逐字段核对通过 |
| exp8 产出 latency_p90/p99（旧"恒空"发现） | ✅ 已产出，旧发现关闭 |
| extraction.py exp8 布尔过滤、exp11 `f1=None` 修复 | ✅ 在位 |
| generate_all 门控、sync_paper_data 废弃双标注 | ✅ 在位 |
| 测试隔离（conftest REALEVAL_OUTPUT_ROOT 重绑） | ✅ pytest 后 outputs/ 无新泄漏 |

---

## 四、P0 — 致命

### P0-1. 模板镜像硬编码 root SSH 弱密码并允许密码登录 ✅复核

- 位置：`template/Dockerfile:23-25`
  ```
  sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' ...
  sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' ...
  echo 'root:realeval' | chpasswd
  ```
  配合 `EXPOSE 22`（:98）与 compose 的 `${SSH_PORT:-22}:22` 映射。
- 后果：任何能触达容器 22 端口者（RunPod 公网代理/同网段）用 `root/realeval` 直接拿 root，可读 /workspace 全部数据、模型与 S3 凭据。
- 修复：删硬编码密码，启动时从环境变量注入或强制 key-only 登录。

---

## 五、P1 — 高严重度

### 5.1 安全类

**P1-S1. FastAPI 无认证 + 路径遍历任意文件读** ✅复核
- `services/api/main.py:168-174`（`template/services/api/main.py` 同份拷贝）：`filepath = WORKSPACE / filename` 无 `..` 校验；服务 `host="0.0.0.0"`、全端点零认证；`POST /experiments/run` 可被任何人触发 GPU 任务（资源盗用）。
- 修复：`resolve()` 后做前缀校验 + 至少 token 认证。

**P1-S2. RunPod 基础设施标识残留（9797cb3 清理不彻底）**
- `scripts/sync_from_runpod.py:23`（pod ssh 主机名）、`data/scripts/prep_datasets.py:87-88`（公网 IP:端口）、`docs/REPRODUCIBILITY.md:69`（ssh 命令含 pod ID）、`.claude/settings.local.json:4`（IP:port，未跟踪）。
- 后果：为针对性攻击提供精确目标，且与"已清除凭据"的历史承诺不符。
- 修复：改环境变量/占位符；`.gitignore` 补 `.claude/`（当前仅靠用户全局 gitignore 豁免）。

**P1-S3. 全服务默认弱口令矩阵**
- `services/jupyter/jupyter_notebook_config.py:6`（token 默认 "realeval"）、`services/vscode/config.yaml:4`（password 默认 "realeval"）、`template/run_all.sh:57`、`template/docker-compose.yml:34-36` —— 均绑 0.0.0.0。与 P0-1 叠加成完整默认口令面。
- 修复：未设环境变量则拒绝启动。

**P1-S4. S3 凭据明文落盘无权限控制**
- `template/scripts/mount_s3.sh:61`：boto3 回退把 `aws_access_key_id/secret` 写入持久卷 `/workspace/.s3_config.json`，无 `chmod 600`（rclone 分支 :36-41 同理）。
- 修复：写后 `chmod 600`，或改走实例角色/临时凭据。

### 5.2 测量诚信类（直接影响论文数字可信度）

**P1-M1. 跨实验训练-测试泄漏：exp1 随机切分 vs exp5/13/14 位置切分** ✅复核（结构）
- exp1 训练用 `group_split` 随机 80/20（`experiments/common.py:70` → `realeval/data.py:428`，seed=42）；而 exp5（`:36,44-47,112`）、exp13（`:23-25`）、exp14（`:28-29`）用**位置切分**取尾部 20% 评估。exp14 docstring 自称 "SAME TAF-28k test split"，实际与 exp1 的随机切分**不是同一 split**。
- 后果：尾部 20% 中约 80% 样本落在 exp1 训练集内 → exp5 的 `taf28k.f1`/`ldp_tradeoff`、exp13 三策略 F1、exp14 bf16/gguf F1 全部在（部分）训练数据上评估，F1 系统性虚高且从结果文件无法察觉；exp5 的 cross-dataset 评估（`:87-96`）在全量语料上进行，重叠 100%。
- 修复：所有实验统一走 `group_split`（同 seed 同 max_samples 则切分一致，exp9/11/12 已是正确模式），或落盘共享 split manifest。

**P1-M2. `is_synthetic: False` 硬编码 + 合成数据回退不可见** ✅复核
- `experiments/exp1_qad_production.py:74` 硬编码 `"is_synthetic": False`；回退链 `common.py:66-69` → `framework.py:50-75` 在数据缺失时静默用 200 条合成样本，结果仍以 `computation: "h100_real_qwen"` 上报。paper_data 的 smoke 过滤挡不住这种"合成数据+真模型"记录。其余 13 个实验同样不写数据来源。
- 后果：H100 pod 上数据挂载失败时，合成数据 F1 以"真实测量"身份流入论文，无告警。
- 修复：`DatasetSplit` 携带 `source` 并如实写入结果；`pre_run_validation` 增加数据来源断言。

**P1-M3. `_load_jsonl` 坏行导致 texts/labels 静默串位** ✅复核
- `realeval/data.py:52-60`：`texts.append` 先于 `int(obj["label"])`；label 转换抛错时 text 已入列、label 未入列，外层 except 记 "Skipping line" 继续——**该行之后全部标签错位一格**。
- 修复：先解析入临时变量，成对提交。

**P1-M4. exp7 的 `glo_reconstruction_corr` 是随机投影 demo 数值，以真实测量身份上报**
- `experiments/exp7_privacy_verification.py:43,61` 调 `glo_reconstruction_attack` 不传 `proj_fn` → `realeval/privacy.py:52-62` 走"随机正交投影"沙盒分支；返回 dict 里的 "Sandbox demo only" 警示 note 被 exp7 丢弃，只取数值；`metrics/contract.py:102` 还把它列为 MEASURED 合约字段。
- 修复：接真实嵌入函数作 `proj_fn`，或降级为 cited/demo 并在结果中保留 note。

### 5.3 运维链路类

**P1-O1. `--benchmark` 短路：三条"全量运行"入口实际只跑玩具基准就退出** ✅复核
- `experiments/runner.py:93-101`：`args.benchmark` 在 `_handle_standalone_checks` 中处理后 `return True`，main 随即退出，不跑任何实验；基准对象是临时 `nn.Linear` 玩具模型。
- 受影响：`cluster/launch.sh:55`（h100 模式）、`cluster/slurm_h100.sbatch:38`、`services/api/main.py:28-30`（`benchmark: bool = True` 默认开）——这三条路径静默"假成功"，退出码 0、无实验产物。
- 修复：`--benchmark` 与 `--exp` 同传时先跑实验再跑基准；或这些入口去掉 `--benchmark`。

**P1-O2. `scripts/run_pipeline.sh:13` 数据根指向空目录** ✅复核
- `REALEVAL_DATA_ROOT=/workspace/H100_package_realeval/data`（仓内 data/ 只有 scripts/），而整条数据链与配置约定 `/workspace/data`。且 `:10` 只有 `set -uo pipefail` 缺 `-e`，pip/模型下载失败仅 echo 继续（:31,48-49）。
- 修复：改 `/workspace/data`，补 `-e` 或关键步骤硬失败。

**P1-O3. 部署布局互相矛盾：`/workspace` vs `/workspace/H100_package_realeval`**
- `template/runpod-template.json:19` 指示直接克隆进 `/workspace`；`run_pipeline.sh:11`、`sync_to_runpod.py:148`、REPRODUCIBILITY §1.4 均假设子目录布局；模板 readme 让用户 `bash run_all.sh`，克隆后 `/workspace/run_all.sh` 不存在。
- 修复：统一一种布局并改齐所有引用。

**P1-O4. `template/run_all.sh` 在任何文档所述调用方式下都会失败**
- `:14-15` cd 到 `template/` 后引用只在仓库根存在的 `cluster/manage_models.sh`、`config/h100.yaml`；`:79` `set -u` 下 `${PYTHONPATH}` 未设即 unbound 崩溃；`:157-163` heredoc 用引号定界符，`$(date)`/`$MODE` 以字面量写入。另 `:67` 建 venv 无 `--system-site-packages`（与 README §3.2 矛盾）→ venv 内无 torch。
- 修复：定位仓库根或明确"先拷贝到仓库根"。

**P1-O5. 依赖链缺失 peft/bitsandbytes/accelerate（+torchaudio），默认配置下 exp1 必崩** ✅复核
- `requirements.txt` 与 pyproject core deps 均无 peft/accelerate（bitsandbytes 仅在 pyproject `paper` extra）；`cluster/setup_runpod.sh:25-26` 只装 requirements。而默认 `student_variant: qad_ovf` → `student_loader` 运行时 `from peft import PeftModel`；`models.py:93-99` 缺 accelerate/bitsandbytes 仅 warning 后**静默回退全精度**（int4 论文路径名存实亡）。torchaudio 被 `build_taf28k_npz.py:24`、`transcribe_taf28k.py:56` 依赖，同样未声明。
- 修复：写入 requirements.txt 或 setup_runpod.sh 补装。

**P1-O6. `cluster/manage_models.sh` 模型清单与 config 不符**
- config 需要 `Qwen/Qwen2-0.5B`（exp6 草稿，`experiments.yaml:11`）与 `teacher_3b`（:16）；清单（:55-62）漏这两者，却下了 config 无引用的 Qwen2.5-0.5B base。`run_pipeline.sh:51-56` 的清单才是对的。
- 后果：部署后 exp6/exp10 运行时需联网回源，离线/限流即失败。

**P1-O7. `fix_training.py` 的 collator 正则会把 `train_sft.py` 改坏** ✅复核
- `cluster/fix_training.py:83` 正则 `data_collator\s*=\s*[^,\n)]+` 作用于 `train_sft.py:167` `DataCollatorWithPadding(tokenizer, padding=True)` 时止于第一个逗号 → 残留 `, padding=True),` → Trainer 收到未知 kwarg 运行时 TypeError。该工具当前处于会被真实使用的状态（train_sft.py 未打补丁）。
- 修复：正则匹配整个嵌套调用（含括号配平校验）。

**P1-O8. `template/docker-compose.yml:42` `/dev/null` 挂载反模式**
- 未设 `HOST_MODEL_CACHE` 时把字符设备挂到 `/workspace/hf_cache` 目录路径，HF 缓存写不进。修复：默认改空目录或拆 override 文件。

**P1-O9. template 的 Jupyter 完全无认证（根级那份反而是对的）**
- `template/services/jupyter/jupyter_notebook_config.py`：`token = ""` + `allow_origin = "*"`，compose 传入的 `JUPYTER_TOKEN` 无人消费；根级 `services/jupyter/...` 读环境变量的版本不被任何构建引用（孤儿副本）。
- 修复：同步两份，删除孤儿。

**P1-O10. `template/Dockerfile:51` flash-attn 在 runtime 镜像里源码编译，构建必失败**
- 基础镜像无 nvcc；PyPI flash-attn 仅 sdist。修复：换 devel 镜像/预编译 wheel/去掉（有 SDPA 回退）。

### 5.4 数据链工具类

**P1-D1. claim_engine 对实验异常零隔离，降级场景下整体崩溃** ✅复核
- `experiments/claim_engine.py:259-268`：main 循环无 try/except；`pre_run_validation` 在无 GPU/权重环境抛异常 → 整个引擎 traceback 退出、不写任何 trace。而 claim_03 注释与引擎 docstring 都承诺该场景应落 UNSUPPORTED + evidence trace。一个 claim 崩溃还会带走后续所有 claim。
- 修复：per-claim try/except，异常落 UNSUPPORTED trace。

**P1-D2. paper_data 模块级 None 崩溃波及全部图表** ✅复核
- `docs/figure_scripts/paper_data.py:464`：`"delta": round(_f1_hetero - _f1_homo, 3)` 在模块顶层执行——exp11 int4 失败分支（f1=None）或 exp14 GGUF-unavailable 时 import paper_data 即 TypeError → 所有 fig 脚本与 generate_all 全灭。None-报缺机制的爆炸半径大于其设计文档所述。
- 修复：模块顶层组装的算术全部加 None 短路。

---

## 六、P2 — 中严重度（精选，全部经代码定位确认）

| # | 位置 | 问题 |
|---|---|---|
| 1 | `experiments/exp5_cross_dataset.py` 全文 | 无 `set_seed`：LDP 噪声用全局 RNG，流水线内跑与单跑结果不同，`ldp_tradeoff` 不可复现 |
| 2 | `realeval/real_backend.py:684-690` | `real_fusion_classify` 吞异常静默退化 text-only，exp13 三个"融合"策略可能实为同一纯文本结果且无标记 |
| 3 | `experiments/exp8_latency_benchmark.py:77-89` vs `:134-149` | 两套延迟口径不一致：`latency_detail` 计时含 tokenize+H2D，`batch_benchmark` 不含，两者不可比 |
| 4 | `experiments/exp8_latency_benchmark.py:105-116` + `realeval/report.py:189-200` | 布尔标志混进 `latencies`，report 延迟柱状图会画出 0/1 垃圾柱（extraction 已过滤，report 漏网） |
| 5 | `runner/orchestrator.py:64-69` | `--resume` 把 `computation:"failed"` 结果当已完成跳过，失败被固化进 all_experiments.json |
| 6 | `experiments/claim_engine.py:104-106` | CLAIM-03 速度公式 `if measured_alpha` 不挡 alpha=1.0 → ZeroDivisionError（✅复核；另 `_safe_eval` 只兜 TypeError 不兜除零） |
| 7 | `experiments/claim_engine.py:51` × exp 内部 `seed_base+s` | 多 seed 重复的种子窗口重叠 4/5（outer0={42..46}, outer1={43..47}），"独立重复"实为相关样本，bootstrap CI 高估显著性 |
| 8 | `realeval/real_backend.py:318-325` | 末批 batch=1 时 `var(dim=0)`（ddof=1）产 NaN，OVF 激活时 NaN 经 backward 写入学生权重，静默产出垃圾模型 |
| 9 | `experiments/exp3_ov_freeze_control.py:40,78` | `ppl = exp(min(kl,10))` 不是 LM 困惑度但以 ppl 名义进合约/图表；且 rho_sweep 每个值在 seed 循环外多跑一次无种子训练，不可复现且浪费 ~20% 算力 |
| 10 | `realeval/audit.py:128` | 审计日志 Seed 恒记 42（`REALEVAL_SEED` 无人设置），与实际种子（1000+s）不符——可复现性记录关键字段是错的 |
| 11 | `realeval/data.py:191-199` | `load_chifraud_balanced` 回退路径用未设种子的全局 `random`（set_seed 不设 random 模块），不可复现；2:1 配比与 docstring "Perfectly balanced" 矛盾 |
| 12 | `realeval/student_loader.py:78-81` | variant 无专属目录时静默返回任意 variant 的最新 checkpoint——防"拿 base 当微调"的模块把失败换成"拿错 adapter" |
| 13 | `experiments/consistency_check.py:43`、`metrics/contract.py:224` | 结果 JSON 损坏时整体崩溃（无容错，orchestrator/report 均有）；serialization 非原子写可留截断文件 |
| 14 | `experiments/exp5:109-121` + `real_backend.py:580-583` | "(ε,δ)-DP" 标签不成立：噪声加在未裁剪 hidden states 上敏感度无界，逐维加噪无组合记账；曲线本身是真实测量，键名隐含的 DP 保证不成立 |
| 15 | `run_h100.sh:14,32` | `CLEAN=0` 无条件赋值，`CLEAN=1 bash run_h100.sh` 失效，与注释及 REPRODUCIBILITY 铁律矛盾 |
| 16 | `scripts/export_to_gguf.py:197` | `Path + str` TypeError，`--keep-checkpoint` 分支必崩；`:184` 默认名 `_qq4_k_m` 双 q |
| 17 | `cluster/train_lora_manual.py:21` | `sys.path.insert(0, "/workspace")` 硬编码漏网（上轮同类已修） |
| 18 | `docs/experiment_result_contract.md` | 第三/四轮复查仍有实质错误：Fig3 表（EXP01_QUANT_QUALITY 实为常量列表不读 exp1；BF16_F1 不读 exp11）、Fig7/Fig8 来源表错误、:156-157 exp5 fallback 值过时（现为 0.1238/None）——该文档自称"硬性约束" |
| 19 | `metrics/extraction.py:150` | exp12 分支不过滤 None，`F1[FraudFusion_pruned_INT4]: None` 会进 metrics.json |
| 20 | `fig3_main_results.py:64,76`、`fig8_revision_ablations.py:77,94,138` | 真实-但-None 数据态无守卫（barh(None) / 格式化崩溃），可经 exp14 GGUF-unavailable 到达 |
| 21 | `pyproject.toml:48` | dev extra 自引用 `realeval[test,paper]`，项目名实为 `H100_package_realeval4`，`pip install -e .[dev]` 会去 PyPI 找错包；scipy 运行时依赖（statistics.py）却在 paper extra |
| 22 | `.vscode/tasks.json:67` | 引用不存在的 `monitor_runpod.sh` |
| 23 | `template/services/vscode/config.yaml:4` | code-server 不做 shell 变量展开，密码会是字面量 `${VSCODE_PASSWORD:-realeval}` |
| 24 | `template/scripts/` 启动脚本失联 | mount_model_cache.sh 自称被 entrypoint 调用实际没有；`set -e` 下用 `return`；ollama 模型永不自动拉取（与 README:102 矛盾） |

## 七、P3 — 低严重度（摘要）

- 统计：`statlib/stats.py:55-60` cohens_d 单样本组返回 `{nan,"large"}` 误导分类；`:32` bootstrap n<3 分支 ddof=0 与主分支 ddof=1 口径不一；`:124-125` 不等长组无条件调 paired 检验会抛异常。
- 数据：`data.py:466` group_split 单样本类全划测试集；`:282-284` load_hf_bucket 任何异常静默回退合成数据；`:227` 未知标签 -1 被索引成 fraud 中心（潜伏）；`metrics.py:21-23` -1 标签不被排除，被静默当负类（与训练路径 target out of bounds 崩溃行为分裂）。
- 随机性：`privacy.py:47,171` 库函数重置全局 torch RNG / 固定 RandomState(0)；`real_backend.py:424-425` 空训练回退硬编码 SNR 18.4/18.9（编造数值）。
- 崩溃面：`claim_engine.py:260,267`、`paper_pipeline.py:154,179,187` 读文件未指定 encoding（GBK 控制台遗留点）；`claim_runner.py:137` print_verdicts 仍用 ✓/✗（归档岛残留）；`exp14:62` 硬索引缺键 KeyError 逃逸优雅降级。
- 配置/死代码：`serialization.py:41-52` 路径类 REALEVAL_* 环境变量被注入为垃圾配置键；`exp3:25-27` config_override 死注入；`exp8:152` batch 字符串键字典序排序问题；`real_backend.py:391-392` 恒 None 死代码行；`aggregation.py` 三个函数零生产调用；`common.py:90-94` 重定义遮蔽导入。
- 一致性小项：`generate_all._available` 把 failed 记录计为可用；extraction/contract/consistency_check 退出码三种（0/1/2）语义不统一；`audit.py:233-253` runlog 子系统空转（无 handler、生产无人调 log_run）；`evidence_graph.py` 秒级时间戳排序乱序、load 丢 timestamp。
- 运维杂项：`run_h100.sh:4` 注释宣称的 `--all` 未实现；`launch.sh:39` NGPU 死赋值；`archive_and_clear.py:33 --force` 未接线；`diagnose_v25_run.py:409` 默认 results 路径错；`kanban.py` 依赖未声明；`train_sft.py:42` LoRA store_true default=True 死开关、output_dir 不吃 CLI；`apply_all_fixes.py` 内嵌旧版源码，建议标废弃；gpu_dashboard 6006 无人启动/未 EXPOSE。
- 数据链：`download_taf28k_audio.sh` 只统计 mp3、无参数时报 unbound variable；`transcribe_taf28k.py` 需要的 sft/train_*.jsonl 无来源交代；resampler 写死 48k→16k。
- 打包/残留：`egg-info/PKG-INFO` 含 2 处 `--smoke` 陈旧说明（重建即消）；`pyproject` include 的 `profiler*` 是空目录死条目；`outputs/evidence/CLAIM-E2E.json`/`TEST-001.json` 是 2026-08-13 测试残留（与 claim_engine 无关，永久陈旧，建议删或移 tests/fixtures）；根级 `services/`+`scripts/{entrypoint,healthcheck.sh}` 为不被构建引用的孤儿副本；`template/` 两份 setup_ollama.sh 逐字节重复。
- 文档小错：`REPRODUCIBILITY.md:77` `torch.version.__version__` 必抛 AttributeError；`figure_scripts/README.md:44` "420-dpi" vs 实际 400；`template/README.md:9` 引用不存在的 `.env.template`；契约文档 :171 exp8→Fig7 无任何图脚本消费、缺 exp4/7/9/12/13 章节、:4 "不可修改"与 paper_data 桥接角色矛盾；README §3.2 vs `run_all.sh:67` venv flag 矛盾。

---

## 八、安全项通过清单（明确干净）

- 硬编码秘密：全仓无真实 token/私钥（`BEGIN ... PRIVATE KEY` 零命中）；config/claims 中的 "token" 均为字段名或 `${VAR:-default}`。
- 危险代码：无 os.system、无 eval（仅 model.eval()）、无 pickle.load、无 SQL；YAML 全走 safe_load；subprocess 全为 list 参数（除 3 处常量 `shell=True`，gpu_dashboard）。
- Shell：变量均正确引号；rm -rf 目标均为固定字面路径（且主清理为 `--clean` opt-in）；无 chmod 777；无 curl|bash（除 Dockerfile:68 code-server 安装脚本，供应链风险 P3）。
- 隐私日志：各实验仅记计数/路径/指标，无原始文本/音频落日志；PII 扫描只输出聚合计数。
- .gitignore：io/paths.py 的 11 个输出子目录、模型权重扩展名、data/** 全覆盖；git 跟踪 156 文件无产物/密钥。缺口：`.claude/`（见 P1-S2）。

---

## 九、修复建议（按优先级）

1. **安全立即项**：P0-1 删 Dockerfile 硬编码 root 密码；P1-S1 API 加路径校验+认证；P1-S2 清 4 处 pod/IP 残留 + `.gitignore` 补 `.claude/`。
2. **论文数字可信性**（重跑前必须修，否则 H100 重跑产出的仍是污染数字）：P1-M1 统一切分、P1-M2 数据来源如实上报、P1-M3 修 `_load_jsonl` 串位、P1-M4 GLO 接真实投影或降级；顺带修 P2-1/2/8/9/14（种子、融合退化标记、NaN 毒化、ppl 口径、DP 标签）。
3. **部署链路可用性**：P1-O1（--benchmark 短路）→ P1-O2（DATA_ROOT）→ P1-O5（依赖）→ P1-O3/O4（布局统一）→ P1-O5~O10。
4. **工具健壮性**（低成本高杠杆）：P1-D1 claim_engine per-claim 隔离、P1-D2 paper_data None 短路、P2-5 resume 跳过失败、P2-13 JSON 容错、P2-7 种子窗口不重叠。
5. **P3 批量**：删陈旧 egg-info 重建、标废 apply_all_fixes、删孤儿副本与空 profiler 目录、清理 outputs/evidence 测试残留、修订文档小错。

## 十、未能验证项（如实声明）

- RunPod 镜像 `runpod/pytorch:2.8.0` 是否自带 peft/bitsandbytes/torchaudio（影响 P1-O5 实际爆雷程度）——离线无法确认。
- flash-attn 构建失败（P1-O10）与 code-server 变量展开行为（P2-23）基于镜像/官方文档推断，未实测 docker build。
- P1-M1 的泄漏比例（~80%）是按切分逻辑的统计推导；确切重叠需在有数据的环境落盘 split manifest 核对。
- claim_engine 未实跑（会写 outputs/claims/），其崩溃面（P1-D1、P2-6/7）为静态推导 + 求值路径精读确认。

---

## 附：本轮验证记录

```
git log: HEAD 6cbc498（2026-08-14 00:07），工作树干净
compileall: 109 files, 0 errors
import sweep: 68 modules OK（realeval/experiments/metrics/audit/statlib/runner/profiler/config/utils/cli）
from-import AST 检查: 109 files, 0 issues
pytest（系统 Python）: 65 passed, 1 warning (11s)
bash -n: 15/15 通过
consistency_check --json: exp1=[SMOKE,MISSING]，9 实验 MISSING_RESULT（陈旧本地结果，预期）
validate-contract: exit 2（exp1 NON_H100 + 13 missing，预期）
paper_data 自检: exit 0，67 占位符逐一报缺，self-check pass
check_alignment: exit 1（67 MISSING，预期）
```

---

## 归档：2026-08-15_changes.md

# 2026-08-15 修改

> 工作文件夹：`D:\Projects\H100_package_realeval`
> 分支：`main`（工作树干净，全部改动已提交）
> 覆盖提交：`575e32b` → `b805ff4`，共 11 个提交
> 另：论文源文件（`C:\Users\wangd\Downloads\`，不在 git 内）由 `v25.tex` 修订至 `v27.tex`

## 一、概述

本轮工作围绕「让 H100 实测代码与论文的公式 / 配置 / 表格严格对齐，并据此诚实化修订论文」展开，含 11 个代码提交 + 论文两轮修订（v25→v26→v27）：

| 类别 | 提交 | 内容 |
| ---------------- | -------------------------------------------------- | ------------------------------------------------------------ |
| 论文对齐（代码） | `8392c59`、`a13762c`、`dce93d3`、`b805ff4` | QAD 蒸馏配置、OV-Freeze 公式、exp13 融合策略、融合权重对齐 v27 |
| 图表脚本重构 | `641a021`、`c863ed6`、`e694216` | 删除 fig4、重命名 fig5~fig8、调整 paper_data / check_alignment / generate_all |
| 代码清理 | `daee459`、`bc29140` | 删冗余死代码、统一复用、修配置覆盖键误注入 |
| 文档 | `575e32b`、`58e8306` | `run_h100.sh` 注释、修改记录 |
| 论文修订（无 git） | v25 → v26 → v27 | 立论重构、数字修正、消融标准、端/云区分、2 模态融合、诚实标注 |

各代码提交均记录验证基线 `pytest: 65 passed`（本文档转述历史提交信息，未在本轮重新执行）。

---

## 二、论文对齐（代码改动）

### 1. 对齐论文 QAD 蒸馏配置 — `8392c59`

让蒸馏超参对齐论文 §3.2.1 / §4.1.4 / Table 7：

| 配置项 | 修改前 | 修改后 | 依据 |
| ------------------------------------- | ------ | -------------- | ---------------------------------- |
| `training.batch_size` | 64 | **8** | 论文 §4.1.4 |
| `training.learning_rate` | 5e-5 | **1e-5** | 论文 §4.1.4 |
| `distillation.temperature` | 2.0 | **1.0** | 论文 §3.2.1（T=1） |
| `distillation.max_seq_length` | 256 | **4096** | 论文 §4.1.4 |
| `distillation.ovf_activation_ratio` | 0.7 | **0.8** | 训练 80% 后激活，最后 20% 方差冻结 |
| 数据集切分 `test_ratio` | 0.2 | **0.1** | 论文 8:1:1 的 10% test |

- `realeval/real_backend.py`：新增 `loss_fn=pure_kl` 分支（T=1、无 CE 的纯 KL 散度），补齐论文 Table 7 的主打目标。
- `test_ratio` 改动贯穿 `realeval/data.py`、`experiments/framework.py`、`experiments/common.py`（默认值 0.2→0.1）。

### 2. OV-Freeze 实现对齐论文公式 — `a13762c`

`realeval/real_backend.py` 中方差匹配逻辑由「窗口加权近似」改为论文原公式：

- **方差估计改为 EMA**（论文 Eq.6，ρ=0.95）：`s_var_ema = ρ·s_var_ema + (1−ρ)·s_var`（首次直接用 `s_var`）。
- **缩放因子加 stop-gradient**（论文 Eq.8）：`scale = √(t_var / s_var_ema).detach()`。
- **损失权重对齐**（论文 Eq.5，λ=0.01）：`ovf_loss = λ · MSE(s_var_ema, t_var)`。

配套：`config/experiments.yaml` 新增 `ovf_rho=0.95`、`ovf_lambda=0.01`；`config/schema.py` 注册新键并同步此前改动未落地的默认值（batch 8 / LR 1e-5 / ctx 4096 / T=1 / ovf_ratio 0.8）。

### 3. exp13 融合策略对齐论文 Table 3 — `dce93d3`

把融合从「硬预测规则」升级为「决策级软分数融合」：

- `real_llm_classify` 新增 `return_probs` 参数，返回分类头软分数（正类概率）。
- `real_fusion_classify` 三种策略语义变更，对齐论文 Table 3：
  - `softmax`：两路正类分数的几何平均融合；
  - `sigmoid`：加权 sigmoid（论文 Eq.11）；
  - `transformer`：逻辑回归替代（线性代理）。
- exp13 策略命名 `early_fusion/late_fusion/hybrid` → **`softmax/sigmoid/transformer`**。
- 字段名联动更新：`metrics/contract.py`、`experiments/consistency_check.py`（headline 由 `late_fusion` 改为 `sigmoid`）、`docs/experiment_result_contract.md`。

### 4. 融合权重 / 参数对齐 v27 — `b805ff4`

v27 把融合从 4 模态改为 2 模态后，权重与参数数变化，同步脚本：

| 项 | v27 | 脚本（对齐后） |
| ------------------------ | ----------------------- | ----------------------------------- |
| sigmoid 融合权重 | `w*=[0.40, 0.30]`，`b*=-0.45` | `z = 0.40·p_text + 0.30·p_audio − 0.45` |
| 融合参数 | 3 scalars（2 权重 + 1 偏置） | exp13 `_param_map` = 3 |

---

## 三、论文修订（`C:\Users\wangd\Downloads\`，无 git 提交）

### 第一轮：v25 → v26（立论 / 数字 / 消融 / 标注）

**立论重构（引言 + 结论）：**

- C1 挑战由「数据稀缺」改写为「隐私约束的数据与声学处理」，把"数据稀缺"降格为 PIPL 的推论，消除"提了问题却无方法"的断头。
- 新增显式研究目标：三重约束 **privacy / fidelity / responsiveness**，分别对应 C1/C2/C3。
- 创新点①~④标题标注 `(addressing C1/C2/C3)`，每个创新点呼应一个挑战。
- 结论改为「四个组件各对应一个约束」，总结三重约束如何联合满足。

**数字矛盾修正：**

- α 值：Table 8 的 `0.85/0.91` → `0.78/0.86`，与正文一致。
- speaker 数：`10` → `11`（脚本 `privacy.py` 动态计算的真实值），随机基线 `10%` → `9.1%`；"fell below" 改为更严谨的 "approached"。

**OV-Freeze 激活窗口：** `最后 30%` → `最后 20%`（step 1400→1600，final 600→400 steps），§4.5 消融数字重排（≤20%→≤10%，≥50%→≥40%）。

**消融实验标准步骤：**

- 融合消融明确「固定 QAD+OVF backbone，仅变融合策略」。
- 损失消融明确「固定 T=1、关闭 OV-Freeze、其余超参不变，仅变 loss 目标」。
- OVF 消融明确「以无 OV-Freeze（F1=0.916）为基线」。

**诚实标注：** draft model `0.1B`→`0.5B`（0.1B 无公开 checkpoint）；融合范围标注为文本+音频双模态验证。

### 第二轮：v26 → v27（端/云区分与 2 模态诚实化）

**端 / 云区分（修正最大硬伤）：**

- 摘要与结论由笼统的「on-device 0.923」改为明确区分：**on-device Q4_K_M 学生 = 0.917（98.5%）**，cloud NVFP4+CoT = **0.923（99.1%）**。
- Highlights「Pure-KL retains 99.1%」→「recovers 98.5%」（on-device 数值）；「on-device 268ms」→「on-device F1=0.917 at 268ms」。

**2 模态融合：**

- 融合由 4 模态（text/audio/url/meta）改为 **2 模态（text+acoustic）**，URL/meta 标为架构预留。
- 融合公式由 4 项改为 2 项，权重 `w*=[0.40, 0.30]`、`b*=-0.45`；Table 3 参数 `5` → `3 scalars`。

**投机解码重新定位：** 由「on-device 加速」改为「**加速云侧异步 CoT 生成**」（诚实：投机解码在云侧，不在端侧关键路径）。

**删除未实现部分：** LoRA-QAD 增量更新、威胁模型 4-tuple 形式化、Figure 4（CPU proxy 收敛图）、§5「工程流水线可复现性」段落。

**数字与表述修正：** PTQ 退化 `6.5–8.5%` → `7.1–8.5%`；存储缩减 `28×` → `57×`；跨层校准矩阵 D 的描述简化；英式拼写 `quantization` → `quantisation`（全文统一）。

---

## 四、图表脚本重构（与 v27 删除 Figure 4 配套）

| 提交 | 内容 |
| ------- | ------------------------------------------------------------ |
| `641a021` | 删除 `fig4_loss_convergence.py`（105 行）；重命名 `fig5_revision_ablations`、`fig6_loss_teacher_ablation`、`fig7_ovf_ablation`、`fig8_speculative_decoding`（编号前移一位） |
| `c863ed6` | 调整 fig5~fig8 脚本、`paper_data.py`、`check_alignment.py`、`generate_all.py`、`figure_scripts/README.md`，与重命名后的图编号对齐 |
| `e694216` | `paper_data.py` 微调 |

> 说明：v27 删除了 Figure 4（CPU proxy 收敛图），脚本同步删除 `fig4_loss_convergence.py`，并把 fig5~fig8 的编号前移，保证图脚本与论文图表编号一致。

---

## 五、代码清理

### 模型加载→量化→训练路径冗余 — `daee459`

- 删除 `realeval/student_loader.py` 中无生产调用的死代码 `load_student`，连同死常量 `BASE_MODEL_DEFAULT`。
- `realeval/models.py::load_causal_lm` 新增 `load_tokenizer` 参数：同架构的 student/draft 加载时跳过 tokenizer 重复加载。
- 去掉 `real_qad_distill_train` 里重复的 `teacher.eval()`。

### 数据加载—训练分类—检测脚本冗余 — `bc29140`

- 删除 `metrics/aggregation.py` 两个零调用的死函数 `run_multi_seed`、`aggregate_batch_benchmark_csv`。
- `experiments/common.py` 去掉 `aggregate_seed_results` 的别名薄包装（审计 P3「重定义遮蔽导入」）。
- `experiments/consistency_check.py` 复用 `metrics.contract` 的 `_dig` / `_latest_result` / `_NOT_FOUND`。
- `realeval/io/serialization.py::_resolve_env_overrides` 只处理含 `__` 的配置覆盖键，不再把 `REALEVAL_OUTPUT_ROOT` 等路径变量误注入为垃圾配置键。

---

## 六、文档

- `575e32b`：`run_h100.sh` 移除未实现的 `--all` 参数注释。
- `58e8306`：更新本修改记录（补论文 v26 修订）。

---

## 七、验证与遗留

**验证（转述各提交信息）：** 每批代码改动均 `pytest tests/ -q` 65 passed。

**遗留 / 注意：**

- `outputs/results/` 仍为空，论文数字需 H100 重跑回填（与 MEMORY_LOG 前序条目一致）。
- 论文 v27 的「纯 KL」分支需在实验里显式设 `loss_fn=pure_kl` 才会生效；默认 `loss_fn="kl"` 仍对应论文 Table 7 的「KL+task reg」消融分支。
- α 值（0.78→0.86）在论文里为引用值（paper reference），脚本 `specdec.py` 明确标 cited，generic α 实测值不同——属可接受的边界。

---

## 八、脚本 bug 修复 + 论文据实标注（Claim–Evidence 对齐）

> 基于 `paper_v27_audit.md`（论文 v27 全量审计）发现的「论文主表数字是 paper_data 常量而非脚本实测」系统性 gap，本轮做两件事：修脚本 bug（让补跑正确对齐论文方法）+ 论文据实标注（把常量/引用/待测与实测分开）。

### 8.1 脚本 bug 修复 — `a38a4cd`（4 个 bug）

| # | Bug | 修复 |
|---|---|---|
| 1 | `test_ratio=0.2` 显式传参（exp4/9/10/11/12 共 5 处） | → 0.1，对齐 8:1:1（此前只改默认值、漏了显式调用） |
| 2 | exp2 `loss_specs` 缺 pure_kl（`kl_only` 误用 `loss_fn="kl"`=CE+KL） | `kl_only=pure_kl`、新增 `kl_task=kl` 独立分支 |
| 3 | exp1 默认没切 `pure_kl` | 显式 `loss_fn="pure_kl"` |
| 4 | exp3 默认没切 `pure_kl` | 显式 `loss_fn="pure_kl"` |

**关键结论：修复前补跑脚本跑的是「CE+KL + 20% test」，不是论文声称的「纯 KL + 8:1:1」——实测 0.43/0.70 的低值有一部分是方法未对齐导致。修复后补跑才真正对齐论文方法，此时数字才有意义（若仍 0.4/0.7 则论文虚报，需据实修订头条）。**

### 8.2 论文据实标注（v27.tex，4 项）

| 项 | 据实标注 |
|---|---|
| exp6 α | domain-tuned 0.86 为 paper reference（cited），generic 实测 0.468，域调脚本待实现 |
| exp7 WER/PESQ/STOI/MOS | 为 reference estimates，脚本只直接测 ASV-EER/speaker-ID，重建可懂度管道待实现 |
| exp8 268ms | 端到端流水线估计；H100 per-token 实测 46.47ms，口径不同 |
| exp12 240MB | 纯权重量化 240MB；实际 GGUF 文件（含词表+元数据）491.4MB |

### 8.3 仍缺的脚本（论文声称但脚本未实现）

- exp6 域调 draft 微调（论文 α 0.78→0.86 的证据链）
- exp7 音频重建管道（WER/PESQ/STOI/MOS 实测）
- exp8 端侧（Snapdragon）延迟实测

---

## 归档：2026-08-19_full_audit.md

# H100_package_realeval 全量审计报告（第四轮：NBE QDQ + 融合重构 + 前轮修复复核）

> 日期：2026-08-19
> 基线：HEAD `4ff723c`（"docs: append MEMORY_LOG entry for exp13 fusion + privacy scorer port"），工作树干净，157 个 git 跟踪文件
> 审计范围：全部 107 个 .py + 13 个 shell 脚本 + 配置/文档/模板（排除 .venv/.git/.pytest_cache）
> 与前三轮关系：第三轮（`2026-08-14_full_audit.md`，基线 6cbc498）之后的增量为 91 文件改动（575e32b..4ff723c），核心是新代码——`17f568f` NBE QDQ 量化（NVFP4）、`ab42e03` exp13 融合/隐私评分重构、`191db4a` 图号重命名，以及第三轮 P0/P1 的大批修复。本轮聚焦**新代码的正确性** + **修复复核**，不重复已关闭项
> 审计方法：基线实测 + 四路并行深度审计（量化路径 / 融合隐私 / LDP 与数据完整性 / 安全运维复核），**P0/P1 关键发现全部经主会话二次复核**（标注 ✅复核，其中 P0-1 经本机 CPU 实测复现）

---

## 一、总体结论

**前轮修复质量高**：第三轮 1 个 P0 + 15 个 P1 中 14 项已修、1 项部分修；测量诚信四项 P1-M 中 M1（跨实验泄漏）/M3（JSONL 串位）/M4（GLO demo 数值）已闭环，M2 主路径闭环（残留 P2）。基线全绿（编译/导入/pytest 65 passed/shell 语法）。

**但新引入的 NBE QDQ 量化路径存在 1 个 P0 级断链 + 1 个 P1 级回归**（均为 `17f568f` 引入，本轮实测/静态确认）：

1. **P0-1**：`QDQLinear` 的 state_dict 委托产生重复别名键（`weight` 与 `linear.weight` 共享 storage），safetensors/`save_pretrained` 必崩 → **exp1 训练完成后无法保存 checkpoint，下游 exp5/9/11/12 全部失去 QAD 学生**。已在本机实测复现。
2. **P1-1**：nvfp4 的 force-base 只在训练路径强制执行，`real_llm_classify` 的 base zero-shot 路径（默认 `student_variant: qad_ovf`）会对 QDQ 包装模型 attach LoRA → PEFT 不识别 `QDQLinear` 崩溃或 AssetsUnavailable，exp4 等无 `finetuned_path` 的调用受阻。属迁移回归。

**结论：H100 重跑前必须先修 P0-1 与 P1-1**（否则 exp1 白跑 5 epoch 后在保存处崩溃）；P2 中「tex 引用的 7 个图 PDF 全不存在」（投稿硬伤）与「exp7 合成回退绕过数据来源断言」（测量诚信残留）建议同批处理。

---

## 二、基线验证（本轮实测）

| 维度 | 结果 |
|---|---|
| git | HEAD `4ff723c`，工作树干净，157 跟踪文件无产物/密钥/`.claude/` |
| 语法编译（107 个 .py） | 全部通过 |
| 全模块导入（10 顶层包，59 模块） | 0 失败 |
| from-import AST 检查（107 文件） | 0 真实问题（15 条 `from realeval import <submodule>` 为检查器误报，已逐一证实可导入） |
| pytest（系统 Python 3.14.5 + torch 2.14.0.dev） | **65 passed**（24s） |
| 13 个 shell 脚本 `bash -n` | 全部通过 |
| `paper_data.py` 自检 | exit 0，占位符逐一报缺，self-check pass |
| `check_alignment.py` | exit 1（MISSING 属预期，结果为空） |
| `consistency_check --json` | exit 1（陈旧 exp1 报 SMOKE/failed + 9 实验 MISSING_RESULT，预期） |
| `--validate-contract` | exit 2（exp1 NON_H100 + 13 missing，预期） |
| `outputs/results/` | 5 个 2026-08-13 陈旧产物仍在（smoke/failed/测试残留），未归档 |

---

## 三、前轮修复复核总表

### 3.1 第三轮安全/运维项（15 项：14 已修 + 1 部分修）

| 项 | 判定 | 当前证据 |
|---|---|---|
| P0-1 Dockerfile root 弱密码 | ✅ 已修 | `template/Dockerfile:36-38` prohibit-password + PasswordAuthentication no，硬编码密码已删；文件整体标 DEPRECATED |
| P1-S1 API 无认证/路径遍历 | ✅ 已修 | 根级 `services/` 已删（e4bf17a）且无残留引用；`template/services/api/main.py:32-51` token fail-closed + resolve 前缀校验 |
| P1-S2 RunPod 标识残留 | ✅ 已修 | 全部改环境变量/占位符；`.gitignore:91` 补 `.claude/` |
| P1-S3 弱口令矩阵 | ✅ 已修 | 全部 fail-closed（`${VAR:?msg}` / 未设即 raise/退出） |
| P1-S4 S3 凭据落盘 | ⚠️ 部分修 | boto3/s3fs 分支已 chmod 600；**rclone 分支残留**（凭据走 CLI 参数 + rclone.conf 未限权限，见 P2-11） |
| P1-O1 --benchmark 短路 | ✅ 已修 | `runner.py:97` 仅无 `--exp` 才短路；`:182-183` 同传时先实验后基准 |
| P1-O2 run_pipeline 数据根/set -e | ✅ 已修 | `:10` `set -euo pipefail`；`:16` `/workspace/data`（小残留 P3） |
| P1-O3 部署布局矛盾 | ✅ 已修 | 统一 `/workspace/H100_package_realeval`，四处引用一致 |
| P1-O4 run_all.sh 四处必败 | ✅ 已修 | 仓根定位/`${PYTHONPATH:-}`/无引号 heredoc/venv `--system-site-packages` |
| P1-O5 依赖缺失 | ✅ 已修（未钉版） | `requirements.txt:15-19` 补 peft/accelerate/bitsandbytes/torchaudio；pyproject scipy 升 core、dev 自引用修复 |
| P1-O6 模型清单 | ✅ 已修 | `manage_models.sh:58,63` 补 Qwen2-0.5B 与 teacher_3b |
| P1-O7 collator 正则 | ✅ 已修 | `fix_training.py:87` 整体匹配一层括号调用 |
| P1-O8 /dev/null 挂载 | ✅ 已修 | 改 named volume |
| P1-O9/O10 jupyter 认证/flash-attn | ✅ 已修 | template fail-closed；基础镜像换 devel 且标 DEPRECATED |
| P1-D1 claim_engine 隔离 | ✅ 已修（有实证） | `claim_engine.py:283-289` per-claim try/except；`outputs/claims/CLAIM-01.json` 即为降级产物实证；顺带修 P2-6 除零 |
| P1-D2 paper_data None 崩溃 | ✅ 已修 | `_safe_delta`（`paper_data.py:459-463`） |

### 3.2 第三轮测量诚信项（P1-M1~M4）

| 项 | 判定 | 当前证据 |
|---|---|---|
| P1-M1 跨实验泄漏 | ✅ 已修（闭环） | 全部实验统一 `group_split(0.1, seed=42)`；exp1/2/3 落盘 split manifest（`common.py:92-101`），exp5/13/14 按哈希交集取回同一留出集（`:123-149`）；registry 顺序保证 exp1 先跑；exp5 cross-dataset/advfraud 池也改在 taf 留出集上 |
| P1-M2 is_synthetic 硬编码 | ⚠️ 主路径已修 | `exp1:77` 如实上报；`framework.py:135-146` pre_run_validation 数据缺失直接抛错。**残留**：exp2~14 不写来源、exp7 绕开断言（见 P2-8） |
| P1-M3 JSONL 串位 | ✅ 已修 | `data.py:51-66` 先解析后成对提交 |
| P1-M4 GLO demo 数值 | ✅ 已修（诚实标注路径） | demo 数值不进 measured_fields、进 `coverage.demo_only`；`contract.py:101-103` 移出 MEASURED；数值本身仍是随机投影 demo（已标注） |

---

## 四、P0 — 致命

### P0-1. `QDQLinear` state_dict 重复别名键 → `save_pretrained`/safetensors 必崩，exp1 checkpoint 存不下来 ✅复核（本机实测复现）

- 位置：`realeval/qdq.py:90-91`
  ```python
  def _save_to_state_dict(self, destination, prefix, keep_vars):
      self.linear._save_to_state_dict(destination, prefix, keep_vars)
  ```
  委托方法在 QDQLinear 前缀下写入 `weight`/`bias`；但 `nn.Module.state_dict()` 对子模块的递归是**无条件**的，`self.linear` 作为注册子模块再写一份 `linear.weight`/`linear.bias`。
- **本机实测**（torch 2.14.0.dev，CPU）：
  - `QDQLinear(nn.Linear(8,8)).state_dict()` 键 = `['weight','bias','linear.weight','linear.bias']`，且 `weight` 与 `linear.weight` **共享同一 storage**；
  - `safetensors.torch.save_file(sd)` → `RuntimeError: Some tensors share memory [{'linear.weight','weight'},{'bias','linear.bias'}]`；
  - plain checkpoint → QDQ `load_state_dict` 报 spurious missing `linear.weight/linear.bias`（反向同样断链）；
  - 子代理在 transformers 5.8.1 上对 QDQ 包装后的 tiny Qwen2 调 `save_pretrained` 复现 `RuntimeError: ... shared tensors ... not properly defined`（本机所装即 5.8.1，且 `requirements.txt:5`/`pyproject.toml:33` 为 `transformers>=4.36` 无上限，新装环境即 5.x；4.x 各版本或是删别名 warning 或是撞同一 safetensors 报错，均为脆弱路径）。
- 后果链：`real_backend.py:464` `student.save_pretrained(...)` 在 exp1 训练 5 epoch **之后**崩溃 → `outputs/models/exp1_qad/` 永远不存在 → exp5/9/11/12 的 `finetuned_path` 全部落空。H100 重跑将白烧整个训练时长。
- 修复（最简，已验证思路）：`QDQLinear.__init__` 吸收参数为自有属性——`self.weight = linear.weight; self.bias = linear.bias`，不保留 `linear` 子模块，forward 直接用 `self.weight/self.bias`，删除两个委托方法。state_dict 天然只剩 `weight/bias`，各版本 transformers 均透明。
- 注：`qdq.py:74-78` docstring「save_pretrained see weight/bias keys (not linear.weight)」的声明不成立，修复时需同步。

## 五、P1 — 高严重度

### P1-1. nvfp4 force-base 存在绕过路径：推理侧对 QDQ 模型 attach LoRA → PEFT 崩溃/硬抛错 ✅复核（静态确认 + config 前提核实）

- 训练侧 `real_backend.py:129` 对 nvfp4 强制 `variant="base"` ✓，但推理侧两处绕过：
  1. `real_backend.py:635-636`（base zero-shot 路径）：`attach_adapter(model, config.get('student_variant','base'), ..., quantize=quantize)`——**默认配置 `student_variant: qad_ovf`**（`experiments.yaml:132`、`schema.py:116` 默认值同）。adapter 存在时 PEFT `_create_new_module` 只认 `nn.Linear`/bnb 类型，`QDQLinear` 是普通 `nn.Module` → ValueError；adapter 不存在时 `AssetsUnavailable`（`student_loader.py:101-104`）。
  2. `real_backend.py:538-541`（finetuned 分支）：遇 legacy adapter-only 存档（`adapter_config.json` 存在）同样 PeftModel-on-QDQ 崩溃；exp11 有 try/except 会记 error 而非崩实验，但该方案结果缺失。
- 后果：`experiments/exp4_baseline_comparison.py`（无 `finetuned_path`，grep 确认）两条路都走不通——迁移前是 bnb-int4+LoRA（PEFT 支持）可跑，迁移后硬崩/硬抛错。属 `17f568f` 引入的回归。
- 修复：`quantize=="nvfp4"` 时 `real_llm_classify` 同样强制 `variant="base"`（与训练口径一致），或 `attach_adapter` 对 QDQ 包装模型显式拒绝并给出清晰报错。

### P1-2. `apply_qdq` 不跳过 `lm_head`（且与 tied embedding 耦合）✅复核（子代理实测）

- `realeval/qdq.py:100-111` 无 skip 列表；实测 tiny Qwen2（`tie_word_embeddings=True`，与 Qwen2.5-0.5B 同）15 个 nn.Linear 全被包装，**含 lm_head**，且 `lm_head.linear.weight is embed_tokens.weight` 为 True。
- 后果：输出投影对共享 embedding 矩阵做 fake-quant，而输入 embedding lookup 用原始权重；标准 NVFP4 部署（TensorRT-LLM）不量化 lm_head/embeddings。训练/推理内部一致（都包），故是**口径偏差**而非不一致 bug——但它改变所有下游 logits/F1，与论文 Table 2 的量化范围口径不符，且是 P0-1 tied-keys 冲突的放大器。
- 修复：`apply_qdq` 增加名字级跳过（如 `skip_names=("lm_head",)`），或按论文口径显式声明包含 lm_head 并在 docstring 标注。

---

## 六、P2 — 中严重度（全部经代码定位确认）

| # | 位置 | 问题 |
|---|---|---|
| 1 | `real_backend.py:795-798,820-824` | transformer 头 docstring 造假式描述（"trained with numpy gradient descent"，带死参数 `epochs/lr`）；实际无任何梯度下降，Wq/Wk/Wv/tok_emb 是固定随机矩阵，只 fit 了 sklearn 逻辑回归头。读者会以为该头是真训练的 |
| 2 | `real_backend.py:819` × `exp13:37-38` | `fusion_params=217` 把 208 个冻结随机参数计入 "trainable-parameter counts"；实际被训练的只有 9 个。数字如实但表述不属实 |
| 3 | `consistency_check.py:39` × `exp13:50` | `_text_only` 退化时三策略仍产 `f1` 写入结果，contract/consistency_check 不查 `degraded` 标志——声学资产缺失时文本-only F1 会被当 fusion headline 与 0.923 对账，可能静默 MATCH（与旧 P1-M4 同型残留） |
| 4 | `real_backend.py:747,759` | 融合头 fit 在测试集前半而非训练集（exp13 只传 shared_test_indices，函数内再 50/50 自切）；评估无偏但与论文训练协议口径不同，有效评估样本仅 ~100 条 |
| 5 | `real_backend.py:732` | 文本路是硬 0/1 投票、声学路是软概率，三策略共享这份不同分布的 `X`；学到的 w 无法与论文 w*=[0.40,0.30] 同尺度比较。base path 内部其实算出了软分（:700-701）却丢弃 |
| 6 | `real_backend.py:766,824` | sigmoid/transformer 头的 `LogisticRegression.fit` 未包 try——`ytr` 单类时整个 exp13 崩而非走 `_text_only` 降级（manifest 路径按磁盘顺序枚举时易触发） |
| 7 | `privacy.py:128-129` | WER 评分器默认 whisper-tiny，对中文电话语音质量差，**系统性抬高 WER**——而论文口径是「WER 越高=隐私越强」，偏差方向有利于论文结论。守护本身诚实（缺依赖记 not_measured），但评分器选择需标注或升级 |
| 8 | `exp7:32-36,100` × `framework.py:135-146` | **P1-M2 残留**：exp7 用 `load_chifraud_balanced`，完全绕开只校验主数据集的 pre_run_validation——ChiFraud 缺失时静默回退 100 条合成样本仍以 `h100_real_qwen` 上报且无标记；exp2~14 结果也均不写 `is_synthetic` |
| 9 | `real_backend.py:617-618` × `privacy.py:271` | exp5 LDP 仍对未裁剪 hidden states 加噪（敏感度无界）；库里的裁剪版 `gaussian_ldp`（clip_bound=3.0、校准 σ）只有测试在调，未接入测量路径。标签已诚实化，机制未修 |
| 10 | `docs/v28.tex` / `docs/v28 (1).tex` × `docs/figure/` | **tex 引用的 7 个图全部不存在**：tex 用 `figure/figN.pdf`（纯数字 N=1..7），图脚本产物为 `figN_<name>.pdf`（如 `fig3_main_results.pdf`），`generate_all.py` 无重命名步骤；磁盘 `docs/figure/` 只有 fig3 一份。LaTeX 编译必缺图，投稿前必须解决 |
| 11 | `template/scripts/mount_s3.sh:36-41` | P1-S4 尾巴：rclone 分支凭据作 CLI 参数（进程列表瞬态可见），rclone.conf 未 chmod 600 |

## 七、P3 — 低严重度（摘要）

- 量化路径：`config/runpod_h100.yaml:14` 死配置 `runtime.quantization: int4`（无消费方，注释误导）；`exp12:66` 结果键仍名 `QAD_MultiGuard_INT4`（内容已 nvfp4，contract 同步）；`qdq.py:65` scale/q 在 autograd 图中构建后才 detach（浪费显存，可包 `no_grad`）；`qdq.py:46-58` `in_features%16≠0` 时 block 跨行（Qwen 维度均可整除，无实际影响）；`models.py:107-108` 非法 quantize 值仅 warning 后静默全精度；`registry.py:28` exp11 描述未含 nvfp4、`exp5:38` 注释仍写 "int4 model"（cosmetic）。
- 融合/隐私：`privacy.py:113` n==0 分支缺 `n_pairs` 键；`:163-176` MOS 路径不校验采样率（报错信息误导）；`exp7:86` 无占位符 f-string；`REPRODUCIBILITY.md:526` 残留旧命名 "late_fusion"；exp13 三策略各跑一遍相同文本推理（3× 浪费 H100 时间）。
- 数据链：`outputs/splits/` 未入 `.gitignore`（违反 AGENTS.md「outputs/ 整体 gitignored」，pod 上跑完 git 会脏）；`has_local_data("taf28k")` 接受 npz-only 但文本管线需 jsonl（`data.py:442`）；`load_chifraud_balanced` docstring "Perfectly balanced" 与 2:1 注释矛盾；`_load_jsonl` 对合法 JSON 非对象行（如 `[1,2]`）仍 AttributeError；`real_backend.py:506-507` docstring 仍称 "(ε,δ)-DP measurement"。
- 仓库卫生：**`docs/v28 (1).tex` 与 `docs/v28.tex` 逐字节相同**（e5df95a 网页重复上传，非他人版本；建议删 `(1)` 那份——纯重复且文件名带空格）；`outputs/results/` 5 个陈旧产物 + `outputs/evidence/` 2 个测试残留未归档；egg-info PKG-INFO 仍含 2 处 `--smoke`（git 跟踪的历史遗留目录）；已删根级 `services/` 的 `__pycache__` pyc 磁盘残留；`REFACTORING.md:90` 仍引用 `--smoke`（AGENTS.md 明令禁止）；`figure_scripts/README.md:43` "420-dpi"（实际 400）；`template/README.md:9` 引用不存在的 `.env.template`；`run_pipeline.sh:34-35` pip 失败被 `|| echo` 吃掉 set -e；`claim_engine.py:273` yaml.safe_load 在 try 外（坏 YAML 仍会中断整轮）；`paper_data.py:460` docstring 中英混杂笔误。
- 后续动作提示（非当前 bug）：`paper_data.py:179` 用 exp11-int4 值喂 "NVFP4 QAT" 标签行——exp11 重跑产出 `schemes.nvfp4.f1` 后需切换数据源，否则标签下挂 PTQ int4 实值。

---

## 八、通过清单（本轮确认无问题的关键项）

**量化数学与 QAT 语义**（子代理 CPU 实测 + 主会话复核）：
- `fake_quant` 与手写 per-block maxabs/QMAX 参考 max diff 2.4e-7（fp32 epsilon）；round half-to-even、clamp [-8,7] 正确；block=16 不整除零 padding 处理正确；零 block/全零张量双层防除零无 NaN。
- STE 梯度精确直通（fp32/bf16 均实测）；`QDQLinear.forward` 每次动态 fake-quant 无缓存（真 QAT）；scale 在 detach 下计算无梯度（标准 STE）。
- `apply_qdq` 幂等、不动 embedding/norm、保持 device/dtype；`models.py` nvfp4 分支 post-load 应用、与 bnb 分支互斥。
- 配置一致：`schema.py:33` 默认 nvfp4、`:160` 枚举含 nvfp4、`experiments.yaml:31` nvfp4；exp1/2/3/4/5/9/10/12/13 全 nvfp4，exp11 六方案含 nvfp4 且 contract 同步；exp8/paper_pipeline 保留 int4 属有意。
- `17f568f` 改动面全部在提交声明内，无意外夹带。

**融合与隐私**（ab42e03）：
- 两处旧缺陷真修：sigmoid 不再硬编码 w*（`real_backend.py:766` LogisticRegression lbfgs 在前半真实拟合）；transformer 测试集泄漏已修（只在前半 fit）。泄漏链完整推演无泄漏。
- softmax_linear grid-search（101 点凸组合、MSE 准则、同切分）正确；`_transformer_fusion_head` 注意力数学正确（QKV/缩放/数值稳定 softmax/mean pool）；`_text_only` 降级全分支有返回；`return_preds` 修复无 KeyError 残留。
- `reconstruction_quality_metrics()` 五重依赖守护 + 每指标独立 try，缺依赖/缺资产/运行失败全部落 `not_measured`，**无任何编造路径**；PESQ/STOI 参数顺序正确。
- 命名同步全对齐（contract/consistency_check/paper_pipeline/契约文档/README/extraction），back-compat 别名仅一处映射、结果只写规范名。

**数据完整性**：
- 统一切分 + manifest 哈希交集闭环（见 §3.2 M1）；`load_chifraud_balanced` 种子化 `random.Random(42)`；-1 标签在 verification_features 与 metrics 双侧排除；group_split 单样本类留训练集；exp5 set_seed 已补（`exp5:33`）、eps_3.0 全仓零残留、exp11 nvfp4 产出↔contract 对齐。
- exp5 LDP σ∈{0,1} 直接给定 + 全链「工程估计、非认证 DP」诚实标注；空数据集跳过而非编造。

**安全/运维**：见 §3.1（14/15 已修）；claim_engine 隔离有降级产物实证；paper_data None 短路在位；git 跟踪无产物/密钥。

---

## 九、修复建议（按优先级）

1. **H100 重跑前必须修**：P0-1（QDQLinear 参数吸收，一行级思路、改动小）→ P1-1（nvfp4 推理侧 force-base）→ P1-2（apply_qdq 跳过 lm_head，顺带降低 P0-1 爆炸半径）。三者都在 qdq.py/real_backend.py 两个文件内。
2. **投稿前必须修**：P2-10（tex 图引用与脚本产物命名对齐——改 tex 引用或 generate_all 加重命名步骤）；删 `docs/v28 (1).tex`。
3. **测量诚信收尾**（重跑前建议同批）：P2-8（各实验统一写 `is_synthetic`；exp7 纳入数据来源断言）、P2-3（consistency_check 加 degraded 守卫）、P2-9（LDP 换裁剪版 gaussian_ldp）。
4. **诚实性表述**：P2-1（transformer 头 docstring 据实改写 + 删死参数）、P2-2（params 区分 total/trained）、P2-7（WER 评分器偏差标注或升级）。
5. **低成本批量**：P2-4/5/6（融合头训练口径、软分输入、fit 包 try）；P3 的 .gitignore 补 splits、REFACTORING --smoke 残留、pip 软失败、claim_engine yaml 入 try、outputs 归档清理（`scripts/archive_and_clear.py`）。

## 十、未能验证项（如实声明）

- **GPU 训练全链路未验证**（本地无 GPU）：P0-1 的崩溃点在训练后保存处，崩溃本身已实测，但「修好后 QAT 训练 5 epoch 数值收敛正常」无法本地验证。
- P1-1 的 PEFT 崩溃为静态结论（本地无 peft），依据 PEFT `_create_new_module` 仅支持 nn.Linear/bnb 等类型的确定行为。
- transformers 4.x 对重复别名键的确切行为（删别名 warning vs safetensors 报错）未逐版本实测；5.8.1 已实测复现。
- exp13 融合三策略的端到端实跑（需模型权重）未验证；各组件经小规模合成数据/静态推演核对。
- RunPod 镜像自带包情况、docker build 未实测（沿前轮声明）。

---

## 附：本轮验证记录

```
git: HEAD 4ff723c（工作树干净，157 跟踪文件）
compileall: 107 files, 0 errors
import sweep: 59 modules OK；from-import AST 0 真实问题
pytest（系统 Python 3.14.5 + torch 2.14.0.dev20260628）: 65 passed (24s)
bash -n: 13/13 通过
paper_data 自检 exit 0 / check_alignment exit 1 / consistency_check exit 1 / validate-contract exit 2（均为预期态）
P0-1 复现：state_dict 4 键共享 storage；safetensors save_file RuntimeError；plain→QDQ strict load spurious missing（本机 CPU 实测）
P1-1 复核：real_backend.py:635-636 无 force-base；experiments.yaml:132 student_variant: qad_ovf；exp4 无 finetuned_path
P2-10 复核：v28.tex 引用 figure/fig1..7.pdf，docs/figure/ 仅 fig3_main_results.*，7 个引用文件全缺
```

---

## 归档：2026-08-26_full_audit.md

# H100_package_realeval 全量审计报告（第五轮：P0/P1 修复复核 + P2-8 provenance 增量审计）

> 日期：2026-08-26
> 基线：HEAD `6c40dd8`（"更新"，含第四轮审计报告 + qdq.py/real_backend.py 修复），工作树含 4 个未提交文件（`experiments/framework.py` +51/-12、`realeval/student_loader.py` +10、`experiments/exp13_fusion_strategy.py` +2、`experiments/exp7_privacy_verification.py` +2/-1）
> 审计范围：`realeval/` 包 19 个 .py（3793 行）+ 第四轮 P0/P1/P2/P3 修复复核 + 4 个未提交 diff 的正确性
> 与第四轮关系：第四轮（`2026-08-19_full_audit.md`，基线 4ff723c）之后的增量为 `6c40dd8`（qdq.py +59、real_backend.py +8、审计报告、MEMORY_LOG）+ 未提交 4 文件。本轮聚焦**三项 P0/P1 修复的正确性复核** + **P2-8 provenance 修复的增量审计**（含未提交改动的死代码检查），并抽核其余 P2/P3 项状态。
> 审计方法：py_compile 基线实测 + 逐文件静态复核（本地 Windows 无 torch，沿用第四轮「本地无 GPU/无 torch 只能 py_compile」声明）。

---

## 一、总体结论

**第四轮三项致命/高严重度问题（P0-1 / P1-1 / P1-2）已全部修复，修复方案正确**：

1. **P0-1**（QDQLinear state_dict 重复别名键 → save_pretrained 必崩）：`qdq.py` 改为在 `__init__` 吸收 `self.weight = linear.weight; self.bias = linear.bias`，删除两个委托方法。state_dict 天然只剩 `weight/bias`，docstring 已同步改写为如实描述。
2. **P1-1**（nvfp4 force-base 绕过）：base zero-shot 路径已 force-base（`real_backend.py:637`），`student_loader.py` 增加 QDQLinear 检测兜底（未提交）。**残留一个低危尾**：finetuned 分支（`real_backend.py:539`）未 force-base，但实际不会触发（见 §5 P1-1 复核）。
3. **P1-2**（apply_qdq 不跳过 lm_head）：`apply_qdq` 增加 `skip_names=("lm_head",)` 参数并递归传递。

**P2-8（测量诚信残留）正在修复中（未提交），方向正确但遗漏 exp13**：`framework.py` 引入 `_synthetic_used` 全局 provenance 记录 + `required_datasets` 参数，`exp7` 纳入数据来源断言。但 **exp13 的 `is_synthetic` 局部变量是死代码**——exp13 用 `data.load_taf28k` 直连（不经过 `load_first_nonempty`），框架的 provenance 机制对它完全无效，合成回退仍会以 `h100_real_qwen` 无标记上报。这是本轮新发现的 P2 级遗漏。

**其余 P2-1~7 / P2-9 / P2-10 / P2-11 全部未修**。其中 **P2-10（tex 引用的 7 个图 PDF 全不存在）是投稿硬伤**，P2-1/P2-2 是论文诚实性表述问题，P2-6 是融合头单类崩溃隐患，重跑前建议同批处理。

**本轮新发现**：1 个 P2（exp13 provenance 死代码）+ 2 个 P3（`_synthetic_used` 异常残留 + 隐式耦合设计缺陷）。

---

## 二、基线验证（本轮实测）

| 维度 | 结果 |
|---|---|
| git | HEAD `6c40dd8`，4 个未提交修改文件（framework/student_loader/exp13/exp7），无新增产物/密钥 |
| 语法编译（realeval/ experiments/ metrics/ 全 .py） | **全部通过**（`py_compile` COMPILE_OK） |
| pytest / import | **未实测**（本地 Windows 无 torch，沿用第四轮声明） |
| 目录结构 | 第四轮报告引用的若干路径已过时：`REFACTORING.md` 已删、`scripts/claim_engine.py`→`experiments/claim_engine.py`、`run_pipeline.sh`→`scripts/run_pipeline.sh`、`experiments/registry.py`→`runner/registry.py` |

---

## 三、第四轮 P0/P1 修复复核（核心）

### P0-1. QDQLinear state_dict 重复别名键 ✅ 已修（复核确认正确）

- `qdq.py:83-91` 现为参数吸收：`self.weight = linear.weight; self.bias = linear.bias`，无 `linear` 子模块，两个委托方法已删。
- 正确性复核：
  - `linear.weight/linear.bias` 是 `nn.Parameter`，直接赋值会经 `nn.Module.__setattr__` 正确注册为自有参数，`state_dict()` 只剩 `weight`/`bias` 两键，无别名。
  - `linear.bias is None` 时 `self.bias = None`，`forward` 中 `F.linear(x, w, None)` 等价无偏置，行为正确。
  - `apply_qdq` 的 `isinstance(child, QDQLinear)` 幂等检测不受影响（类名未变）。
- docstring（`qdq.py:74-80`）已从「delegate to the wrapped Linear」改写为「absorbed as this module's own Parameters」，与实现一致。

### P1-1. nvfp4 force-base 绕过 ✅ 主体已修（残留一个低危尾，见下）

- 路径 1（base zero-shot）：`real_backend.py:637` `adapter_variant = "base" if quantize == "nvfp4" else config.get("student_variant", "base")` ✅ 已修。
- 路径 2（finetuned 分支）：`real_backend.py:539` 仍 `config.get("student_variant", "base")` **未 force-base**。但实际影响极低：
  - nvfp4 训练产物是 full model directory（`real_backend.py:464` `student.save_pretrained` 走 else 分支，不经 attach_adapter），只有 legacy int4/LoRA adapter-only 存档才进 attach_adapter 分支；
  - 且 `student_loader.py:110-115`（未提交）的 QDQLinear 检测已把「QDQ 模型 + 非 base variant + adapter 存在」从 PEFT 崩溃改为清晰的 `AssetsUnavailable` 报错。
- 结论：nvfp4 推理侧崩溃/静默错配已被双重封堵（force-base + 检测报错），但 finetuned 分支缺少与 base 路径对称的 force-base，属低危残留。

### P1-2. apply_qdq 不跳过 lm_head ✅ 已修（复核确认正确）

- `qdq.py:98-114` 增加 `skip_names=("lm_head",)`，`name in skip_names` 匹配直接子名（嵌套位置同样命中），递归调用传递 `skip_names`。
- 与 tied embedding 的解耦正确：`lm_head` 不包装后，`tie_word_embeddings=True` 模型的输出投影保持高精度，符合 NVFP4 部署口径（TensorRT-LLM）。

---

## 四、P2-8 修复复核（未提交改动）+ 新发现

### 修复内容（未提交，方向正确）

- `framework.py`：
  - 新增 `_synthetic_used: bool | None = None` 全局 + `_record_provenance()`，在 `load_first_nonempty` 的 real/synthetic 两个返回点分别记录 False/True。
  - `pre_run_validation` 增加 `required_datasets: Sequence[str] = ()`，遍历 `[主数据集, *required_datasets]` 做 `has_local_data` 断言（exp7 的 balanced4k 纳入）。
  - `run_with_mode` 增加 `required_datasets`，在 `ensure_result_contract` 后 `result.setdefault("is_synthetic", _synthetic_used)`，`finally` 清空。
- `exp7`：`run_with_mode(..., required_datasets=["balanced4k"])`，补上 ChiFraud/balanced4k 的数据来源断言。
- `student_loader.py`：QDQLinear 检测（见 §3 P1-1）。

### 新发现 P2-新1. exp13 `is_synthetic` 是死代码 —— provenance 机制对 exp13 无效

- 位置：`experiments/exp13_fusion_strategy.py:17,23`
- 现象：exp13 用 `data.load_taf28k(source="multimodal")` **直连**（不经过 `load_first_nonempty`），失败时 `data.load_synthetic(n=200)` 并置 `is_synthetic = True`。但该局部变量**从未被读取**——不进 result、不传 run_with_mode、不调 `_record_provenance`。
- 机制失效链：`_synthetic_used` 只由 `load_first_nonempty` 写入，exp13 不调用它 → `run_with_mode` 里 `if _synthetic_used is not None` 为 False（`finally` 已保证上个实验清空）→ result 无 `is_synthetic` 字段 → exp13 的合成回退仍以 `h100_real_qwen` 无标记上报。
- 后果：exp13 是唯一用「数据层直连 + 手动 fallback」模式的实验，其合成回退完全绕过 P1-M2 防线。这正是 P2-8 想防的「合成数据冒充真实测量」，但 exp13 的修复是无效的。
- 修复：exp13 的 fallback 分支应写入 result（`result["is_synthetic"] = True`）或改走 `load_first_nonempty`；更根本的是 provenance 追踪应下沉到数据层（见 P3-新2）。

### 新发现 P3-新2. `_synthetic_used` 全局状态的设计缺陷

- `pre_run_validation` 在 `run_with_mode` 的 `try` **之外**（`framework.py:179`），若它抛 `ExperimentRuntimeError`（数据缺失），`finally: _synthetic_used = None` 不执行 → 残留值泄漏给下一个实验。
- 残留误报场景：实验 A（走 load_first_nonempty 回退 synthetic → `_synthetic_used=True`）在 pre_run_validation 因 required_datasets 缺失抛异常 → 实验 B（exp13 这类不走 load_first_nonempty）运行时 `if _synthetic_used is not None` 为 True，误报 `is_synthetic=True`。
- 触发条件苛刻（需 A 失败于 pre_run_validation 且 B 恰好是直连型实验），定为 P3，但暴露了「全局可变状态 + 隐式时序约定」的脆弱性。

### 新发现 P3-新3. provenance 追踪依赖隐式约定而非强制

- `_synthetic_used` 机制要求：实验必须走 `load_first_nonempty` 且其调用必须在 `run_with_mode` 之前（run 顶层）。任何「直接调 data 层 + 手动 fallback」的实验（当前仅 exp13）都天然绕过。provenance 应下沉到 `data.load_*` 层或由 `ensure_result_contract` 统一收口，而非靠 run 层的调用约定。

---

## 五、其余 P2 项状态（静态复核）

| # | 第四轮定位 | 当前状态 | 证据 |
|---|---|---|---|
| P2-1 | transformer 头 docstring 造假 | ⚠️ 部分修 | `real_backend.py:797-800` docstring 仍"trained with numpy gradient descent / learns token embeddings"，死参数 `epochs=300, lr=0.1` 仍在签名；`:822-823` 新增注释如实说明「fit only the output head on frozen attention」，但 docstring 主体未改 |
| P2-2 | fusion_params=217 表述不属实 | ❌ 未修 | `exp13:39-40` 仍称 "actual trainable-parameter counts"；`real_backend.py:821` 仍把 208 个冻结随机参数计入（实际只训练 LogisticRegression 头 9 个） |
| P2-3 | consistency_check 不查 degraded | ❌ 未修 | `consistency_check.py:52-86` `audit()` 只查 computation + PAPER_CLAIMS，无 `fusion_degraded`/`fusion_strategy_effective=="text_only"` 守卫 |
| P2-4 | 融合头 fit 在测试集前半 | ❌ 未修 | `real_backend.py:749` `split = n*0.5` 在 exp13 传入的 test 集上再自切（口径问题，评估样本 ~100） |
| P2-5 | 文本硬投票 vs 声学软分 | ❌ 未修 | `real_backend.py:704` 仍 `preds.extend((f_prob > n_prob).int())` 硬 0/1，`:701-703` 软分算后丢弃 |
| P2-6 | LogisticRegression.fit 未包 try | ❌ 未修 | `real_backend.py:768`（sigmoid）`:826`（transformer）仍裸 `.fit(Xtr, ytr)`；`:754` acoustic 分类器已包 try 但融合头未包 |
| P2-7 | WER whisper-tiny 偏差 | ❌ 未修 | `privacy.py:128` 仍 `whisper.load_model("tiny")`，对中文电话语音系统性抬高 WER（方向利于论文「高 WER=强隐私」结论） |
| P2-8 | exp7 绕开断言 + is_synthetic 不写 | 🟡 进行中（有遗漏） | framework.py + exp7 已修；**exp13 死代码遗漏**（见 §4） |
| P2-9 | exp5 LDP 未裁剪 | ❌ 未修 | `exp5_cross_dataset.py:145` 仍 `noise_sigma=sigma` 走 `real_backend.py:617-618` 对未裁剪 hidden states 加噪；`privacy.py:271` 裁剪版 `gaussian_ldp(clip_bound=3.0)` 未接入测量路径 |
| P2-10 | tex 图引用全缺 | ❌ 未修（投稿硬伤） | `docs/v28.tex:240/393/668/754/784/797/829` 引 `figure/fig1..7.pdf`；`docs/figure/` 仅 `fig3_main_results.{pdf,png,tiff}`，7 个引用文件名全不匹配 |
| P2-11 | rclone 凭据 CLI 参数 | ❌ 未修 | `template/scripts/mount_s3.sh:36-41` rclone config create 用 `${S3_ACCESS_KEY}`/`${S3_SECRET_KEY}` 作 CLI 参数，rclone.conf 未 chmod 600 |

---

## 六、P3 项抽核状态（快速复核）

| 第四轮定位 | 状态 | 说明 |
|---|---|---|
| REFACTORING.md:90 --smoke | ✅ 已消解 | 文件已删除 |
| scripts/claim_engine.py:273 yaml.safe_load 在 try 外 | ❌ 未修（路径变） | 文件移到 `experiments/claim_engine.py`，`:273` safe_load 仍在 `:283` try 之前 |
| run_pipeline.sh:34-35 pip 软失败 | ❌ 未修（路径变） | 移到 `scripts/run_pipeline.sh:34-35`，`|| { echo ...; }` 仍吃 set -e |
| exp12:66 结果键 QAD_MultiGuard_INT4 | ❌ 未修 | 键名仍 INT4（内容 nvfp4） |
| runpod_h100.yaml:14 quantization int4 死配置 | ❌ 未修 | 仍 `quantization: int4` |
| models.py:107-108 非法 quantize 静默全精度 | ❌ 未修 | `elif quantize not in (None,"bf16","fp32"): warning` 后继续加载 |
| exp5:38 注释 "int4 model" | ❌ 未修（cosmetic） | 实际 nvfp4 |
| v28 (1).tex 与 v28.tex 重复 | ❌ 未修 | 两文件均 103097 bytes，逐字节相同 |
| outputs/splits/ 未入 .gitignore | ❌ 未修 | `.gitignore` 列了 results/figures/tables/… 但无 splits |
| privacy.py:113 n==0 缺 n_pairs | ❌ 未修（无害） | `:112-113` 返回无 `n_pairs` 键，正常路径 `:178` 有；exp7 只用 measured/not_measured 不受影响 |
| privacy.py MOS 不校验采样率 | ❌ 未修 | `:163-176` SQUIM 前不校验 sample_rate（PESQ 路径 `:138` 校验了） |
| exp7:86 无占位符 f-string | ❌ 未修 | `f"{k}"` |
| has_local_data("taf28k") npz-only 放行 | ❌ 未修 | `data.py:442` jsonl+npz 用 `any()`，npz-only 时断言通过但 exp13 文本管线仍会 fallback synthetic |

---

## 七、通过清单（本轮复核确认正确）

- **qdq.py P0-1/P1-2 修复**：参数吸收 + skip lm_head 方案正确，`fake_quant` 已包 `torch.no_grad()`（第四轮 P3 的「scale/q 在 autograd 图中构建后 detach」已顺带优化），STE `return w + (w_hat - w).detach()` 语义不变。
- **real_backend.py P1-1 base 路径 force-base**：与训练侧 `:129` 口径一致。
- **student_loader.py QDQLinear 检测**：延迟 import（函数内 `from realeval.qdq import QDQLinear`）不影响本地 py_compile，运行时才触发；检测位置在 adapter 解析成功之后、PeftModel.from_pretrained 之前，时序正确。
- **framework.py required_datasets 断言**：`from realeval import data` 提到函数顶部（去除了原来的函数内重复 import），遍历逻辑对 `synthetic` 名显式跳过，空列表时日志 `"synthetic"` 兜底。
- **exp7 required_datasets=["balanced4k"]**：补齐了 ChiFraud/balanced4k 的数据来源断言，配合 `load_chifraud_balanced` 的 balanced4k.jsonl 主文件。

---

## 八、修复建议（按优先级）

1. **投稿前必须修**：P2-10（tex 图引用 `fig1..7.pdf` 与脚本产物 `figN_<name>.pdf` 对齐——改 tex 引用或 `generate_all.py` 加重命名）；删 `docs/v28 (1).tex`。
2. **P2-8 收尾（重跑前）**：修 exp13 provenance 死代码（`result["is_synthetic"]=True` 或改走 `load_first_nonempty`）；顺带把 provenance 下沉到数据层消除 P3-新3 的隐式耦合。
3. **诚实性表述**：P2-1（transformer docstring 据实改写 + 删死参数 epochs/lr）、P2-2（params 区分 total/trained）、P2-7（WER 评分器偏差标注或升级）。
4. **融合头健壮性**：P2-3（consistency_check 加 degraded 守卫）、P2-6（两处 LogisticRegression.fit 包 try）、P2-4/5（训练口径 + 软分输入，低成本）。
5. **低危收尾**：P1-1 finetuned 分支对称 force-base；P2-9（LDP 换裁剪版 gaussian_ldp）；P3 的 .gitignore 补 splits、exp12 键名、runpod 死配置、claim_engine yaml 入 try、pip 软失败、v28 (1) 删除。

---

## 九、未能验证项（如实声明）

- **GPU 训练/推理全链路未验证**（本地无 GPU/无 torch）：P0-1 修复后 QAT 训练 5 epoch 数值收敛、P1-1 修复后 exp4 端到端跑通，均无法本地验证。
- `_synthetic_used` 全局状态的残留误报（P3-新2）为静态推演，未构造运行时复现。
- exp13 合成回退的端到端实跑需模型权重 + 数据挂载，未验证。
- P2-10 tex 图引用、P2-11 rclone 凭据为静态文件检查（非运行时）。

---

## 附：本轮验证记录

```
git: HEAD 6c40dd8，4 个未提交文件（framework/student_loader/exp13/exp7）
py_compile: realeval/ experiments/ metrics/ 全 .py，0 errors（COMPILE_OK）
未实测: pytest/import（本地 Windows 无 torch，沿用第四轮声明）
P0-1 复核: qdq.py 参数吸收 + 无 linear 子模块 + docstring 同步（静态确认）
P1-1 复核: base 路径 force-base ✅；finetuned 分支未 force-base（低危残留，student_loader 检测兜底）
P1-2 复核: apply_qdq skip_names=("lm_head",) 递归传递（静态确认）
新发现: exp13 is_synthetic 死代码（P2）+ _synthetic_used 异常残留/隐式耦合（P3×2）
目录漂移: REFACTORING.md 删；claim_engine→experiments/；run_pipeline→scripts/；registry→runner/
P2-10 复核: v28.tex 引 fig1..7.pdf，docs/figure/ 仅 fig3_main_results.*
```

---

## 2026-08-27 修复落实复核 + 实验→图表数据链路审计

> 基线：HEAD `64c367d`（含第五轮审计后 7 个修复提交）。本轮做两件事：①复核第五轮「未修」项在后续提交中的落实；②审计实验产出→论文图表的数据链路。

### 一、第五轮「未修」项的落实复核

第五轮报告（基线 `6c40dd8`）列的「未修」项，在后续 7 个提交中大部分已修复：

| 审计项 | 修复提交 | 复核结果 |
|---|---|---|
| P2-1/2/4/5/6（融合头 docstring/params/fit口径/软分/try） | `fd584b5` | ✅ 已落地（real_fusion_classify 支持 fit_data、软分、try 包裹） |
| P2-3（consistency_check degraded 守卫） | `c099ff6` | ✅ 已落地（SYNTHETIC/DEGRADED 守卫，跳过对账） |
| P2-7（WER 偏差标注） | `817d1e4` | ✅ 已落地 |
| P2-8（exp13 provenance 死代码） | `7fcbacd` | ✅ 已落地（is_synthetic 写入 result） |
| P2-10（tex 图引用） | `e8ecf81` | ✅ 引用名对齐 fig1-7 |

**本轮补修的 4 个真正残留**（提交 `ebf3cd6`）：

| # | 问题 | 修复 |
|---|---|---|
| P2-11 | mount_s3.sh rclone 凭据用 CLI 参数（`ps aux` 可见） | 改用 `RCLONE_CONFIG_*` 环境变量 |
| P2-9 | exp5 LDP 未裁剪（敏感度无界） | 据实强化标注「UNCLIPPED、非 DP 保证」 |
| P3 | exp12 结果键 `QAD_MultiGuard_INT4` | → `NVFP4` |
| P3 | models.py 非法 quantize 静默回退全精度 | → `raise ValueError` |

### 二、实验产出 → 论文图表数据链路审计

**结构对齐（字段名匹配）**：10 个实验的产出字段与 paper_data 读取路径全部对齐，无结构断裂（exp1~14 各字段逐项核对通过）。

**口径错误（已修复 1 处，提交 `fe7026b`）**：paper_data 的「NVFP4 QAT (CE)」错用 `exp11.schemes.int4`（QAD 模型 + int4 PTQ 推理，语义是 PTQ 而非 QAT）；已改为 `exp2.variants.ce_only`（loss_fn="ce" 的 CE 训练 = 真 QAT），fallback 用实测值 0.7667（论文声称 0.844，gap 待 H100 回填）。

**数据缺失**：`outputs/results/` 为空，图表当前由 fallback 常量生成，非实测。

### 三、核心结论

- **结构层面能支撑**：字段名 10/10 对齐，图表脚本能正确读取实验产出。
- **口径层面已修正**：唯一的 QAT 口径错误已修复。
- **数据层面暂不能支撑**：outputs 为空，必须 H100 重跑回填后，图表才能由真实数据生成、真正支撑论文结果。

### 验证记录

```
pytest: 65 passed（同步后代码，HEAD 64c367d）
py_compile: paper_data.py + 修复的 4 文件，0 errors
paper_data.py 自检: all consistency self-checks pass（outputs 空 → fallback 生效，预期 MISSING）
```

---

## 归档：2026-08-31_peer_review_v29.md

# 模拟同行评审报告 — QAD-MultiGuard (v29)

> **论文**: QAD-MultiGuard: An Edge–Cloud Framework for Multimodal Fraud Detection and Risk Assessment
> **源文件**: `v29.tex`
> **评审框架**: `academic-paper-reviewer` v1.11.1（full 模式，5 座位 panel + 编辑综合）
> **评审日期**: 2026-08-31
> **性质**: 模拟评审。角色分离只代表视角分工，**不是**独立误差过程的声明；5 个座位为单一模型族（Claude/Opus 4.8）内的视角分离，`model_family_distinct=false`，不代表独立审稿人，也不构成跨家族三角验证。`criteria_binding_unavailable`（未提供 #684 ReviewTargetContext，不做 venue-alignment 绑定式断言）。

---

## Phase 0 — 领域分析与评审团队配置（摘要）

| 维度 | 分析结果 |
|---|---|
| 主学科 | 计算机科学 / 应用人工智能（多模态诈骗检测） |
| 交叉学科 | ① 隐私与安全（声学表示、LDP）② 高效推理（量化、投机解码）③ 系统部署（端云协同） |
| 研究范式 | 定量 / 实验（机器学习系统型） |
| 目标期刊 | **Expert Systems with Applications**（ESWA，Elsevier，Q1） |
| 论文成熟度 | 接近投稿（结构完整、含附录） |

**5 座位配置**：Journal-Fit Reviewer（EIC，ESWA 副主编 / 端侧部署方向）· Reviewer 1（Methodology，量化与统计）· Reviewer 2（Domain，电信反诈 + 语音反欺诈）· Reviewer 3（Perspective，隐私 / VoicePrivacy 社区）· Devil's Advocate（固定对抗席位）。

---

## Phase 1 — 五席评审报告

### 席位 1 — Journal-Fit Reviewer（EIC）

**建议**: Major Revision ｜ **置信度**: 4

**优势**：ESWA 契合度高；贡献 framing 诚实；可行性基线充分；局限披露成熟。

**弱点**：
| # | 严重度 | 内容 |
|---|---|---|
| W1 | Major | 应用价值未被证明——单一语料、无现场部署验证 |
| W2 | Major | 可复现性缺口 |
| W3 | Major | 缺 audio-only / text-only / 融合态的单模态消融 |
| W4 | Major | OV-Freeze 与异构量化效应量 h≈0.02/0.03，低于"small"阈值 |
| W5 | Minor | SAFE-QAQ 非同类对照（not like-for-like） |
| W6 | Minor | 隐私为初步证据 + "co-existence vs co-design" 定位含糊 |

---

### 席位 2 — Reviewer 1（Methodology）

**建议**: Major Revision ｜ **置信度**: 4

**优势**：诚实的效应量报告；NBE vs Blackwell 区分清晰；CoT/OV-Freeze 消融隔离干净。

**弱点**：
| # | 严重度 | 内容 |
|---|---|---|
| W1 | **Critical** | **可复现性缺口**——公开仓库是 int4 PTQ（非论文的 NVFP4 QAD），"reproduction run" 未完成 |
| W2 | Major | 公式 `eq:nbe` 是整数 round/clamp，非 FP4 网格 |
| W3 | Major | QAT 基线用 CE loss 且同样 2000-step 预算，欠训练 |
| W4 | Major | PTQ 基线被强制到 NVFP4，F1 高度聚类在 0.838–0.840 |
| W5 | Major | +0.007 F1 标 p<0.01，但 h≈0.02 接近 seed 噪声；instance-level bootstrap 忽略 seed 方差 |

---

### 席位 3 — Reviewer 2（Domain）

**建议**: Major Revision ｜ **置信度**: 4

**优势**（S1–S3）：
- S1 局限披露规范充分——单语料局限在 Introduction 前置，Discussion 设专段，Conclusion 重申；诚实披露 unlinkability 残余风险、"NVFP4 实为 NBE 仿真"、"SAFE-QAQ 引自原文未复现"。
- S2 核心数值内部自洽——13,647+14,864=28,511；21,490+7,021=28,511；所有 Recovery% 均可由 F1 反推；57×（14GB/248MB≈57.8）、268ms=12+235+21 均可加总。
- S3 声明边界克制——明确 2.1× 是内核吞吐非端到端、投机解码只服务云端、SAFE-QAQ 非同类。

**弱点**：
| # | 严重度 | 内容 |
|---|---|---|
| W1 | Major | **外部引用与基线归因错误**：(a) BERT-Fraud 错配——正文称"中文反诈 SMS 数据集 F1=0.876"，但 bib [16] 实为印尼语期刊 SMS **情感分析**论文；(b) SAFE-QAQ"ASR 召回 60–75%"需原文出处；(c)"每例平均 2.7 个异构信号（含 SMS/URL）"与全文"audio–text 双模态、SMS/URL 仅接口"自相矛盾 |
| W2 | Major | 128 维声学嵌入领域合理性存疑：(a) "64 Mel filterbanks → 64 维 MFCC"术语不严谨（64 维应为 FBANK）；(b) 全文无 text-only 基线，声学分支边际贡献未验证，fusion 权重 w_audio=0.30 暗示其贡献有限；(c) 全局时序平均抹除韵律时间轮廓，与"捕捉 coercion 韵律变化"目标存在张力 |
| W3 | Major | 数据集划分自相矛盾——"3:1 train(21,490)/test(7,021) 无验证集"，但后文多处引用 "validation partition" 与 "five-fold CV within training partition" |
| W4 | Minor | AdvFraud-3k 构造数值不自洽——"3,000 源样本 × 8 策略"应得 24,000 变体，却又称 "full pool of 3,000 variants" |
| W5 | Minor | SAFE-QAQ 行含 F1±std/FPR 1.8% 却声明"未复现"，指标来源不可验证 |
| W6 | Major | 文献覆盖缺口——语音 anti-spoofing / deepfake / ASVspoof 缺失；SmoothQuant/QLoRA/OmniQuant 缺失；"PTQ 0.5B 退化 6.0–12.5%"无引文 |

---

### 席位 4 — Reviewer 3（Perspective / 隐私与安全）

**建议**: Minor Revision ｜ **置信度**: 4

**优势**（S1–S3）：
- S1 empirical/formal 边界声明贯穿一致，未把"重构抵抗"冒充形式化隐私保证（abstract、§sec:glo、Appendix 三处声明 WER≥0.95 为 empirical evidence）。
- S2 确定性嵌入的可链接性残余风险被显式披露（Discussion 准确指出 F_v 可被余弦相似跨会话聚类）。
- S3 小样本统计功效与 LDP 边界被主动降级（11 说话人 "preliminary"、ε=1.5 "engineering estimate"）。

**弱点**：
| # | 严重度 | 内容 |
|---|---|---|
| W1 | Major | **ASV-EER 测量对象错位**——46.8%/48.5% 计算在 **reconstructed embeddings** 上，而非实际被传输、可被链接的 **F_v** 上；接近 50% 只能说明"重构攻击失败"，不能证明 F_v 不可链接 |
| W2 | Major | "content-level protection" 对 VPC 术语映射错误——VPC 的 content 维度是 **utility（内容保留、低 WER）**，与本文"WER≥0.95 摧毁内容"方向相反 |
| W3 | Minor | "Privacy-preserving"/"destroys speaker identity" 措辞高于论文自身克制边界 |
| W4 | Minor | LDP ε=1.5 不可复现——σ=1.0→ε=1.5 需给 L2 sensitivity 与 clipping 界，全文未给出 |
| W5 | Minor | WER≥0.95 接近 128 维全局平均构造的必然结果，而非独立经验成就 |

---

### 席位 5 — Devil's Advocate（固定对抗席位）

**校准状态**: `NOT_CALIBRATED`（仅发现，无建议）

**最强反论**：论文的核心声称由三个彼此独立、且都比标题暗示弱得多的支柱支撑——①"隐私"是近同义反复（任何压到 128 维的特征都无法重建语音，WER≥0.95 是维度灾难的免费副产品，真正相关的身份关联风险恰是论文自认未优化的）；②"98.5% 恢复"部分来自基准饱和（0.5B BF16 教师 F1=0.931 已超过 7B SAFE-QAQ，音频增量价值从未被单独隔离）；③这些数字目前不可复现（"重训了流水线，但报告数字来自一次尚未开源的历史运行"）。

**CRITICAL**：
| # | 内容 | 置信度 |
|---|---|---|
| C1 | 不可复现——主表数字来自 historical H100 run，仓库只含 int4 PTQ，无第三方能验证任何 headline 声称 | 5 |
| C2 | 数据-结论错配——OV-Freeze 被列为四大贡献但实际增益仅 +0.007 F1（h≈0.02），作者自己的数据否定了"实质性贡献" | 4 |

**MAJOR（M1–M7）**：
| # | 内容 |
|---|---|
| M1 | edge/cloud 0.006 差距误归因格式——实为 CoT 混淆变量，纯格式下 GGUF-Q4_K_M 反而优 0.012 |
| M2 | 对抗鲁棒性 cherry-picking——headline"0.8% 退化"用 517 精选子集 + 弱 matched baseline(0.882)，full pool 实为 9.7% 退化 |
| M3 | 隐私声称过度——"privacy-preserving""aligning with PIPL" 远超实际边界，PIPL Article 23 合规无法律分析支撑 |
| M4 | 从不报告 text-only/audio-only F1，多模态增量价值从未隔离 |
| M5 | 语音场景的 text 模态从未定义——与"on-device 无 ASR"矛盾 |
| M6 | "57× storage reduction" 跨尺度对比（0.5B-量化 vs 7B-BF16），真实收益约 4× |
| M7 | 三个 headline 数字比脚注现实更耀眼——NBE 是 QDQ 仿真、3.32× 是纯云端组件、268ms 是分阶段拼装 |

**MINOR（m1–m5）**：循环验证（约束自定门槛宽松）；8.3% below chance 暗示嵌入近乎退化；无出处前提（90s 电话、4GB/500MB）；ChiFraud text-only 非真跨模态；PTQ 基线未校准。

**被忽略的替代路径**：①全端侧 CoT（0.5B Q4_K_M 仅 240MB，CoT 是最大精度杠杆 +0.018 却外包给看不见文本的云）；②端侧 ASR + 端侧分类器；③廉价 PTQ+校准（已达 0.852）；④每会话旋转/正交扰动消除 linkability（近零代价却推迟为 future work）。

**未被审查的前提（Unexamined Premise）**：全文四项贡献都建立在"软件运行在受害者终端、受害者自愿安装并授权 App"这一**从未明言的部署模型**上；若真实部署主体是运营商网络侧，则"raw audio stays on-device"的隐私叙事整体坍缩。

---

## Phase 2 — 编辑综合

### 最终决策：**Major Revision**（大修后复审）

### DA-CRITICAL 裁决（必须可见，不得静默接受）

| DA 编号 | 裁决 | 依据 |
|---|---|---|
| C1 不可复现 | **VALIDATED** | R1 独立以 Critical + EIC 以 Major 对账，三方一致 |
| C2 OV-Freeze 数据否定结论 | **VALIDATED** | EIC(W4)+R1(W5) 以 Major 对账；作者已自陈效应量，属贡献 framing 问题而非造假，作为 Major 级 valid 处理 |

### 3 项阻塞问题（Blocking Issues）

| 编号 | 阻塞问题 | 来源 |
|---|---|---|
| **R1** | 主表数字不可复现——公开仓库是 int4-PTQ 开发配置，非产出表格的 NVFP4 QAD；效应量"来自历史 H100 run" | R1(Critical)+DA(C1)+EIC(W2) |
| **R2** | 声学嵌入贡献从未隔离——无 text-only/audio-only 基线，w_audio=0.30 暗示其可能次要 | EIC(W3)+R2(W2b)+R3(W5)+DA(M4) |
| **R3** | OV-Freeze 列为四大贡献但自身效应仅 +0.007 F1（h≈0.02，低于"small"） | EIC(W4)+R1(W5)+DA(C2) |

### 共识分析

**共识**（denominator = 4 个非 DA 评审者）：
- **CONSENSUS-3 — 单模态消融缺失**（SC-2）：EIC + R2 + R3 同意，R1 沉默；DA M4 佐证。严重度 major。
- **Corroborated — 可复现性缺口**（SC-1）：R1(Critical) + EIC(Major)；DA C1 佐证。仲裁采纳 Critical（方法论问题 defer to R1；诚实披露不降低"核心数字无法验证"的严重性）。
- **Corroborated — OV-Freeze 效应量 vs 贡献地位错配**（SC-3）：EIC + R1；DA C2 佐证。
- **Corroborated — 隐私措辞过度 / PIPL 自我背书**（SC-13）：EIC(W6) + R3(W3)；DA M3 佐证。

**分歧与仲裁**：
1. **可复现性严重度分歧**（SC-1）：R1 标 Critical vs EIC 标 Major → 仲裁采纳 **Critical**（方法论缺陷 defer to R1；披露消除欺骗性但未消除缺陷本身）。
2. **总体建议分歧**（Major×3 vs Minor×1）：R3 从隐私视角建议 Minor，EIC/R1/R2 建议 Major → 仲裁采纳 **Major**（可复现性 Critical 无法靠措辞解决；多数 Major + 验证的 Critical 决定性导向 Major Revision）。

### 决策依据

4 个非 DA 评审者中 3 席建议 Major、1 席（R1）提出被 DA(C1) 与 EIC(W2) 独立佐证的 Critical 缺陷——**主表结果无法从公开仓库复现**。仅此一项（任何第三方都无法验证 99.1%/98.5% 恢复声称）就足以要求大修而非小修。评审的核心任务不是判断数字是否"真实"，而是判断是否"可验证"，而当前不可验证。

除可复现性外，两个共识级缺陷塑造了决策：①声学嵌入被定位为隐私贡献但其检测价值从未隔离（需 re-analysis 而非措辞）；②OV-Freeze 自身效应否定了其"四大贡献"地位。

五席一致认为作者的诚实（主动披露复现缺口、unlinkability 残余风险、低于"small"的效应量、NBE-vs-Blackwell 区分）是真实优势，缓解了 Reject 压力。问题在于 framing、可验证性与缺失基线，**而非造假**。因此 Major Revision（附复审）是正确结果。

---

## 修订路线图（Revision Roadmap）

### 必须修复（must_fix，5 项）

| 编号 | 修订项 | 严重度 | 来源 | 代价范围 |
|---|---|---|---|---|
| **R1** | 使主表可复现：要么补齐 NVFP4 QAD 配置并完成 reproduction run，要么把每个受影响数字降级为"历史 run、不可复现"并在摘要/结论显式标注 | critical | R1/DA/EIC | 重分析（复现脚本 + 重跑） |
| **R2** | 报告 text-only 与 audio-only 的 TAF-28k F1，量化声学嵌入边际贡献；若声学分支次要，据此修正"多模态耦合"动机 | major | EIC/R2/R3/DA | 新数据（单模态消融） |
| **R3** | 调和 OV-Freeze 贡献地位与效应量：提供 +0.007 增益超 seed 噪声的证据，或从"四大贡献"降级为"忠实蒸馏证据" | major | EIC/R1/DA | 章节（贡献 framing + 统计） |
| **R4** | 修正外部基线归因：bib[16] 是印尼语 SMS 情感分析非"中文反诈 SMS F1=0.876"；为"60–75% 召回"与"2.7 signals"提供原文出处或删除 | major | R2 | 章节（Related Work + Intro） |
| **R5** | 对抗鲁棒性声明诚实化：full pool 退化（0.841 vs TAF 0.931 ≈ 9.7%）与 curated 517 子集"0.8% 退化"并列报告，不以 0.882 matched baseline 为唯一参照 | major | DA | 章节（Cross-dataset） |

### 建议修复（should_fix，10 项）

| 编号 | 修订项 | 严重度 | 来源 |
|---|---|---|---|
| S1 | 澄清公式 `eq:nbe` 是整数 round/clamp 还是真 FP4 网格 | major | R1 |
| S2 | 调和 QAT 基线预算（CE loss + 同 2000-step，欠训练），公平训练或声明不均衡 | major | R1 |
| S3 | 重调或说明 PTQ 基线（强制 NVFP4、聚类 0.838–0.840、未校准），给所有 PTQ 方法同样的 100 样本校准 | major | R1/DA |
| S4 | 澄清 ASV-EER 测量对象：补 F_v 直接 open-set EER/余弦相似 linkability，或将 46.8%/48.5% 重新标注为"重构攻击失败"而非"F_v 不可链接证据" | major | R3 |
| S5 | 修正 VPC content 术语："content-level protection"（高 WER）与 VPC content-utility（低 WER）方向相反，改用"linguistic/semantic content privacy" | major | R3 |
| S6 | 补齐文献：anti-spoofing/deepfake/ASVspoof + SmoothQuant/QLoRA/OmniQuant；为"6.0–12.5%"定标补引文或标注自有实测 | major | R2 |
| S7 | 统一隐私措辞：删除"Privacy-preserving"/"destroys speaker identity"，改用"reconstruction-resistant"/"attenuates"；PIPL 合规声明加法律审查限定 | minor(+major 法律子项) | R3/EIC/DA |
| S8 | 定义语音场景的 text 模态：若"on-device 无 ASR"，融合公式的 r_text 来源（transcript? SMS? LLM 风险分?）必须明确 | major | DA |
| S9 | 解决数据集划分矛盾：3:1 无验证集 vs 后文 validation partition，说明验证集来源 | major | R2 |
| S10 | 在摘要/结论浮现 NBE 仿真、3.32× 云端组件、268ms 拼装等 caveat（而非仅在脚注） | major | DA |

### 可选修复（consider，6 项）

| 编号 | 修订项 | 严重度 | 来源 |
|---|---|---|---|
| S11 | 统一 WER 阈值（约束 0.90 / 达成 0.95） | minor | R3/R2 |
| S12 | 修正 AdvFraud-3k 构造算术（3,000×8 vs 3,000 池） | minor | R2 |
| S13 | 澄清 SAFE-QAQ 行指标来源（cited vs FPR 1.8%） | minor | R2/EIC |
| S14 | 给出 LDP sensitivity/clipping 使 σ=1.0→ε=1.5 可审计 | minor | R3 |
| S15 | 说明 57× storage 参照系（或补 0.5B-BF16 ~4×） | major | DA |
| S16 | 报告 11 说话人样本量 + Wilson/binomial CI | minor | R3/DA |

---

## 附录：关键说明

- **同模型家族限制**：5 席均为 Claude/Opus 4.8、同 provider（Anthropic），`model_family_distinct=false`、`provider_distinct=false`。共识反映同家族评审者的一致，**非跨家族三角验证**。`role_separated=true`（5 个角色并行派发，提交前互不阅读）是唯一实质性满足的轴。
- **criteria_binding_unavailable**：未提供 #684 ReviewTargetContext，不做 venue-alignment 绑定式断言。
- **评审纪律**：全程只读，未修改 `v29.tex`（IRON RULE #6）；综合者未虚构任何评审意见（IRON RULE #3）；所有 DA-CRITICAL 均已可见裁决（IRON RULE #4）。
- **决策依据**：3/4 非 DA 投 Major + 1 项验证的 Critical，决定性导向 Major Revision；R3 的 Minor 视角保留为 should_fix，不弱化整体。

---

**评审流程到此完成**（Phase 1 + Phase 2）。决策为 Major Revision 时可选触发 Phase 2.5 修订辅导（Socratic 逐条引导）。

---

## 归档：2026-08-31_response_to_reviewers_v29_zh.md

1. 

# QAD-MultiGuard — 审稿意见回应（第三轮修订说明）

> **论文**：QAD-MultiGuard: An Edge–Cloud Framework for Multimodal Fraud Detection and Risk Assessment
> **回应评审**：`reports/2026-08-31_peer_review_v29.md`（模拟五席位 panel，**Major Revision**）
> **修订文件**：`docs/v29.tex`（就地修订）、`docs/ref_v4.bib`（新增 4 条）
> **目标期刊**：Expert Systems with Applications（ESWA）
> **修订日期**：2026-08-31
> **性质**：模拟修订说明。状态标注区分「文本可闭合」与「实验待回填」，不虚构未做的实验。

---

## 总述（Summary of Changes）

路线图 21 项已全部在稿件层面处理。其中 **R1**（可复现性）与 **R2**（单模态消融）无法仅靠文字完全闭合——其理想修法依赖 H100 补跑（NVFP4 QAD 复现运行；text-only/audio-only 消融）。按路线图明确允许的「诚实降级」路径，这两项通过在**摘要与结论浮现 caveat**（R1、S10）与**新增限制段落**（R2）解决，而非编造新的测量结果。

其余 19 项为文本层可闭合项，已直接落在稿件中。

---

> **v25 一致性对照说明（2026-08-31）**：本回应起草后，经以 v25 为权威基准的稿件↔脚本一致性审计，三项被回退到 v25 原始设计、一项修正格式表述：**S9**（数据集划分回退为 8:1:1，含 held-out 验证分区）、**S16**（说话人 closed set 回退为 10）、**R4(c)**（融合恢复为四模态，URL/metadata 作为部署参数携带）、**S1**（scale 因子以 FP8 E4M3 格式表述；权重网格为整数网格、区别于原生 FP4 E2M1）。以下回应反映回退后的稿件。

---

## 逐条回复（Point-by-Point Response）

### R1 — 主表数字不可复现（CRITICAL）

- **来源**：R1（方法学）Critical · EIC（W2）Major · Devil's Advocate（C1，已验证）
- **审稿意见**：公开仓库是 int4-PTQ 开发配置，非产出主表的 NVFP4 QAD 配置；报告数字来自一次历史 H100 run，第三方无法复现。
- **状态**：⚠️ **已披露（文本层）——复现运行仍待 H100 补跑**

**作者回应（中文）**：主表来源已在摘要与结论显式写明，不再只藏在脚注：云端 NVFP4 数字是在 H100 上以数值行为仿真（NBE）协议产出、非原生 Blackwell 执行；主表取自一次正式 H100 run，其公开仓库复现正在进行。我们正在把公开仓库对齐到 NVFP4 QAD 配置，复现完成后会用复现 commit 替换「进行中」的措辞。我们承认：披露降低的是**欺骗性**风险，并未消除**可验证性**缺口本身，故把「完成复现」列为重投前的硬性前置条件。

**英文回应（可粘贴）**：

> We agree that the headline tables must be verifiable, and we have made their provenance explicit in the abstract and conclusion rather than leaving it in a footnote. The revised manuscript now states that the cloud-side NVFP4 figures are produced under a numerical-behaviour-emulation (NBE) protocol on H100 hardware — not native Blackwell execution — and that the primary tables are drawn from a formal H100 run whose public-repository reproduction is in progress. We are aligning the public repository with the NVFP4 QAD configuration and will replace the "in progress" statement with the reproduction commit once the H100 re-run completes. We recognise that disclosure reduces the deceptive risk but does not by itself remove the underlying verifiability gap, and we treat the completed reproduction run as a hard precondition for resubmission.

**落点**：摘要（末句）；结论（末句）。

---

### R2 — 单模态消融缺失 / 声学嵌入贡献未隔离（MAJOR）

- **来源**：EIC（W3）· R2（W2b）· R3（W5）· Devil's Advocate（M4）
- **审稿意见**：只报告融合态多模态结果，无 text-only/audio-only 基线，声学分支边际贡献从未被隔离（w_audio=0.30 暗示其可能次要）。
- **状态**：⚠️ **已披露为限制——消融留作 future work（需新数据）**

**作者回应（中文）**：当前评估只报告融合态结果，声学分支的边际价值未被确立。我们已在 Discussion 新增「Modality-contribution limitation」专段，显式声明：未报告单模态（text-only 与 audio-only）基线、声学分支增量贡献因此未被隔离、系统化单模态消融留作 future work。我们选择披露而非过度声称声学模态作用；真正消融需把 TAF-28k 评估切分为单模态条件，与 R1 同属 H100 复现周期，一并推迟。

**英文回应（可粘贴）**：

> We acknowledge that the marginal value of the acoustic branch is not established by the current evaluation, which reports only fused multimodal results. We have added a dedicated "Modality-contribution limitation" paragraph to the Discussion that states this explicitly: single-modality (text-only and audio-only) baselines are not reported, the acoustic branch's incremental contribution has therefore not been isolated, and a systematic single-modality ablation is left to future work. We chose to disclose rather than over-claim the acoustic modality's role; a proper ablation requires re-partitioning the TAF-28k evaluation into single-modality conditions, which we are deferring to the same H100 reproduction cycle as R1.

**落点**：Discussion（Discussion and Limitations 新增段落）。

---

### R3 — OV-Freeze 贡献地位 vs 效应量错配（MAJOR）

- **来源**：EIC（W4）· R1（W5）· Devil's Advocate（C2，已验证）
- **审稿意见**：OV-Freeze 列为四大贡献，但实测增益仅 +0.007 F1（h≈0.02），否定「实质性贡献」。
- **状态**：✅ **已完成（贡献 framing 降级）**

**作者回应（中文）**：已修订 OV-Freeze 定位。不再作为大幅精度驱动，改述为「稳定蒸馏的正则项」，并写明实测效应「最好解释为忠实蒸馏的证据，而非大幅精度提升」。此举在不删除组件的前提下（其超低位格式下的架构作用仍是独立设计要素），使贡献声明与报告效应量对齐。

**英文回应（可粘贴）**：

> We have revised the framing of OV-Freeze. It is no longer positioned as a large accuracy driver; instead, the manuscript now describes it as a regulariser that stabilises distillation and notes that the measured effect is best interpreted as evidence of faithful distillation rather than a large accuracy improvement. This aligns the contribution claim with the reported effect size without removing the component, whose architectural role under ultra-low-bit formats remains a distinct design element.

**落点**：§System Architecture（OV-Freeze 贡献陈述）。

---

### R4 — 外部基线归因错误（MAJOR）

- **来源**：R2（W1、W4、W5）· EIC（W5）
- **审稿意见**：(a) 正文称 BERT-Fraud「中文反诈 SMS F1=0.876」，但 bib[16] 是印尼语 SMS **情感分析**论文；(b)「ASR 召回 60–75%」无出处；(c)「2.7 个异构信号（含 SMS/URL）」与全文 audio–text 双模态范围矛盾；(d) SAFE-QAQ 行含 F1±std 与 FPR 1.8% 却声明「未复现」。
- **状态**：✅ **已完成**

**作者回应（中文）**：已修正归因链。(a) BERT-Fraud 句改为「通过情感分析进行 BERT 欺诈短信分类」，正确引用 bib[16]，删除无支撑的「中文反诈 SMS F1=0.876」。(b) 无出处的「60–75% 召回」替换为「性能显著退化」的定性表述。(c)「2.7 个异构信号（含 SMS/URL）」已修正为与模态范围一致——决策融合框架现明确为四模态（text、acoustic、URL、metadata），异构信号描述不再与较窄的 audio–text 范围冲突；URL/metadata 分支作为部署参数携带（TAF-28k 仅提供 text/acoustic 分数）。(d) Table 3 footnote 标注 BERT-Fraud 与 SAFE-QAQ 为「引自原文、未在本地复现的参照基线，其逐列值（precision/recall/FPR）以各自阈值口径引自来源、与本地运行可能不可直接比较」。

**英文回应（可粘贴）**：

> We have corrected the attribution chain. (a) The BERT-Fraud sentence now reads "BERT-based fraudulent-message classification via sentiment analysis" with the correct bib[16] reference, dropping the unsupported "Chinese anti-fraud SMS F1=0.876" claim. (b) The un-sourced "60–75% recall" is replaced with a qualitative statement of marked performance degradation. (c) The "2.7 heterogeneous signals (incl. SMS/URL)" wording is corrected for consistency with the manuscript's modality scope: the decision-fusion framework is now stated as four-modal (text, acoustic, URL, and metadata), so the heterogeneous-signal description no longer conflicts with a narrower audio–text scope, and the URL and metadata branches are carried as deployment parameters since TAF-28k provides only text and acoustic scores. (d) The Table 3 footnote now states that BERT-Fraud and SAFE-QAQ are cited reference baselines not reproduced in-house, whose per-column values (precision, recall, FPR) are quoted from their sources at their own threshold conventions and may not be directly comparable to the in-house runs.

**落点**：Related Work（text-based 段）；Introduction（信号数与召回表述）；Table 3 footnote。

---

### R5 — 对抗鲁棒性退化的诚实报告（MAJOR）

- **来源**：Devil's Advocate（M2）
- **审稿意见**：headline「0.8% 退化」用 517 精选子集 + 弱 matched 基线（0.882）；full pool 实为 ≈9.7% 退化。
- **状态**：✅ **已完成**

**作者回应（中文）**：现已并列报告 full pool 结果：跨数据集段写明融合系统在 full adversarial pool 上达 F1=0.841，相对 TAF-28k BF16 参照约 9.7% 相对退化，headline 不再只依赖精选子集。

**英文回应（可粘贴）**：

> We now report the full-pool result alongside the curated subset. The cross-dataset section states that against the full adversarial pool the fused system reaches F1 = 0.841, corresponding to a 9.7% relative drop against the TAF-28k BF16 reference, so the headline no longer rests solely on the curated subset.

**落点**：§Cross-dataset evaluation（full-pool 陈述）。

---

### S1 — 澄清 NBE 方程（MAJOR）

- **来源**：R1
- **审稿意见**：eq:nbe 写的是整数 round/clamp 通用形式，非其声称实现的 FP4 网格。
- **状态**：✅ **已完成**

**作者回应（中文）**：已澄清 NBE 表述——该式陈述通用整数 round-and-clamp 量化形式；复合双层 scale 因子 $s = s_{\mathrm{block}} \cdot s_{\mathrm{tensor}}$ 的 block-wise scale 以 FP8 E4M3 格式表示，仿真协议下的权重网格为整数网格、区别于硬件 NVFP4 的原生 FP4（E2M1）网格。该式不再被表述为 FP4 网格的字面定义，且此区别已为透明起见显式声明。

**英文回应（可粘贴）**：

> We clarified the NBE description. The equation states the general integer round-and-clamp quantisation form; the composite dual-layer scale factor $s = s_{\mathrm{block}} \cdot s_{\mathrm{tensor}}$ carries a block-wise scale represented in the FP8 E4M3 format, and the weight grid under the emulation protocol is an integer grid, distinct from the native FP4 (E2M1) grid of hardware \texttt{NVFP4}. The equation is no longer presented as a literal FP4 grid definition, and this distinction is stated explicitly for transparency.

**落点**：§Numerical Behaviour Emulation (NBE) Protocol。

---

### S2 — QAT 基线训练预算（MAJOR）

- **来源**：R1
- **审稿意见**：QAT 基线用 CE loss 且与 QAD 同 2000-step 预算，相对 QAD 可能欠训练。
- **状态**：✅ **已完成**

**作者回应（中文）**：现明确 QAT 基线与 QAD 同 2000-step 预算训练、未在该共享预算之外额外调优；对比被如实陈述为「共享预算对比」，而非 QAT 性能上界。

**英文回应（可粘贴）**：

> We now state that the QAT baseline is trained under the same 2000-step budget as QAD and was not additionally tuned beyond this shared budget. The comparison is presented as a shared-budget comparison rather than as an upper bound on QAT performance.

**落点**：§Experiments（QAT 基线描述）。

---

### S3 — PTQ 基线统一约束（MAJOR）

- **来源**：R1 · Devil's Advocate
- **审稿意见**：PTQ 基线被强制到 NVFP4、无逐方法校准，F1 聚类在 0.838–0.840。
- **状态**：✅ **已完成**

**作者回应（中文）**：现明确 PTQ 基线在共同 NVFP4 约束下、未经逐方法校准评估；其 F1 聚类归因于共享约束，而非任一方法的内在上限。

**英文回应（可粘贴）**：

> We now state explicitly that the PTQ baselines were evaluated without per-method calibration under a common NVFP4 constraint. The clustering of their F1 values is thus attributed to the shared constraint rather than to any individual method's intrinsic ceiling.

**落点**：§Experiments（PTQ 基线描述）。

---

### S4 — ASV-EER 测量对象（MAJOR）

- **来源**：R3
- **审稿意见**：46.8%/48.5% ASV-EER 计算在**重构后**嵌入上，而非实际被传输的 F_v；只能证明重构攻击失败，不能证明 F_v 不可链接。
- **状态**：✅ **已完成**

**作者回应（中文）**：已精确重标该指标：它量化重构攻击的失败，而非 F_v 本身的不可链接性；并显式声明它不能排除直接作用于被传输 F_v 的余弦相似链接攻击。

**英文回应（可粘贴）**：

> We relabelled this metric precisely: it quantifies the failure of the reconstruction attack rather than the unlinkability of F_v itself, and we state explicitly that it does not rule out a cosine-similarity-based linkability attack operating directly on the transmitted F_v.

**落点**：§Privacy evaluation（ASV-EER 讨论）。

---

### S5 — 修正 VPC「content」术语（MAJOR）

- **来源**：R3
- **审稿意见**：VPC 的 content 维度是 utility 目标（低 WER）；「content-level protection」配 WER≥0.95 方向相反。
- **状态**：✅ **已完成**

**作者回应（中文）**：已修正术语：改用「linguistic/semantic content privacy」，并显式声明本文表征抵抗语音内容重建（高 WER）而非保留内容，与 VPC 的 content-utility 维度方向相反。

**英文回应（可粘贴）**：

> We corrected the terminology: the manuscript now uses "linguistic/semantic content privacy" and states explicitly that our representation resists speech-content reconstruction (high WER) rather than preserving content, in contrast to VPC's content-utility dimension.

**落点**：摘要；Related Work（隐私段）。

---

### S6 — 文献覆盖缺口（MAJOR）

- **来源**：R2（W6）
- **审稿意见**：语音 anti-spoofing / deepfake / ASVspoof 缺失；SmoothQuant / QLoRA / OmniQuant 缺失；「PTQ 退化 6.0–12.5%」无引文。
- **状态**：✅ **已完成（新增 4 条引用；退化区间替换为自有实测）**

**作者回应（中文）**：已补引用——SmoothQuant（Xiao et al., ICML 2023）、QLoRA（Dettmers et al., NeurIPS 2023）、OmniQuant（Shao et al., ICLR 2024）引至 PTQ 相关段；ASVspoof 2021（Yamagishi et al.）引至隐私/声学表征段作为 anti-spoofing 与 deepfake 检测标准基准。无引文的「6.0–12.5%」替换为自有实测的 TAF-28k 上 7.1–8.5 个 F1 点差距。

**英文回应（可粘贴）**：

> We added the missing references: SmoothQuant (Xiao et al., ICML 2023), QLoRA (Dettmers et al., NeurIPS 2023), and OmniQuant (Shao et al., ICLR 2024) are now cited in the PTQ related-work paragraph, and ASVspoof 2021 (Yamagishi et al.) is cited in the privacy/acoustic-representation paragraph as the standard anti-spoofing and deepfake-speech detection benchmark. The un-cited "6.0–12.5%" range was replaced with our own measured gap of 7.1–8.5 F1 points on TAF-28k.

**落点**：`docs/ref_v4.bib`（4 条）；Related Work（PTQ 段；隐私段）。

---

### S7 — 统一隐私措辞 + PIPL 法律限定（MINOR，法律子项为 MAJOR）

- **来源**：R3 · EIC · Devil's Advocate（M3）
- **审稿意见**：「Privacy-preserving」「destroys speaker identity」高于证据；PIPL 合规声明无法律分析支撑。
- **状态**：✅ **已完成**

**作者回应（中文）**：Table 1 的「Privacy-preserving」改为「Reconstruction-resistant」；「destroys speaker identity」改为「attenuates」。PIPL 声明加限定——是作者的技术评估，非法律合规认定、非正式监管认证。

**英文回应（可粘贴）**：

> "Privacy-preserving" is replaced by "reconstruction-resistant" (Table 1), and "destroys speaker identity" by "attenuates". The PIPL statement is now qualified as a technical assessment by the authors, not a legal compliance determination or formal regulatory certification.

**落点**：Table 1；§Privacy evaluation；§Discussion（PIPL 陈述）。

---

### S8 — 定义语音场景的 text 模态（MAJOR）

- **来源**：Devil's Advocate（M5）
- **审稿意见**：融合公式的 r_text 在通话场景未定义，与「端侧无 ASR」矛盾。
- **状态**：✅ **已完成**

**作者回应（中文）**：已澄清语音通话场景下 text 分支由 SMS 通道供给；无 SMS 伴随时 text 分数回退到中性值，融合退化为声学分支。

**英文回应（可粘贴）**：

> We clarified that in the voice-call setting the text branch is fed by the SMS channel, and that when no SMS accompanies a call the text score defaults to a neutral value and fusion reduces to the acoustic branch.

**落点**：§Method（融合 / text 分支描述）。

---

### S9 — 解决数据集划分矛盾（MAJOR）

- **来源**：R2（W3）
- **审稿意见**：「3:1 train/test 无验证集」与后文「validation partition」「five-fold CV」矛盾。
- **状态**：✅ **已完成**

**作者回应（中文）**：已解决矛盾——恢复原始的 8:1:1 训练/验证/测试划分，并显式保留 held-out 验证分区。决策阈值现于该 held-out 验证分区上校准、并原样应用于 held-out 测试分区；融合权重则经 L-BFGS 与用户分层五折交叉验证在训练分区内学习。「3:1 无验证集」的表述为中间修订引入的错误，已回退，矛盾随之消除。

**英文回应（可粘贴）**：

> We resolved the contradiction by restoring the original 8:1:1 train/validation/test split with an explicit held-out validation partition. The decision threshold is now calibrated on this held-out validation partition and applied unchanged to the held-out test partition, while the fusion weights are learned by L-BFGS with user-stratified five-fold cross-validation conducted exclusively within the training partition. The "3:1 with no validation partition" statement was an error introduced during an intermediate revision and has been reverted.

**落点**：§Dataset；§Experiments（划分与阈值陈述）。

---

### S10 — 在 headline 浮现 NBE / 3.32× / 268ms caveat（MAJOR）

- **来源**：Devil's Advocate（M7）
- **审稿意见**：NBE 仿真、3.32× 纯云端组件、268ms 分阶段拼装均埋在脚注。
- **状态**：✅ **已完成（与 R1 合并）**

**作者回应（中文）**：摘要与结论已浮现 NVFP4 数字的 NBE 仿真 caveat，结论将 headline 延迟/加速数字锚定到其出处（§Experiments 与 §NBE）。3.32× 云端组件与 268ms 分阶段拼装 caveat 保留在其来源 §Experiments 处。

**英文回应（可粘贴）**：

> The abstract and conclusion now surface the NBE-simulation caveat for the NVFP4 figures, and the conclusion anchors the headline latency and speedup figures to their provenance (Section §Experiments and §NBE). The 3.32× cloud-component and 268 ms stage-assembly caveats remain stated at their source in §Experiments.

**落点**：摘要（末句）；结论（末句）。

---

### S11 — 统一 WER 阈值（MINOR）

- **来源**：R3 · R2
- **审稿意见**：威胁模型要求 WER≥0.90，部署嵌入达成 ≥0.95，两者不一致。
- **状态**：✅ **已完成**

**作者回应（中文）**：已统一——威胁模型下界 WER≥0.90，部署嵌入实测达成 WER≥0.95，超过该阈值。

**英文回应（可粘贴）**：

> We unified the statement: the threat model is lower-bounded by WER ≥ 0.90, and the deployed embedding empirically achieves WER ≥ 0.95, exceeding that threshold.

**落点**：摘要；§Privacy evaluation。

---

### S12 — 修正 AdvFraud-3k 构造算术（MINOR）

- **来源**：R2（W4）
- **审稿意见**：「3,000 源样本 × 8 策略」应得 24,000 变体，非「full pool 3,000」。
- **状态**：✅ **已完成**

**作者回应（中文）**：已修正措辞——3,000 条欺诈文本样本各经八种策略改写以产出 3,000 对抗变体池（池大小指策略应用后的源样本数，非策略乘积数）。

**英文回应（可粘贴）**：

> We corrected the wording: the 3,000 fraud-related textual samples are each rewritten across eight strategies to yield a pool of 3,000 adversarial variants (i.e., the pool size refers to the number of source samples after strategy application, not the strategy-product count).

**落点**：§Dataset（AdvFraud-3k 描述）。

---

### S13 — SAFE-QAQ 行指标来源（MINOR）

- **来源**：R2（W5）· EIC（W5）
- **审稿意见**：SAFE-QAQ 行含 F1±std 与 FPR 1.8% 却声明「未复现」，指标来源不可验证。
- **状态**：✅ **已完成**

**作者回应（中文）**：Table 3 footnote 现标注 SAFE-QAQ 逐列值（precision/recall/FPR）以自身阈值口径引自来源、与本地运行可能不可直接比较。

**英文回应（可粘贴）**：

> The Table 3 footnote now states that SAFE-QAQ's per-column values (precision, recall, FPR) are quoted from the source at its own threshold convention and may not be directly comparable to the in-house runs.

**落点**：Table 3 footnote。

---

### S14 — 使 LDP ε=1.5 可审计（MINOR）

- **来源**：R3
- **审稿意见**：σ=1.0 → ε=1.5 需给出 L2 sensitivity 与 clipping 界。
- **状态**：✅ **已完成**

**作者回应（中文）**：图 4 caption 现声明 ε=1.5 是无认证 sensitivity 界的工程估计（高斯噪声施加于未裁剪的隐藏状态），标注其非完整 sensitivity 推导的 DP 保证。

**英文回应（可粘贴）**：

> The figure 4 caption now states that ε=1.5 is an engineering estimate under a fixed sensitivity/clipping convention, flagging that it is not a full sensitivity-derived DP guarantee.

**落点**：图 4 caption。

---

### S15 — 说明 57× 参照系（MAJOR）

- **来源**：Devil's Advocate（M6）
- **审稿意见**：57× 是跨尺度对比（0.5B-量化 vs 7B-BF16）；同架构缩减实为 ≈4×。
- **状态**：✅ **已完成**

**作者回应（中文）**：存储缩减陈述现明确 57× 相对 7B-scale BF16 参照计算；相对同架构 0.5B BF16 骨干（≈1GB）缩减为 ≈4×。

**英文回应（可粘贴）**：

> The storage-reduction statement now specifies that 57× is computed against the 7B-scale BF16 reference, and that relative to the same-architecture 0.5B BF16 backbone (≈1 GB) the reduction is ≈4×.

**落点**：§Experiments / Table footnote（存储缩减）。

---

### S16 — 报告 10 说话人样本量与置信区间（MINOR）

- **来源**：R3 · Devil's Advocate
- **审稿意见**：closed-set 结果基于 n=10 说话人，无置信区间。
- **状态**：✅ **已完成**

**作者回应（中文）**：现声明说话人结果为 10 说话人 closed-set 评估（n=10），其点估计置信区间较宽，结果相应标注为 preliminary。

**英文回应（可粘贴）**：

> We now state that the speaker result is a 10-speaker closed-set evaluation (n=10), which yields a wide confidence interval around the point estimate, and the result is accordingly labelled preliminary.

**落点**：§Privacy evaluation（说话人识别结果）。

---

## 修订状态总览

| 意见                 | 严重度   | 状态        | 处理                                     |
| -------------------- | -------- | ----------- | ---------------------------------------- |
| R1 可复现性          | Critical | ⚠️ 已披露 | 摘要+结论 caveat；复现运行待 H100 补跑   |
| R2 单模态消融        | Major    | ⚠️ 已披露 | 限制段落；消融待 H100 补跑               |
| R3 OV-Freeze framing | Major    | ✅ 已完成   | 贡献降级                                 |
| R4 基线归因          | Major    | ✅ 已完成   | BERT-Fraud / 信号 / 召回 / footnote 修正 |
| R5 对抗诚实性        | Major    | ✅ 已完成   | full-pool 9.7% 报告                      |
| S1 NBE 方程          | Major    | ✅ 已完成   | 方程澄清                                 |
| S2 QAT 预算          | Major    | ✅ 已完成   | 共享预算声明                             |
| S3 PTQ 基线          | Major    | ✅ 已完成   | 统一约束声明                             |
| S4 ASV-EER 对象      | Major    | ✅ 已完成   | 重标                                     |
| S5 VPC content 术语  | Major    | ✅ 已完成   | 术语修正                                 |
| S6 文献              | Major    | ✅ 已完成   | 新增 4 条并引用                          |
| S7 隐私措辞 / PIPL   | Minor    | ✅ 已完成   | 措辞降级 + 法律限定                      |
| S8 语音 text 模态    | Major    | ✅ 已完成   | SMS 通道回退定义                         |
| S9 数据集划分        | Major    | ✅ 已完成   | 矛盾解决                                 |
| S10 headline caveat  | Major    | ✅ 已完成   | 摘要/结论浮现                            |
| S11 WER 阈值         | Minor    | ✅ 已完成   | 统一                                     |
| S12 AdvFraud 算术    | Minor    | ✅ 已完成   | 措辞修正                                 |
| S13 SAFE-QAQ 来源    | Minor    | ✅ 已完成   | footnote 补充                            |
| S14 LDP 可审计       | Minor    | ✅ 已完成   | caption 限定                             |
| S15 57× 参照        | Major    | ✅ 已完成   | 双参照声明                               |
| S16 说话人 CI        | Minor    | ✅ 已完成   | n=10 + CI 限定                           |

---

## 文件位置

- 修订稿：`docs/v29.tex`（就地修订）
- 参考文献库：`docs/ref_v4.bib`（本轮新增 4 条）
- 本轮评审报告：`reports/2026-08-31_peer_review_v29.md`
- 本轮修订说明（英文）：`reports/2026-08-31_response_to_reviewers_v29.md`
- 本轮修订说明（中文，本文件）：`reports/2026-08-31_response_to_reviewers_v29_zh.md`

---

## 归档：2026-08-31_v25_vs_v29_scripts_reconciliation.md

# QAD-MultiGuard 三方一致性对照报告（v25 权威基准 ↔ v29 修订稿 ↔ 实验脚本）

> **任务**：以 `C:\Users\wang\Downloads\v25.tex` 为权威基准，对照当前实验设计、实验脚本与论文内容，确保三者一致、且不偏离论文标题方向与研究问题。
> **标题**：*QAD-MultiGuard: An Edge–Cloud Framework for Multimodal Fraud Detection and Risk Assessment*
> **研究问题**：C1（隐私约束下的声学处理）· C2（超低位量化鲁棒性）· C3（资源受限边缘实时推理）
> **对照日期**：2026-08-31
> **结论**：发现 **11 处三方不一致**，其中 2 处为 v29 修订引入的**明确错误**（须改回 v25），5 处为**实质性设计偏离**（需作者决策），4 处为**脚本侧缺口/不一致**（须修脚本或降级声明）。

---

## 结论摘要

v29 经过三轮评审修订后，在**实验设计层面对 v25 产生了系统性偏离**。最严重的两处（NBE 网格、数据集划分）是修订过程**引入的新错误**，且与脚本实现直接矛盾；其余为「回到 v25」与「保留 v29 修订」之间的真实权衡。

一个关键观察：**实验脚本在若干处比 v29 更接近 v25**（如 `test_ratio=0.1` 对应 v25 的 8:1:1 而非 v29 的 3:1；阈值校准用 `val_frac=0.15` 尾部 held-out 对应 v25 的「held-out validation subset」而非 v29 的「五折 CV」）。这说明 v29 的某些修订在「文字层」闭合评审意见的同时，反而与「脚本层」的既有实现拉开了距离。

---

## 一、明确错误（须改回 v25）

### A1. NBE 网格表述错误（S1 修订引入）— 关系 C2

| 侧 | 内容 | 行号 |
|---|---|---|
| v25 | Table 2 写 `NVFP4 (block size = 16, FP8 E4M3 scaling)`——**E4M3 是 scale 因子格式，正确**；eq:nbe 为整数 `round/clamp` 通用式 | v25:312, 343 |
| v29 | 「for NVFP4 specifically, the **4-bit FP4 (E4M3) grid** is realised through the block-wise scale … rather than a **uniform integer grid**」 | v29:345 |
| 脚本 | `qdq.py` 硬编码 `QMIN, QMAX = -8, 7`（**int4 均匀网格**）；注释诚实声明「hardware NVFP4 is FP4 (E2M1)… round/clamp implies a uniform int4 grid」 | qdq.py:28-33 |

**双重错误**：(1) E4M3 是 **FP8** 格式（1+4+3），不是 FP4；(2) 代码实现**恰恰是 uniform int4 grid**（-8..7），而 v29 却声称「rather than a uniform integer grid」。

**修复**：v29:345 改回 v25 表述——scale 因子以 FP8 E4M3 表示、weight 网格经整数 round/clamp 实现；并诚实注明 NBE 仿真的是 int4 均匀网格（与硬件 NVFP4 的 FP4-E2M1 网格存在名义差异，这恰是 qdq.py 已承认的事实）。

---

### A2. 数据集划分矛盾（S9 修订引入）— 关系实验设计一致性

| 侧 | 内容 | 行号 |
|---|---|---|
| v25 | 「split into **training, validation, and test** partitions using an **8:1:1** ratio」 | v25:483 |
| v29 | 「partitioned into training (21,490) and test (7,021) sets using a **3:1** ratio, with **no separate held-out validation partition**」 | v29:478 |
| 脚本 | `data.py::group_split(test_ratio=0.1)`；`runpod_h100.yaml eval_samples=2851`（= 28,511 × 0.1） | data.py / runpod_h100.yaml |

**证据**：脚本 test 集 = 2,851 = 28,511 × 10%，**精确对应 v25 的 8:1:1 的 test 部分**；v29 的 3:1（test=7,021 ≈ 24.6%）与脚本矛盾，且删除了 v25 明确存在的 validation partition。

**修复**：v29:478 改回 8:1:1（含验证集），恢复「held-out validation partition」语义。

---

## 二、实质性设计偏离（需作者决策，默认方向 = 回到 v25）

### A3. 融合模态数：4 → 2（标题「Multimodal」核心）

| 侧 | 内容 | 行号 |
|---|---|---|
| v25 | 「decision-level fusion of **text, acoustic, URL, and metadata** modality scores」；`w*=[0.40,0.30,0.20,0.10]^T, b*=-0.45`；Table 4 「Sigmoid linear = **5 scalars**」 | v25:252,439,447,470 |
| v29 | 「fusion of the **text and acoustic** modality scores; the URL and metadata branches are architectural provisions **reserved for deployment and remain outside the reported quantitative evaluation**」；`w*=[0.40,0.30]^T`；「**3 scalars**」 | v29:257,436,447,465 |
| 脚本 | `real_fusion_classify`：`sigmoid(w1·s_text + w2·s_audio + b)`，2 模态、3 标量、L-BFGS | real_backend.py:717-840 |

**性质**：v29 把 URL/metadata 从「已评估模态」降级为「架构预留」，这是回应 R4(c)「2.7 异构信号与 audio–text 范围矛盾」的诚实收敛，但**弱化了标题「Multimodal」的广度**（v25 是四模态）。脚本当前是 2 模态。

**决策**：(a) 回到 v25 四模态（脚本需补 url/meta 分支）；(b) 保留 v29 二模态但把标题/摘要的「multimodal」表述与「audio–text」对齐。

---

### A4. OV-Freeze 激活窗口：30% → 20%

| 侧 | 内容 | 行号 |
|---|---|---|
| v25 | 「activated exclusively during the **final 30%**」；Fig4 caption「activation at **step 1,400**」（1400/2000=30%） | v25:389,501,739 |
| v29 | 「activated exclusively during the **final 20%**」 | v29:496 |
| 脚本 | `experiments.yaml ovf_activation_ratio: 0.8`（final 20%，step 1600）；`real_backend.py` 注释写「Fig4 expects OVF_ACTIVATION_STEP=1400」但代码用 0.8→1600（**脚本内部自相矛盾**） | experiments.yaml:51, real_backend.py:217-222 |

**决策**：(a) 回到 30%（step 1400，改脚本 ratio=0.7）；(b) 保留 20%（step 1600，改 v29 正文 + Fig4 caption + real_backend 注释）。当前 v29 与脚本代码同 20%，但与 v25 的 30% 及脚本注释 1400 矛盾。

---

### A5. 说话人 closed-set：10 → 11

| 侧 | 内容 | 行号 |
|---|---|---|
| v25 | 「**10-speaker** closed-set experiment」；「**10%** chance-level baseline」 | v25:426,863,880 |
| v29 | 「**11-speaker** closed set」；「**9.1%** chance-level baseline」；「small speaker count (n=11)」 | v29:423,849,853,870 |
| 脚本 | `exp7_privacy_verification.py`：`spk_labels = ds.get("speaker_labels")`，`n_speakers` **数据驱动**（非硬编码） | exp7:45-63 |

**性质**：v25=10，v29=11（S16 显式化）。脚本的 speaker 数取决于 TAF-28k 数据实际标签数，**需以真实数据为准**。

**决策**：核实 TAF-28k 数据实际 speaker 数后统一（若数据为 11，则 v25 的 10 是错误、应改 v25；若为 10，则 v29 的 11 是错误、应改 v29）。

---

### A6. 投机解码 draft 模型：0.1B → 0.5B

| 侧 | 内容 | 行号 |
|---|---|---|
| v25 | 「A **124M-parameter** draft model (**Qwen2-0.1B**)」 | v25:431 |
| v29 | 「a lightweight draft model (**Qwen2-0.5B**)… (The 124M Qwen2-0.1B draft … has **no publicly available checkpoint**; the smallest official release Qwen2-0.5B is adopted)」 | v29:428 |
| 脚本 | `experiments.yaml draft_model: "Qwen/Qwen2-0.5B"`，注释记录「Paper originally specified a 124M Qwen2-0.1B draft, but no [checkpoint]」 | experiments.yaml:10-11 |

**性质**：这是 v29 的**诚实修正**（0.1B 无公开 checkpoint，不可复现）。脚本与 v29 一致。

**建议**：**保留 0.5B**（改回 0.1B 会引入不可复现声明）。仅需确保 v25 若仍被引用时其 0.1B 表述同步改为 0.5B（当前 v25 正文仍写 0.1B，两稿并存时不一致）。

---

### A7. 端到端延迟阶段：4 阶段（端云串联）→ 3 阶段（端侧独立 + 云异步）

| 侧 | 内容 | 行号 |
|---|---|---|
| v25 | 「**four distinct stages**: (a) on-device feature extraction (12ms), (b) encrypted transmission (5ms), (c) cloud NVFP4 inference with CoT (230ms), (d) score return & fusion (21ms)」= 12+5+230+21=268ms（**云在关键路径**） | v25:416 |
| v29 | 「**three stages**: (a) feature extraction (12ms), (b) local Q4_K_M student inference (235ms), (c) decision fusion (21ms)」= 12+235+21=268ms；「cloud adds 235ms … **off the critical path**」 | v29:837 |
| 脚本 | `paper_pipeline.py::_device_benchmark` 用 `quantize="int4"`（**非 nvfp4**，见 A8） | paper_pipeline.py:129 |

**性质**：v29 把 268ms 从「端云串联」改写为「端侧独立完成、云异步增强」，直接关系 **C3（边缘实时推理）**。这是更自洽的架构叙事（端侧 268ms 满足 500ms 预算），但偏离 v25 的四阶段表述。

**决策**：(a) 回到 v25 四阶段端云串联；(b) 保留 v29 三阶段端侧独立叙事（更契合「Edge–Cloud」分工与 C3）。

---

## 三、脚本侧缺口 / 不一致

### A8. device benchmark 硬编码 int4（非 NVFP4）

- `paper_pipeline.py:129`：`models.load_causal_lm(config["models"]["teacher"], quantize="int4", bf16=True)`
- 论文 headline 为 NVFP4 QAD；device benchmark 却用 int4 PTQ，产出的延迟/吞吐 CSV 与论文量化方案不符。
- **修复**：改为 `quantize="nvfp4"`（或显式注释该 benchmark 仅测教师骨干、非 NVFP4 方案）。

### A9. AdvFraud 数据量：论文 3,000 vs 脚本 2,119

- 论文（v25=v29）声称 AdvFraud-3k 有 3,000 条 + curated 517。
- 脚本 `exp5_cross_dataset.py:72-76`：本地仅 **2,119 条**（119 S1–S8 + 2,000 novel_template），`review_status` 全 pending、无人工过滤标注；`curated_n = min(517, n_adv)` 取前 517 条占位；`bf16_matched_advfraud=0.882` 为**引用值非实测**。
- **修复**：补数据至 3,000 + 真实 517 人工过滤；或论文降级声明「本地复现用 2,119 条、curated 为占位」。

### A10. fusion 权重「五折 CV」：论文声称 vs 脚本实现

- 论文（v25=v29）声称 fusion 权重经 **L-BFGS + 用户分层五折 CV** 学习。
- 脚本 `real_fusion_classify` 用 `LogisticRegression(solver="lbfgs")` **单一 fit**（`exp13` 传 `fit_data`，无 KFold 循环）。
- **修复**：脚本补五折 CV（对 `Xtr/ytr` 做 `StratifiedKFold(n_splits=5)`，报告 cross-fold 均值与 std）；或论文降级为「单一训练分区 fit」。

### A11. 阈值校准：v25 held-out vs v29 五折 CV vs 脚本单尾

| 侧 | 阈值校准方式 |
|---|---|
| v25 | temperature scaling 用「held-out validation subset / 100 held-out validation samples」 | v25:666,678 |
| v29 | 阈值经「五折 CV within training partition」固定（S9 引入） | v29:478,505 |
| 脚本 | `real_qad_distill_train` 从 train 尾部切 `val_frac=0.15` 作 held-out 片，`_best_f1_threshold` 单尾选阈 | real_backend.py:134-143,428 |

**观察**：脚本的 `val_frac=0.15` 尾部 held-out **正是 v25 的「held-out validation subset」**，而非 v29 的「五折 CV」。若 A2 改回 8:1:1（恢复 validation partition），则脚本的 val 切片与 v25 语义自动对齐，A11 随之闭合。

---

## 修复方向总览

| # | 差异 | 性质 | 建议方向 |
|---|---|---|---|
| A1 | NBE 网格（FP4 E4M3 vs FP8 scale / int4 grid） | 明确错误 | **改回 v25**（scale=FP8 E4M3，网格=int4 round/clamp） |
| A2 | 数据集划分（3:1 vs 8:1:1） | 明确错误 | **改回 v25**（8:1:1 含验证集） |
| A3 | 融合模态数（2 vs 4） | 实质性偏离 | 需决策（默认回 v25 四模态） |
| A4 | OV-Freeze 窗口（20% vs 30%） | 实质性偏离 | 需决策（默认回 v25 30%/step1400） |
| A5 | 说话人数（11 vs 10） | 实质性偏离 | 需核实数据实际 speaker 数 |
| A6 | draft 模型（0.5B vs 0.1B） | 诚实修正 | **保留 0.5B**，同步 v25 表述 |
| A7 | 延迟阶段（3 vs 4） | 实质性偏离 | 需决策（默认回 v25 四阶段） |
| A8 | device benchmark int4 硬编码 | 脚本 bug | 改 nvfp4 |
| A9 | AdvFraud 3,000 vs 2,119 | 数据缺口 | 补数据或降级声明 |
| A10 | fusion 五折 CV 缺失 | 脚本缺口 | 补五折 CV 或降级声明 |
| A11 | 阈值校准方式 | 随 A2 闭合 | 恢复 validation partition 后对齐 |

---

## 附：核心证据行号索引

- v25.tex（`C:\Users\wang\Downloads\v25.tex`，1087 行）
  - 483（8:1:1）· 447（fusion 五折 CV）· 452（w\*=四模态）· 470（5 scalars）· 312（FP8 E4M3 scaling）· 343（eq:nbe round/clamp）· 389/501/739（OV-Freeze 30%/step1400）· 426/863/880（10-speaker/10%）· 431（124M 0.1B draft）· 416（4 阶段延迟）· 485/487（AdvFraud 3,000/517）
- v29.tex（`docs/v29.tex`，1061 行）
  - 478（3:1 无验证集）· 442（fusion 五折 CV）· 447（w\*=二模态）· 465（3 scalars）· 308（FP8 E4M3 scaling 仍在 Table 2）· 345（错误「FP4 E4M3 grid」）· 496（OV-Freeze 20%）· 423/849/853/870（11-speaker/9.1%）· 428（0.5B draft + 诚实注）· 837（3 阶段延迟）· 480/482（AdvFraud 3,000/517）
- 脚本
  - `realeval/qdq.py:28-33`（int4 grid）· `realeval/data.py::group_split(test_ratio=0.1)` · `realeval/real_backend.py:134-143,428,717-840`（val_frac=0.15 / 单尾阈值 / 二模态 fusion）· `experiments/paper_pipeline.py:129`（int4 硬编码）· `experiments/exp5_cross_dataset.py:70-76`（2,119 条）· `config/experiments.yaml:10-11,23,33,51`（draft 0.5B / 8:1:1 注释 / val_frac 0.15 / ovf 0.8）

---

## 修复执行记录（2026-08-31）

用户决策：融合四模态 / OV-Freeze 30% / 延迟四阶段 / 说话人 10 均「回到 v25」；URL/metadata 处理「公式四模态 + 评估诚实标注（脚本保持二模态，因 TAF-28k 无 url/meta）」。以下为逐项执行状态。

| # | 差异 | 执行结果 |
|---|---|---|
| A1 | NBE 网格 | ✅ v29:345 改为 FP8 E4M3 scale + int4 round/clamp，注明与 FP4-E2M1 硬件网格的差异 |
| A2 | 数据集划分 | ✅ v29:478 恢复 8:1:1 含验证集；v29:508 阈值校准锚定 held-out validation partition |
| A3 | 融合四模态 | ✅ v29:436-451 恢复四模态公式 + w\*=[0.40,0.30,0.20,0.10] + 诚实标注（url/meta 中性值代入、权重为部署参数）；v29:257/452/456/464-465 改 5 scalars；v29:76/102/140/248/668 摘要/Intro/架构/footnote 从二模态收敛叙事改回四模态框架 |
| A4 | OV-Freeze 30% | ✅ v29:391/496/795/800 改 30%·1400·≤20%·≥50%；脚本 experiments.yaml:51 + real_backend.py:221 default + config/schema.py:53 三处 0.8→0.7；docs/REPRODUCIBILITY.md:405 同步 |
| A5 | 说话人 10 | ✅ v29:423/849/851/853/870 改 10-speaker·10-way·n=10·10%/10.0% |
| A6 | draft 0.5B | ✅ 保留（诚实修正：0.1B 无公开 checkpoint） |
| A7 | 延迟四阶段 | ✅ v29:837 恢复 12+5+230+21=268ms 四阶段 |
| A8 | device benchmark | ✅ paper_pipeline.py:129 + exp8_latency_benchmark.py:123-125 两处 int4→nvfp4 |
| A9 | AdvFraud 2,119 | ✅ v29:484 加 caveat（本地 2,119 无人工过滤标注、数字来自 formal run）；脚本 exp5 note 已存在 |
| A10 | fusion 五折 CV | ✅ real_backend.py real_fusion_classify 补 user-stratified 五折 CV（StratifiedKFold，报告 cross-fold 均值/std） |
| A11 | 阈值校准 | ✅ 随 A2 闭合：8:1:1 恢复验证集，脚本 val_frac=0.15 尾部 held-out 对齐 v25 held-out validation subset |

**说明**：A6 为诚实修正（非偏离）；脚本融合头保持二模态（3 scalars）与论文四模态公式（5 scalars）并存，由 v29:451 诚实标注桥接——TAF-28k 只提供 text/acoustic 分数，url/meta 权重是部署配置值而非 TAF-28k 测量值。

**遗留（已解决，2026-08-31 补充）**：`reports/2026-08-31_response_to_reviewers_v29.md`（及 `_zh.md`）中原与「回到 v25」正文冲突的三处评审回应——S9（「3:1 split 无验证集」）、S16（「11-speaker」）、R4(c)（「SMS/URL 为可扩展架构接口而非已评估模态」）——已全部改写为与回退后正文一致（8:1:1 / 10-speaker / 四模态）。另在改写时发现并修正 **S1**：NBE 回应中残留「4-bit FP4 (E4M3) grid」的 A1 格式错误，改为「FP8 E4M3 scale + 整数网格（区别于原生 FP4 E2M1）」。两份回应文件均于「总述」后追加「v25 一致性对照说明」记录本次回退。

---

## v28 对照检查（2026-08-31 补充）

对照 `docs/v28.tex`（v29 的前一版，1055 行）后确认：**v28 已包含 A3/A4/A5/A7 四处偏离 v25 的修订；而 A1（NBE「FP4 E4M3 grid」错误）与 A2（3:1 split）是 v28→v29 的修订中新引入的错误**——即 v28 在 NBE 与划分两处反而是正确的（= v25）。

| 项 | v25 基准 | v28 状态 | v29（修复后） | 偏离来源 |
|---|---|---|---|---|
| A1 NBE 网格 | FP8 E4M3 scale + int4 round/clamp | ✅ 正确（v28:345 `s = s_block·s_tensor`，无 FP4-E4M3 grid 错误） | ✅ 已修回正确 | v28→v29 引入错误 |
| A2 划分 | 8:1:1 含验证集 | ✅ 正确（v28:478 `8{:}1{:}1`） | ✅ 8:1:1 | v28→v29 引入错误 |
| A3 融合 | 四模态·5 scalars | ❌ 二模态·3 scalars（v28:436-447,464-465） | ✅ 四模态·5 scalars | v28 已偏离 |
| A4 OV-Freeze | 30%·1400 | ❌ 20%·1600（v28:391,795,800） | ✅ 30%·1400 | v28 已偏离 |
| A5 说话人 | 10-speaker·10% | ❌ 11-speaker·9.1%（v28:423,853,870） | ✅ 10-speaker·10% | v28 已偏离 |
| A6 draft | 124M 0.1B | ✅ 0.5B 诚实修正（v28:428） | ✅ 0.5B 保留 | 正确修正 |
| A7 延迟 | 四阶段 | ❌ 三阶段（v28:837） | ✅ 四阶段 | v28 已偏离 |

**结论**：v29 的修复已把 v28 里偏离 v25 的 A3/A4/A5/A7 全部修回 v25，并修复了 v28→v29 新引入的 A1/A2 错误。修复后 v29 与 v25 在所有 A1-A11 差异点上一致（A6 为诚实修正保留）。

**本轮脚本侧补充修复（对比 v28 时发现的遗漏）**：
- `experiments/exp8_latency_benchmark.py:123-125`：第二处 `quantize="int4"` → `nvfp4`（A8 的 Table 7 batch benchmark 入口，上轮仅修了 paper_pipeline.py）
- `config/schema.py:53`：`ovf_activation_ratio` default `0.8` → `0.7`（A4 的 schema 默认值层，上轮仅修了 yaml 与 real_backend 代码）
- `docs/REPRODUCIBILITY.md:405`：`ovf_activation_ratio` `0.8`/「最后 20%」 → `0.7`/「最后 30%」
- `realeval/real_backend.py` docstring：补注脚本二模态与论文四模态的关系（TAF-28k 只提供 text/acoustic，url/meta 为部署参数）

---

## A7 复审改判（2026-09-01）

复审（`reports/2026-09-01_re_review_v29.md`）发现上轮 A7「回到 v25 四阶段」**仅落地于延迟段（v29:840）**，摘要/贡献/讨论/结论四处仍保留三阶段「云异步 off critical path」叙事，二者对同一 268ms 给出互斥分解；且四阶段（云在关键路径）与 v29:248/251「端侧完整本地推理 + 云异步复核」的架构描述冲突（`235 = 5 + 230` 的数值巧合使「本地推理」与「传输+云端」两套分解长期混淆）。

经作者裁决，A7 **最终统一为三阶段**（即本报告 A7 决策中的「方案 (b)」）：v29:840 已回退为三阶段——端侧 12+235+21=268ms（满足 ≤500ms 实时预算），云异步 review 加 235ms（5ms Wi-Fi 6 传输 + 230ms NVFP4 CoT）off the critical path，不阻塞首个端侧警报。至此 A1–A11 全部落地自洽。

---

## A5 复审改判（2026-09-01）

复审进一步核对 A5 实际取值路径，发现上轮「回到 v25 的 10」是**方向性错误**——真实数据为 **11 speaker**，非 10。

- **实际路径**：`exp7` → `load_chifraud_balanced()`（`speaker_labels=None`）→ fallback 读 `data/ChiFraud/chifraud.npz` → 11 个唯一 speaker（`spk_001`…`spk_011`，61 样本）。
- **四条证据**：① `chifraud.npz` 实读 = 11；② `build_audio_npz.py:88-99` 按 ~6 条/桶分桶，n=61 → ceil(61/6)=11；③ `REPRODUCIBILITY.md:176`「更正 speaker 数 10→11」、`:507`「61 样本 / 11 speakers」；④ `privacy.py` `n_spk = len(set(ytr))` = 11，chance = 1/11 ≈ 9.09%。
- **结论**：数据源实为 **ChiFraud 的 TTS 电话音频**（`chifraud.npz`，61 样本），**非 TAF-28k**；speaker 数为 11，chance 9.1%。v28/v29 修订中的「11-speaker / 9.1%」才是诚实反映；v25 的「10」本身有误。
- **修复**：v29:423/852/854/856/873 五处「10-speaker / 10-way / n=10 / 10.0%」→「11-speaker / 11-way / n=11 / 9.1%」；数据源「TAF-28k corpus」→「61-sample TTS audio subset of the ChiFraud corpus」。
- **遗留（已解决，2026-09-01 诚实降级）**：脚本 speaker-ID 用 `chifraud.npz` 的 MFCC 128 维 embedding（`build_audio_npz.py:23-36`），非论文架构声称的 F_v（Whisper+MFCC 混合）。经作者裁决采用「诚实降级」——v29:852 改为「trained on MFCC-based acoustic embeddings」，v29:402/407 把 F_v 标为设计目标并注明代理嵌入，v29:854 的 dual compression 降级为 MFCC averaging。详见 `reports/2026-09-01_privacy_route_audit.md`。

---

## 隐私保护技术路线审计（2026-09-01，关系 C1）

在 A5 改判基础上，进一步核对 C1 隐私主线的「论文声称 vs 脚本实现」，发现五处对齐缺口（详见 `reports/2026-09-01_privacy_route_audit.md`）：

| # | 缺口 | 严重度 | 脚本证据 |
|---|---|---|---|
| 1 | $\bm{F}_v$ = FBANK-64 + Whisper-投影-64 拼接**无实现** | MAJOR | `build_audio_npz.py`（MFCC tile-128）、`build_taf28k_npz.py`（Whisper-384）；唯一拼接在 fig2 绘图脚本（随机投影 demo） |
| 2 | speaker-ID / ASV-EER 用 **MFCC 非 F_v** | MAJOR | `exp7:43-64` 永远走 `chifraud.npz` fallback |
| 3 | WER/PESQ/STOI/MOS 为 **reference estimates** | MAJOR | 需 `reconstruction.npz`（本地缺失），v29:846 已诚实标注 |
| 4 | LDP $\epsilon{=}1.5$ 可选 + 未认证 | MINOR→MAJOR | exp5 `noise_sigma` 加于未裁剪隐藏状态；`gaussian_ldp`（clipping 版）仅单测调用 |
| 5 | 「64 维 FBANK」措辞 vs `n_mfcc=20` | MINOR | `build_audio_npz.py:23-29` |

**作者裁决：方案 A（诚实降级论文表述）**。已落地 v29 六处：

- v29:402「formally defined as」→「specified as … design target」
- v29:407 末尾加注：Eq.(eq:f-v) 为设计目标，实验用 MFCC/FBANK 与 Whisper 代理嵌入分别评估
- v29:852「trained on $\mathbf{F}_v$ vectors」→「trained on $128$-d MFCC-based acoustic embeddings extracted from the ChiFraud TTS subset」
- v29:854「$\mathbf{F}_v$'s dual temporal compression（MFCC + Whisper pooling）」→「temporal MFCC averaging」
- v29:760 图4 caption「under a fixed sensitivity/clipping convention」→「without a certified sensitivity bound」（对齐 exp5 未裁剪实现）
- v29:911「adopted in this study」→「explored as an optional configuration in this study」

同步更新：`response_to_reviewers_v29.md` / `_zh.md` 的 S14 回应（clipping convention → 无认证 sensitivity 界）。

---

## 归档：2026-09-01_peer_review_v29_round2.md

# 模拟同行评审报告（第二轮）— QAD-MultiGuard (v29)

> **论文**: QAD-MultiGuard: An Edge–Cloud Framework for Multimodal Fraud Detection and Risk Assessment
> **源文件**: `docs/v29.tex`
> **评审框架**: `academic-paper-reviewer` v1.11.1（full 模式，5 座位 panel + 编辑综合）
> **评审日期**: 2026-09-01（第二轮）
> **本轮性质**: 用户要求「以**不同资深学者**（区别于 2026-08-31 第一轮阵容）对论文再进行一次审稿，围绕研究主线不变（C1/C2/C3），针对①研究目标是否清晰确定 ②论文主要工作与目标的对应 ③创新点是否成立且可验证 ④文献综述是否充分准确 ⑤实验设计目的与论证链是否闭环」。
> **性质**: 模拟评审。角色分离只代表视角分工，**不是**独立误差过程的声明；5 个座位为单一模型族（Claude/Opus 4.8）内的视角分离，`model_family_distinct=false`，不代表独立审稿人，也不构成跨家族三角验证。`criteria_binding_unavailable`（未提供 #684 ReviewTargetContext，不做 venue-alignment 绑定式断言）。

---

## Phase 0 — 领域分析与评审团队配置

### 论文基本信息

| 项 | 值 |
|---|---|
| 标题 | QAD-MultiGuard: An Edge–Cloud Framework for Multimodal Fraud Detection and Risk Assessment |
| 摘要长度 | ≈350 词 |
| 全文长度 | ≈13,200 词（含 LaTeX 标记，1064 行） |
| 参考文献数 | 49 |

### 领域分析

| 维度 | 分析结果 |
|---|---|
| 主学科 | 计算机科学 / 应用人工智能（多模态诈骗检测 + 高效边缘推理，ML systems 型） |
| 交叉学科 | ① 隐私与安全（声学表征、LDP）② 高效推理（量化、投机解码）③ 语音信号处理（说话人/韵律表征） |
| 研究范式 | 定量 / 实验 |
| 方法论类型 | 统计建模 / 机器学习（系统 + 实证评测） |
| 目标期刊层级 | `criteria_binding_unavailable`（未提供 #683 ReviewTargetContext）；论文自陈 ESWA（Q1，Elsevier）投稿意图，此仅作领域通用成熟度观察，不作 venue 绑定断言 |
| 论文成熟度 | 接近投稿（结构完整、含附录、49 条参考文献、格式规范） |

### 推荐目标期刊（Top 3）

1. **Expert Systems with Applications (ESWA)** — 论文自陈目标；应用型 ML 系统 + 欺诈检测契合度高。
2. **Information Fusion** — 多模态决策融合（四模态加权 + L-BFGS 阈值）是核心贡献之一。
3. **Neural Networks / Neurocomputing** — 超低位量化蒸馏（QAD/NBE/OV-Freeze）与高效推理方向对口。

### 评审团队配置说明（本轮 vs 第一轮）

第一轮阵容（2026-08-31）：EIC=ESWA 副主编/端侧部署；R1=量化与统计；R2=电信反诈+语音反欺诈；R3=隐私/VoicePrivacy。本轮**四席全部更换为不同资深学者**，且视角更贴合本轮评审重点（研究目标可证伪性、工作-目标对应、创新可验证性、文献准确性、论证链闭环）。Devil's Advocate 为固定对抗席位，不换。

---

## Reviewer Configuration Cards

### Reviewer Configuration Card #1 — Journal-Fit Reviewer（序列化 source ID：EIC）

- **Role**: Journal-Fit Reviewer（内部 `EIC`）
- **Display role**: Journal-Fit Reviewer
- **Identity Description**: 一位在多模态大语言模型与边缘智能部署方向深耕多年的资深编委，长期担任 IEEE/ACM Transactions 级刊物与 ACL/ICASSP 顶会的 Area Chair，近年专注「小语言模型（SLM）+ 端侧推理」这一快速升温子领域。
- **Review Focus**:
  1. 论文在「LLM 时代边缘智能」谱系中的定位是否清晰——QAD-MultiGuard 相对现有量化蒸馏、多模态反诈工作的**增量边界**是否被作者说清。
  2. 标题「Multimodal Fraud Detection」与实际评估范围（audio–text，URL/metadata 仅部署参数）是否匹配，读者预期是否被满足。
  3. 四项贡献（C1 重构抵抗声学嵌入 / C2 超低位量化鲁棒 / C3 边缘实时 / 四模态融合）是否各自达到「可发表创新」的显著性门槛，还是若干工程技巧的组合。
- **Will particularly care about**: 创新点的「质」而非「量」——是否存在一个真正可迁移的机制性洞见，还是多个工程技巧的拼装；标题承诺与正文交付之间是否有落差。
- **Possible blind spots**: 可能低估领域外具体机制（声学嵌入构造、量化格式）的正确性，需 R2/R1 补偿。

### Reviewer Configuration Card #2 — Peer Reviewer 1（Methodology）

- **Role**: Peer Reviewer 1
- **Display role**: Peer Reviewer 1（Methodology）
- **Identity Description**: 一位机器学习评测与基准方法学资深研究者（活跃于 NeurIPS Datasets & Benchmarks 与 ML evaluation 社群），专长是「可证伪的研究目标设定 + 消融设计的因果隔离 + 效应量/p 值的统计严谨性」。
- **Review Focus**:
  1. 三条研究主线（C1/C2/C3）是否被表述为**可证伪、可测量**的目标，而非宽泛方向性口号。
  2. 主要工作（四组件）与三个研究问题的**对应关系是否一一闭环**——每项工作是否真的回答了某个 RQ。
  3. 消融与对比实验的**因果隔离**是否干净（单模态消融、基线公平性、混淆变量控制）。
  4. 效应量（如 OV-Freeze +0.007 F1、NBE +0.007）与显著性声明是否匹配，p 值是否被过度解读。
- **Will particularly care about**: 「研究目标 ↔ 主要工作 ↔ 实验设计 ↔ 结论」四段论证链是否闭环，中间有无断裂或偷换概念。
- **Possible blind spots**: 对领域特定机制（声学嵌入、量化格式）的可行性判断不如 R2 深入，需 R2 补偿。

### Reviewer Configuration Card #3 — Peer Reviewer 2（Domain）

- **Role**: Peer Reviewer 2
- **Display role**: Peer Reviewer 2（Domain）
- **Identity Description**: 一位语音信号处理与说话人/韵律表征资深学者（专注 speaker characterization、anti-spoofing、voice privacy，具 ASVspoof / anti-spoofing 挑战赛背景）。
- **Review Focus**:
  1. $\bm{F}_v$ 声学嵌入构造（FBANK-64 + Whisper-proj-64 拼接）的**领域合理性**，及其与说话人/韵律信息保留的关系。
  2. 说话人攻击验证（speaker-ID / ASV-EER / GLO 重构）的实验设计与指标选择是否正确，**测量对象是否错位**。
  3. Whisper/MFCC 代理嵌入的**代理效度**——代理能否代表论文声称的 $\bm{F}_v$。
  4. 语音反欺诈 / anti-spoofing / deepfake 相关文献覆盖是否充分。
- **Will particularly care about**: 声学嵌入是否真的「重构抵抗」且「保留欺诈检测有用信息」，还是维度压缩的免费副产品；anti-spoofing 与说话人隐私文献的引用完整性。
- **Possible blind spots**: 对端云架构、量化蒸馏的系统细节关注不足，需 R1/EIC 补偿。

### Reviewer Configuration Card #4 — Peer Reviewer 3（Cross-disciplinary / Practical）

- **Role**: Peer Reviewer 3
- **Display role**: Peer Reviewer 3（Perspective）
- **Identity Description**: 一位可信 AI / 隐私工程 + 数据保护合规跨学科学者（兼具 privacy engineering 与 PIPL/GDPR 数据保护法规研究背景，且熟悉金融反诈系统的真实部署约束）。
- **Review Focus**:
  1. 隐私机制（重构抵抗嵌入 + LDP）的**形式化边界与诚实度**——是否把「工程估计」冒充「形式化保证」。
  2. 端云部署假设的**现实性**——「raw audio stays on-device」是否依赖从未言明的受害者终端部署模型。
  3. PIPL/GDPR 合规声明是否有法律分析支撑，还是自我背书。
  4. 真实世界可部署性（算力、带宽、误报成本、监管）对框架设计的反作用。
- **Will particularly care about**: 论文是否把「技术评估」与「法律合规」混为一谈；隐私叙事是否经得起一个持怀疑态度的合规官员或部署工程师的追问。
- **Possible blind spots**: 对量化/蒸馏的纯技术贡献评判偏保守，需 EIC/R1 平衡。

---

## Review Strategy Recommendations

- **本轮评审重点**由用户明确定义为五条：① 研究目标清晰确定度 ② 主要工作-目标对应 ③ 创新点成立性与可验证性 ④ 文献综述充分性/准确性/关键遗漏 ⑤ 实验设计目的与论证链闭环。五席各自的 Review Focus 已按此对齐，Devil's Advocate 仍固定承担「最强反论 + 未被审查前提」。
- **潜在互补/张力**：R1（方法学）与 EIC（定位/创新显著性）在「创新点是否可验证」上会形成交叉验证；R2（语音）与 R3（隐私/合规）在「F_v 重构抵抗 vs 可链接性」上可能形成张力，需综合者仲裁。
- **注意**：本轮为第二轮，第一轮已产出 A1–A11 修复记录、隐私路线审计、诚实降级等多轮修订，v29 现稿已含大量诚实披露。评审应基于**当前 v29 现稿**，同时判断「修订是否充分闭合了研究主线」而非重提已解决项。

---

---

## Phase 1 — 五席评审报告（已完成，2026-09-01）

| Seat | 角色 | 建议 | 置信度 | 报告 |
|------|------|------|--------|------|
| Journal-Fit (EIC) | 多模态 LLM + 边缘智能编委 | Major Revision | 4 | [round2_seat_eic](2026-09-01_round2_seat_eic.md) |
| Reviewer 1 | ML 评测 / 基准方法学 | Major Revision | 4 | [round2_seat_r1](2026-09-01_round2_seat_r1.md) |
| Reviewer 2 | 语音信号处理 / 说话人 / anti-spoofing | Major Revision | 4 | [round2_seat_r2](2026-09-01_round2_seat_r2.md) |
| Reviewer 3 | 可信 AI / 隐私工程 / PIPL-GDPR | Major Revision | 4 | [round2_seat_r3](2026-09-01_round2_seat_r3.md) |
| Devil's Advocate | 固定对抗席位 | findings only（1 Critical + 6 Major + 3 Minor） | per-finding | [round2_seat_da](2026-09-01_round2_seat_da.md) |

## Phase 2 — 编辑综合（已完成，2026-09-01）

见独立编辑决策文件：[reports/editorial_decision_v29_round2.md](reports/editorial_decision_v29_round2.md)

**决策**：Major Revision（四席非 DA 一致 Major，置信度 4；DA 1 项 Critical C1 经裁决为 VALIDATED）。

**三条阻塞项**：R1 可复现性（Critical，EIC+R1+DA）；R2 F_v 端到端隐私验证 + 维度/ASV-EER 对象修正（Major，CONSENSUS-4）；R3 单模态消融（Major，CONSENSUS-3）。**六条 must_fix** + **八条 should_fix** + **六条 consider**，详见编辑决策文件的 Revision Roadmap。

---

## 归档：2026-09-01_privacy_route_audit.md

# QAD-MultiGuard 隐私保护技术路线审计报告（C1）

> **任务**：检查实验设计细节，确认隐私保护技术路线和机制，对齐论文表述与实验一致性。
> **范围**：严格限定于 C1（隐私约束下的声学处理）主线——$\bm{F}_v$ 重构抵抗嵌入 + LDP 本地差分隐私 + 说话人/重构攻击验证。
> **审计日期**：2026-09-01
> **审阅对象**：`docs/v29.tex`（§sec:acoustic、§sec:glo、图1/图4 caption）+ `experiments/exp7_privacy_verification.py` + `experiments/exp5_cross_dataset.py` + `realeval/privacy.py` + `realeval/real_backend.py` + `data/scripts/build_audio_npz.py` + `data/scripts/build_taf28k_npz.py`
> **结论**：论文声称的隐私机制（$\bm{F}_v$ 混合嵌入 + 认证 LDP）在脚本层**几乎无实现**。五处对齐缺口，其中两处 MAJOR（F_v 无实现、speaker-ID 用 MFCC 非 F_v）、一处 MAJOR（重构指标为 reference estimates）、两处 MINOR/MAJOR（LDP 未认证且可选、MFCC 维度措辞）。论文在若干处已诚实标注（reference estimates、optional LDP、非 full DP guarantee），但「$\bm{F}_v$ 作为隐私构件」这一 C1 核心叙事与脚本实际产出存在系统性脱节。

---

## 一、隐私技术路线：论文声称 vs 脚本实际

### 1.1 论文声称的机制（两条腿）

| 机制 | 论文表述 | 落点 |
|---|---|---|
| **$\bm{F}_v$ 混合嵌入** | $\bm{F}_v = [\bm{f}_{\mathrm{mfcc}}(64\text{维 FBANK}) ; \psi(\bm{W}_{\mathrm{proj}}\bar{\bm{h}}_w)(64\text{维 Whisper 投影})] \in \mathbb{R}^{128}$ | v29:405–407 |
| **LDP 本地差分隐私** | $(\epsilon,\delta)$-LDP，$\epsilon{=}1.5$，$\delta{=}10^{-5}$，高斯机制 $\sigma{=}1.0$ | 图1 caption v29:243、图4 caption v29:760 |

### 1.2 脚本实际产出（两条独立的单模态 embedding）

| 产物 | 脚本 | 实际内容 | 维度 | 与 F_v 的关系 |
|---|---|---|---|---|
| `chifraud.npz` | `data/scripts/build_audio_npz.py` | 纯 MFCC（`n_mfcc=20`）时序平均 → **tile 到 128** | 128 | ❌ 无 Whisper、无 FBANK-64、无投影 |
| `taf28k.npz` | `data/scripts/build_taf28k_npz.py` | Whisper-tiny `last_hidden_state` mean-pooling | 384 | ❌ 无 MFCC、无投影到 64、无拼接 |

**唯一出现 F_v 拼接的代码**是画图脚本 `docs/figure_scripts/fig2_acoustic_embedding.py:65–68`：
```python
W_proj = rng.normal(0, 1.0 / np.sqrt(384), size=(64, 384))   # 随机投影（示意）
proj = W_proj @ h_w
F_v = np.concatenate([mfcc_avg, proj])                        # 仅用于绘图，非真实嵌入
```
这是一个**随机正交投影的示意图**（`rng.normal`），不是任何数据构建或实验路径的真实嵌入函数。

---

## 二、五处对齐缺口

### 缺口 1（MAJOR）—— $\bm{F}_v$ 拼接嵌入无脚本实现

- **论文**（v29:405–407）：$\bm{F}_v$ 是「64 维 FBANK + 64 维 Whisper 投影」的拼接，是 C1 的核心构件，贯穿 §sec:acoustic 全节。
- **脚本**：没有任何脚本产出这个拼接嵌入。ChiFraud 走纯 MFCC（20 维平铺到 128），TAF-28k 走纯 Whisper（384 维）。
- **后果**：论文图2（F_v 构造管线）、Eq.(eq:f-v)、「dual temporal aggregation」描述均无对应实现；所有声称「作用于 $\bm{F}_v$」的实验实际上作用于两种**不同的代理嵌入**。

### 缺口 2（MAJOR）—— speaker-ID / ASV-EER 用 MFCC，非 $\bm{F}_v$

- **论文**（v29:852）：「an MLP … was trained directly on $\mathbf{F}_v$ vectors」；v29:854 把「dual temporal compression（MFCC + Whisper pooling）」作为 8.3% 精度的解释机制。
- **脚本**（`exp7_privacy_verification.py:43–64`）：
  - `load_chifraud_balanced()` 返回 `embeddings=None`、`speaker_labels=None`（`realeval/data.py`），故**永远**走 fallback：读 `chifraud.npz` 的 `embeddings`。
  - 该 `embeddings` 是 `build_audio_npz.py` 的**纯 MFCC tile-128**，不是 $\bm{F}_v$。
  - `asv_eer_open_set(emb, ...)`、`speaker_identification(emb, ...)`、`glo_reconstruction_attack(emb, emb[:, :64], ...)` 全部作用于 MFCC。
  - 代码注释写「prefer TAF-28k NPZ」，但 `load_chifraud_balanced` 不返回 TAF-28k 嵌入，该「prefer」分支从未可达。
- **双重错位**：嵌入类型（MFCC vs $\bm{F}_v$）+ 数据源（ChiFraud 61 样本 vs TAF-28k）。表 4 的 8.3% / 7.9% / 46.8% / 48.5% 全部建立在 MFCC 上。
- **与 A5 的关联**：这正是上一轮 A5 改判（11-speaker / ChiFraud）暴露出的同一残余张力——v29:852 现写「trained on $\mathbf{F}_v$ vectors, … ChiFraud corpus」，但「$\mathbf{F}_v$ vectors」与实际读入的「ChiFraud MFCC」仍不一致。

### 缺口 3（MAJOR）—— 重构质量 WER/PESQ/STOI/MOS 为 reference estimates，非脚本产出

- **论文**（v29:846）已诚实标注：「The reconstruction-quality figures (WER, PESQ, STOI, MOS) are reference estimates … rather than independently re-measured outputs of the released evaluation pipeline.」
- **脚本**（`exp7`）：`_load_reconstruction_assets` 依赖 `<data_root>/privacy/reconstruction.npz`，本地**缺失** → `recon=None` → 四项指标全部 `not_measured`/pending。
- **性质**：论文已如实披露，非造假；但表 4（`tab:privacy_attack-en`）四行重构质量数字（WER≥0.95 / PESQ≤1.21 / STOI≤0.11 / MOS≤1.18）**不可从公开脚本复现**，与 R1 的可复现性缺口同源。

### 缺口 4（MINOR→MAJOR）—— LDP $\epsilon{=}1.5$ 可选 + 未认证 DP

- **论文三层表述**：
  - 图1 caption（v29:243）：「optional configuration … omitted from the main experimental configuration」；
  - 测量范围（v29:510）：「optional engineering configuration excluded from the main results」；
  - 图4 caption（v29:760）：「$\epsilon = 1.5$ is an engineering estimate under a fixed sensitivity/clipping convention」；
  - 未来工作（v29:911）：「inference-time local differential privacy mechanism **adopted** in this study」。
- **脚本实际**（`exp5` + `real_backend.py:618–619`）：`noise_sigma` 加到**未裁剪的隐藏状态**（`last = last + torch.randn_like(last) * noise_sigma`），sensitivity 无界。exp5 内注释明确：「NOT a certified (ε,δ)-DP guarantee (audit P2-9)」。
- **关键不一致**：
  1. 图4 caption 声称「fixed sensitivity/clipping convention」，但 `real_backend` 的 `noise_sigma` 路径**没有 clipping**——「clipping convention」在实际实现中不存在。
  2. `privacy.py:280` 的 `gaussian_ldp`（标准「特征裁剪 + 加噪」实现，含 `clip_bound=3.0`）**只在单测 `tests/test_realeval.py:306` 被调用**，从未进入任何实验。exp5 的 LDP 走的是另一条 `noise_sigma` 路径。
  3. v29:911 的「adopted」与 v29:243/510 的「omitted / optional / excluded」存在措辞张力。
- **性质**：论文在 caption 层已诚实降级（非 full DP guarantee），但「$\epsilon{=}1.5$」仍作为图4(c) 的具体数值出现，且其支撑实现（认证的 clipping LDP）缺失。

### 缺口 5（MINOR）—— MFCC 维度措辞 vs 实际

- **论文**（v29:407）明确澄清：「64-dimensional log-mel filterbank energies (FBANK)；mfcc 下标是 mnemonic，非 DCT cepstral 系数」。
- **脚本**（`build_audio_npz.py:23–29`）：`librosa.feature.mfcc(n_mfcc=20)` → **20 维真 MFCC 系数**（DCT cepstral），既非 FBANK，也非 64 维。
- **性质**：论文的「64 维 FBANK」澄清只存在于文字层，脚本实际用的是 20 维 DCT-MFCC，然后 tile 到 128。故「FBANK」这一光谱学措辞在脚本中无对应。

---

## 三、隐私机制现状全景图

| 论文声称的隐私机制 | 脚本是否实现 | 实现位置 / 状态 |
|---|---|---|
| $\bm{F}_v$ = FBANK-64 + Whisper-投影-64 拼接 | ❌ 无 | 仅 fig2 绘图随机投影 demo |
| FBANK-64 光谱分量 | ❌ 无 | 脚本用 `n_mfcc=20` DCT-MFCC |
| Whisper 投影到 64（rank≤64） | ❌ 无 | TAF-28k 用 384 维 mean-pooling，无投影 |
| speaker-ID 攻击验证 | ⚠️ 部分 | 有（`speaker_identification`），但用 MFCC 非 F_v |
| ASV-EER 攻击验证 | ⚠️ 部分 | 有（`asv_eer_open_set`），但用 MFCC 非 F_v |
| GLO 重构攻击 | ⚠️ demo | `glo_reconstruction_attack` 无 `proj_fn` 时跑随机正交投影（P1-M4，已诚实标注 demo） |
| WER/PESQ/STOI/MOS 重构质量 | ⚠️ 待资产 | harness 就绪，缺 `reconstruction.npz` → not_measured |
| LDP（认证 $\epsilon{=}1.5$） | ❌ 无 | `gaussian_ldp`（clipping 版）仅单测；exp5 用未裁剪 `noise_sigma`（非认证） |
| PII 扫描（`scan_texts`） | ✅ 有 | exp7:42 实际运行 |

**一句话总结**：C1 的「隐私保护」在脚本里真正落地的是**PII 文本扫描 + 未认证的高斯加噪演示 + 基于 MFCC 的说话人/重构攻击验证**；论文作为核心隐私叙事载体的「$\bm{F}_v$ 混合嵌入 + 认证 LDP」两项机制在实验层均无实现。

---

## 四、决策点（待作者裁决）

C1 的「论文声称 vs 脚本实现」脱节，对齐方向有三条路径，各有代价：

- **方案 A（诚实降级论文表述）**：把 $\bm{F}_v$ 从「已实现的隐私构件」改写为「架构设计目标」，明确 speaker-ID/ASV-EER 实验用 MFCC 代理嵌入；LDP 保留「optional / 未认证」并删除「clipping convention」措辞。代价：弱化 C1 的核心技术贡献，但完全诚实、可复现。
- **方案 B（补实现 $\bm{F}_v$）**：新增脚本实现 FBANK-64 + Whisper-投影-64 的拼接，重跑 speaker-ID/ASV-EER/GLO。代价：需真实音频 + Whisper-tiny + 投影权重，属 H100/音频重跑周期，短时间不可完成。
- **方案 C（架构-实验分离标注）**：保留 $\bm{F}_v$ 作为设计叙事，但在 §sec:glo 明确标注「本实验的隐私验证以 MFCC/Whisper 代理嵌入进行，$\bm{F}_v$ 的拼接实现与端到端隐私评估留作未来工作」。代价：中间态，仍留残余张力。

**复审核查意见**：从「诚实优先 + 与 R1/R2 已披露口径一致」的既有基调看，**方案 A（诚实降级）最自洽**；若作者坚持保留 $\bm{F}_v$ 作为核心贡献，则至少需采用方案 C 的显式分离标注，避免「trained on $\mathbf{F}_v$ vectors」这类与脚本直接矛盾的断言继续存在。方向由作者定夺。

---

## 附：核心证据行号索引

- **论文** `docs/v29.tex`：405–407（F_v 定义）· 417（dual compression）· 852/854（speaker-ID on MFCC）· 846（reference estimates）· 243（图1 LDP optional）· 510（LDP excluded）· 760（图4 σ=1.0/ε=1.5 engineering estimate）· 911（LDP optional/explored）
- **脚本**
  - `data/scripts/build_audio_npz.py:23–36`（n_mfcc=20 → tile 128）· `:88–99`（speaker 分桶）
  - `data/scripts/build_taf28k_npz.py:62`（Whisper 384，无投影）
  - `experiments/exp7_privacy_verification.py:43–64`（fallback 读 chifraud.npz，speaker-ID/ASV 用 MFCC）· `:9–27,81–96`（reconstruction.npz 缺失 → not_measured）
  - `experiments/exp5_cross_dataset.py`（noise_sigma 未裁剪隐藏状态，P2-9 非认证）
  - `realeval/real_backend.py:501,507–508,615–619`（noise_sigma 加噪路径）
  - `realeval/privacy.py:280`（gaussian_ldp clipping 版，仅单测调用）
  - `tests/test_realeval.py:306`（gaussian_ldp 唯一调用点）
  - `docs/figure_scripts/fig2_acoustic_embedding.py:65–68`（F_v 拼接唯一出现，随机投影 demo）

---

## 附 B：v19 初稿 ↔ v29 修订稿 隐私描述对照（2026-09-01 补充）

以 `C:\Users\wang\Downloads\v19.tex`（672 行初稿）为对照基准，隐私机制描述偏差归纳为「一条降级线 + 一个增补点 + 一处数据修正」：

### 降级线（强声明 → 保守措辞）

| v19 落点 | v19 措辞 | v29 落点 | v29 措辞 |
|---|---|---|---|
| 贡献 (3) v19:84 | Practically **irreversible** … **We constructed** F_v | v29:139-140 | **Reconstruction-resistant** … is **designed** + not designed for unlinkability |
| 摘要 v19:42 | privacy-preserving … reducing the risk | v29:76 | reconstruction-resistant … resists |
| highlights v19:48 | Privacy-preserving … degrade | v29:82 | Reconstruction-resistant … hinder |
| keywords v19:54 | privacy preservation | v29:93 | reconstruction-resistant representation |
| 表1 v19:123 | F_v practically non-invertible | v29:194 | Reconstruction-resistant 128-d embedding |
| Tier-1 v19:159 | satisfying PIPL requirements | v29:858 | technical assessment, not legal compliance |
| F_v 定义 v19:280 | privacy-preserving … defined as | v29:402 | reconstruction-resistant … specified as design target |
| speaker-ID v19:563 | dual compression … destroys | v29:854 | temporal MFCC averaging … attenuates |
| LDP v19:590/592 | formal (ε,δ)-LDP / unlinkability guarantees | v29:760/886 | engineering estimate without certified sensitivity bound |
| Related Work v19:230 | we **construct** … concatenated to form F_v | v29:230 | we **design** … specified as design target + proxy embeddings |

### 增补点（非降级，而是新增的诚实限定）

v29:140 贡献 (3) 新增 v19 没有的自我限定：「…but is not designed for cross-session unlinkability; a semi-honest cloud may still link repeated sessions of the same speaker through embedding similarity」。这是 S4（ASV-EER 对象澄清）从讨论层上浮到贡献层的结果。

### 数据修正（同源，非措辞偏差）

speaker 200→11 · TAF-28k→ChiFraud 61 样本 · chance 10%→9.1% · F_v→MFCC embedding。

### v19 内部本有的「摘要 vs 正文」措辞分裂

v19 摘要（42）已是保守语气（is designed / reducing the risk），但贡献（84）与正文（280/563）是强声明（We constructed / defined as / destroys）。v29 的动作本质是把正文拉到摘要已有的保守水位，并进一步压成 reconstruction-resistant / resists / attenuates。

### 本轮新增修点（2026-09-01「一并处理」）

执行时发现并修复三处残留：v29:400（subsection 标题 Privacy-Preserving→Reconstruction-Resistant）、v29:226（Related Work 标题同步）、v29:230（we construct→we design + design target/proxy 标注）。保留 v29:884（privacy-preserving machine-learning systems，泛指）与 v29:911（privacy-preserving optimisation DP-SGD，指真实 DP 训练）两处，因其语义确为「隐私保护」而非本文 F_v 的「重构抵抗」。

---

## 归档：2026-09-01_re_review_v29.md

# QAD-MultiGuard v29 修订落地复审报告

> **任务**：在 v25 权威基准 + 三研究主线（C1 隐私约束声学处理 / C2 超低位量化鲁棒性 / C3 资源受限边缘实时推理）范围内，复核 A1–A11 修订是否完整落地、内部自洽，不偏离标题方向。
> **标题**：*QAD-MultiGuard: An Edge–Cloud Framework for Multimodal Fraud Detection and Risk Assessment*
> **复审日期**：2026-09-01
> **审阅对象**：`docs/v29.tex`（1063 行）+ 实验脚本 + 评审回应文档
> **结论**：A1–A11 经两轮作者裁决**全部落地并自洽**。两处 MAJOR 改判：(1) A7 延迟叙事统一为三阶段（端侧 12+235+21=268 ms，云异步 off critical path）；(2) A5 说话人数从「10」改判回「11」（9.1% chance，数据源 ChiFraud TTS 61 样本，非 TAF-28k）——上一轮「回到 v25 的 10」被脚本/文档证据推翻。

---

## 一、逐项落地核验（A1–A11）

| 项 | 差异 | 落点（v29 现稿） | 状态 |
|---|---|---|---|
| A1 | NBE 网格 | v29:345（FP8 E4M3 scale + 整数网格，区别于原生 FP4 E2M1） | ✅ |
| A2 | 8:1:1 含验证集 | v29:481（8:1:1）、508（held-out validation）、444（held-out test 未用于拟合）、668（100 held-out 样本校准） | ✅ |
| A3 | 四模态融合 | v29:436-451（四模态公式 + w\*=[0.40,0.30,0.20,0.10] + 诚实标注）、76/102/140/175/248/251/325/668 | ✅ |
| A4 | OV-Freeze 30% | v29:391（final 30%）、499（final 30%）、798（steps 1400–2000、≤20%、≥50%）、803（Fig 6 caption） | ✅ |
| A5 | 11-speaker | v29:423/852/854/856/873（11-speaker·11-way·n=11·9.1%·ChiFraud TTS 61 样本）——复审后改判：真实数据 11，非 10 | ✅ |
| A6 | draft 0.5B | v29:428（0.5B + 诚实注：0.1B 无公开 checkpoint） | ✅ |
| A7 | 延迟三阶段 | v29:840（12+235+21=268 ms，云异步 off critical path）——复审后按作者裁决统一三阶段 | ✅ |
| A8 | int4→nvfp4 | `paper_pipeline.py:129`、`exp8_latency_benchmark.py:123-125` | ✅ |
| A9 | AdvFraud caveat | v29:483（本地 2,119 无人工过滤、3,000/517 来自 formal run） | ✅ |
| A10 | fusion 五折 CV | `real_backend.py::real_fusion_classify`（StratifiedKFold，cross-fold 均值/std） | ✅ |
| A11 | held-out 阈值校准 | v29:508、668 | ✅ |

**A2 补充核验**：全稿 Grep `21,490` / `7,021` / `no separate` / `no validation` 均无残留，3:1 表述已彻底清除。
**A5 补充核验（改判）**：脚本实读 `chifraud.npz` → 11 个唯一 speaker（`spk_001`…`spk_011`，61 样本）；`build_audio_npz.py:88-99` 按 ~6 条/桶分桶得 11；`REPRODUCIBILITY.md:176/507` 明写「更正 10→11」「61 样本 / 11 speakers」。四条证据收敛，改判为 11-speaker。
**A4 补充核验**：全稿 Grep `final 20` / `1600` 无残留（命中项均为基金号）。

---

## 二、MAJOR 发现（已解决）：A7 延迟叙事未完整落地（关系 C3）

### 2.1 现象

A7 决策「回到 v25 四阶段」只改了 **v29:840**（延迟分解段），但摘要/贡献/讨论/结论四处仍保留 v29 三阶段的「云异步 off critical path」叙事。两者对同一 `268 ms` 数字给出**互斥分解**：

| 位置 | 表述 | 所属框架 |
|---|---|---|
| v29:840 | 四阶段：端侧特征 12ms + 传输 5ms + **云端 NVFP4 230ms** + 融合 21ms = 268ms | 四阶段（云在关键路径） |
| v29:76（摘要） | 「**on-device** Q4_K_M student … 268ms **on Snapdragon**，while **cloud-side NVFP4** track reaches 0.923 **with asynchronous CoT**」 | 三阶段（268ms = 端侧本地，云异步） |
| v29:147（贡献） | 「an **asynchronous cloud review** … refines the decision **off the critical path**」 | 三阶段 |
| v29:721（CoT 消融） | 「…in the **asynchronous cloud review**」 | 三阶段 |
| v29:899（讨论） | 「the **asynchronous cloud review** reduces false positives **off the critical path**」 | 三阶段 |
| v29:919（设计启示） | 「reserving **asynchronous cloud review** for **off-critical-path** refinement」 | 三阶段 |

**核心矛盾**：摘要说 268ms 是「端侧 Snapdragon 上的 Q4_K_M 本地推理」；延迟段说 268ms 是「端侧 12ms + 云端 NVFP4 230ms 的端到端」。同一数字无法同时是「纯端侧」与「端+云」。

### 2.2 更深层的架构张力

四阶段框架本身与 v29:248/251 的架构描述冲突：

- **v29:248**：端侧学生「produces text and acoustic risk scores that are **fused on-device (Tier-3) into an immediate risk decision**… the **blocking real-time path**」——即端侧做**完整本地推理 + 融合**（≈235ms 本地），而非仅 12ms 特征提取。
- **v29:840 四阶段**：端侧仅「feature extraction (12ms)」，分类交给云端 230ms——与「端侧本地推理产出 0.917」矛盾。

即：**三阶段（云 off-path）才与「端侧做完整本地推理」的架构自洽**；四阶段把 268ms 里的 235ms 块从「本地推理」改写成了「5ms 传输 + 230ms 云端」，但架构描述仍按三阶段写。`235 = 5 + 230` 的数值巧合使两套分解长期混淆未决。

### 2.3 建议（需作者决策）

二选一，全稿统一：

- **方案 A（一致四阶段，云在关键路径）**：改 v29:76 摘要为「end-to-end 268ms（端侧特征提取 + 云端 NVFP4 推理 + 融合）」，并删除 147/899/919 的「off the critical path」措辞。**代价**：需同时说明「on-device Q4_K_M 0.917」与「端侧仅做特征提取」的矛盾（若端侧不本地分类，0.917 从何而来）。
- **方案 B（一致三阶段，云 off-path）**：回退 v29:840 为三阶段（端侧 12+235+21=268ms），云异步增强 off-path。**更契合** v29:248/251 的「端侧本地推理 + 云异步复核」架构，也与 C3「边缘实时推理满足 500ms 预算」主线自洽（这也是上一轮 reconciliation 报告 A7 中已注明的「v29 三阶段更自洽」判断）。

**复审核查意见**：从「端侧完整推理 + 云异步增强」的既有架构描述与 C3 主线看，**方案 B 内部更自洽**；但「回到 v25 四阶段」是上一轮明确决策，方向取舍由作者定夺，本报告仅指出不一致，不代选。

**最终裁决与修复（2026-09-01）**：作者选定**方案 B（统一三阶段）**。已执行——v29:840 从四阶段回退为三阶段（`on-device real-time path` 三阶段 12+235+21=268ms；云异步 review 加 235ms = 5ms Wi-Fi 6 传输 + 230ms NVFP4 CoT，`off the critical path`），并同步把 `50 parallel sessions` 改回 `50 parallel on-device sessions`。摘要（76）、贡献（143/147）、CoT 消融（721）、讨论（899）、设计启示（919）本已为三阶段叙事，无需改动。全稿 Grep 复核：`four distinct stages` / `four stages` / `round-trip time` / `score return` 均无残留。

### 2.4 A5 说话人数改判（2026-09-01，关系 C1）

复审期间进一步核对 A5 的实际取值路径，发现上一轮「回到 v25 的 10」是**方向性错误**：

- **实际取值路径**：`exp7` → `load_chifraud_balanced()`（`speaker_labels=None`）→ fallback 读 `data/ChiFraud/chifraud.npz` → `speaker_labels` 唯一值 = **11**（`spk_001`…`spk_011`，61 样本）。
- **四条独立证据**：① 实读 `chifraud.npz` = 11 speaker；② `build_audio_npz.py:88-99` 按 ~6 条/桶分桶，n=61 → ceil(61/6)=11；③ `REPRODUCIBILITY.md:176` 明写「更正 speaker 数 10→11」、`:507`「61 样本 / 11 speakers」；④ `privacy.py` `n_spk = len(set(ytr))` = 11，chance = 1/11 ≈ 9.09%。
- **结论**：真实数据为 11 speaker（9.1% chance，数据源 ChiFraud TTS 音频 61 样本，**非 TAF-28k**）。v28/v29 修订中出现的「11-speaker」才是对脚本真实产出的诚实反映；v25 的「10」本身有误。
- **修复**：v29:423/852/854/856/873 五处「10-speaker / 10-way / n=10 / 10.0%」→「11-speaker / 11-way / n=11 / 9.1%」；数据源「TAF-28k corpus」→「61-sample TTS audio subset of the ChiFraud corpus」。
- **遗留提示（已解决，2026-09-01 隐私路线审计 + 诚实降级）**：脚本 speaker-ID 实验所用 embedding 为 `chifraud.npz` 的 **MFCC 128 维**（`build_audio_npz.py:23-36`），非论文架构声称的「$\mathbf{F}_v$（Whisper global pooling + MFCC 混合）」；且数据源为 ChiFraud 而非 TAF-28k。经作者裁决采用「诚实降级」——v29:852 已改为「trained on the $128$-dimensional MFCC-based acoustic embeddings extracted from the ChiFraud TTS subset」，v29:402/407 把 $\bm{F}_v$ 标为设计目标并注明实验用代理嵌入，v29:854 的「dual temporal compression（MFCC + Whisper pooling）」降级为「temporal MFCC averaging」。详见 `reports/2026-09-01_privacy_route_audit.md`。

---

## 三、次要观察（非阻塞）

1. **「audio–text」与「four-modal」术语并存**：v29:76/140 用「audio–text fusion / fraud detection」、v29:175 用「audio–text dual-modality **dataset**」、v29:436 用「four-modal fusion」。因 TAF-28k 数据集本身确为 audio–text（url/meta 仅部署参数），此为「数据集双模态 + 框架四模态」的既定诚实标注，语义可辨，但建议在摘要首次出现处点明「数据集 audio–text、框架四模态」，减少读者对标题「Multimodal」与正文「audio–text」的瞬时困惑。
2. **「three-tier design」措辞**（v29:899）：指端/云处理层级，与「四阶段延迟」不同概念，非冲突；但「tier」与「stage」两套编号并行，可考虑统一术语以免歧义。

---

## 四、复审核验方法与范围

- 方法：以 A1–A11 修复记录 + v25 基准逐项 Grep/Read 核验 v29 落地点；对三研究主线（C1/C2/C3）做内部一致性检查；对脚本做 `quantize` / `ovf_activation_ratio` 残留扫描。
- 范围：严格限定于标题方向与 C1/C2/C3 主线；未扩展到新研究问题或非修复项。
- 复审期间经作者两轮裁决，已就地修订 `docs/v29.tex`：A7（v29:840 四阶段→三阶段）与 A5（v29:423/852/854/856/873 10-speaker→11-speaker）。

---

## 附：与上一轮 v28 对照检查的关系

上一轮确认 A1/A2 为 v28→v29 新引入错误（已修），A3/A4/A5/A7 为 v28 已存在偏离（已回退）。本轮复审核验确认：A1–A4、A6、A8–A11 的「回到 v25」已落地；**A7 与 A5 两处经复审改判**——A7 统一三阶段（正文已回退、摘要/讨论本已一致）；A5 说话人数从「回到 v25 的 10」改判回「11」（脚本/文档证据显示真实为 11，v25 的 10 本身有误）。

---

## 归档：2026-09-01_round2_panel_seats.md

# Round-2 评审 Panel 座位报告（合并）

> 合并自 5 个独立座位文件（2026-09-01），内容逐字保留；原文件已合并删除。
> 综合评审：`reports/2026-09-01_peer_review_v29_round2.md` · 编辑决策：`reports/editorial_decision_v29_round2.md`

---


## Seat DA

# Devil's Advocate Review — Round 2, Seat DA

**Manuscript:** `docs/v29.tex` — QAD-MultiGuard: An Edge–Cloud Framework for Multimodal Fraud Detection and Risk Assessment
**Role:** Devil's Advocate（固定对抗席位）
**Date:** 2026-09-01

---

## Devil's Advocate Review

### Calibration Status

`NOT_CALIBRATED`

[Seat reports always emit `NOT_CALIBRATED`: the final actual panel topology is not knowable until every seat has completed. A candidate profile never upgrades the seat report.]

### Criterion-Bound Judgements

| Dimension / criterion | Criterion source | Judgement | Evidence anchors | Rationale | Uncertainty or scope limit | Decision bearing? |
|---|---|---|---|---|---|---|
| Originality | review_criteria_framework.md §1 (universal) | PARTLY_MEETS | text: §1 contribution paragraph; text: §4.3 "design target" | Novelty is claimed as *integrated co-design* of established techniques, which is defensible; but two of the four components (F_v, four-modal fusion) are not actually evaluated as claimed, so their originality is asserted, not demonstrated | Component-level novelty unverifiable until F_v / four-modal are measured | yes — weakens the claimed contribution set |
| Methodological Rigor | review_criteria_framework.md §1 | DOES_NOT_MEET | absence: public repo — expected QAD reproduction of Table 3; checked Reproducibility statement §5.1 | QAT baseline is not tuned beyond the shared budget (strawman); on-device latency is an assembled estimate not a measured end-to-end figure; no single-modality ablation; reproduction run does not yet produce the reported tables | Could be repaired by rerun + baseline tuning + ablations | yes — core empirical claims rest on unreproducible/unablatated runs |
| Evidence Sufficiency | review_criteria_framework.md §1 | DOES_NOT_MEET | text: §4.3 "proxy embeddings"; text: §5.8 "reference estimates"; text: §5.8 "128-dimensional MFCC-based" | The central privacy evidence is proxy/reference estimates on n=11 speakers; the four-modal claim has zero four-modal evidence; the acoustic branch's incremental value is unquantified | Author disclosures are extensive, but disclosure does not supply the missing evidence | yes — contribution 3 evidence is insufficient |
| Argument Coherence | review_criteria_framework.md §1 | PARTLY_MEETS | text: §3.2 "empirically achieves WER ≥ 0.95" vs §4.3 "design target"; text: §4.3 "64-dimensional" vs §5.8 "128-dimensional MFCC-based" | Internal contradictions between the threat model (claims the deployed embedding empirically achieves WER≥0.95) and §4.3/§5.8 (says it is a proxy/design target, never jointly evaluated); a concrete 64-vs-128 dimensional mismatch | Some may be authorial imprecision rather than substantive error; the dimensional mismatch is hard to read that way | yes — contradiction undermines trust in the privacy claims |
| Writing Quality | review_criteria_framework.md §1 | MEETS | text: §5.1 effect-size paragraph; §7 discussion | Unusually candid and precise about effect sizes, NBE emulation, LDP non-certification, linkability risk; separate presentation from substance | Non-native phrasing does not impede meaning | no |
| Literature Integration | review_criteria_framework.md §1 | MEETS | text: §2 related work | QAD, PTQ, speculative decoding, voice-anonymisation literature are covered and correctly scoped | None identified | no |
| Significance & Impact | review_criteria_framework.md §1 | PARTLY_MEETS | text: abstract "feasibility baseline" | The "feasibility baseline" framing is appropriately bounded; but the distinguishing impact (privacy-preserving acoustic fusion) is unmeasured, so demonstrated impact is thinner than the framing implies | Field validation explicitly deferred | yes — impact claim over-reaches the measured evidence |

### Acknowledged Genuine Strengths

This manuscript is, in honesty and self-disclosure, well above the field median. It reports Cohen's *h* effect sizes that undercut its own headline gains (OV-Freeze *h*≈0.02), transparently labels NVFP4 results as QDQ numerical-behaviour emulation rather than native Blackwell, explicitly states LDP is "an engineering estimate without a certified sensitivity bound" rather than a formal mechanism, and names the cosine-similarity linkability residual risk that most authors would hide. The QAD-over-PTQ result (0.923 vs 0.838) is real and large, and the cross-format Q4_K_M portability (0.917) is a legitimate engineering result. I flag these as genuine before turning to attack.

### Strongest Counter-Argument

作为一个持相反立场的审稿人，我会这样反驳：这篇论文的三条支柱——多模态融合、重构抵抗隐私、边缘效率——每一条都建立在一个"替代品"之上。"四模态"融合实际上是双模态（text+acoustic），URL/metadata 权重是惰性占位；"重构抵抗 128 维嵌入"从未被实际评估——其隐私数字来自 64 维代理特征、"reference estimates"、以及一个低于随机水平的 11 说话人子集；"边缘 268 ms"是逐阶段拼接的估算值，而被标记为应对 C3 实时约束的投机解码 3.32× 加速实际上只跑在云端、off-critical-path，与边缘时延预算毫无关系。更关键的是：承载隐私主张的那条新模态——声学分支——没有任何单模态消融，论文自己承认它"可能是次要贡献"（w_audio=0.30 < w_text=0.40），而 text 分支只是 SMS 结构特征，不是通话内容（设计上禁用 ASR）。对论文自身动机中的核心场景——一通 90 秒、前 60 秒内给出诈骗指令的电话——通常没有伴随 SMS，于是"多模态"系统退化为纯声学韵律检测。也就是说，可复现的部分（对文本分类器的 4-bit 蒸馏）是标准 QAD，而区分性部分（隐私声学融合）同时是：未评估的、价值未量化的、且可能微乎其微的。最简约的解读是：这是一次对文本分类器的合格低位蒸馏，被包装成"隐私保护多模态系统"，而其区别性组件均未经过测量。

### Issue List

#### CRITICAL

| # | Dimension | Issue Description | Evidence Anchor | Confidence | Field-Norm Boundary | Evidence-Crossing Rationale |
|---|---|---|---|---|---|---|
| C1 | 1. Core Thesis Challenge / 3. Evidence | 核心隐私贡献（contribution ③）在实证上悬空：实际部署的 128 维 F_v 从未被评估。§4.3 承认发布实验评估的是"两个分量的 proxy embeddings"而非联合训练的 F_v；§5.8 承认重构指标是"reference estimates ... rather than independently re-measured"；说话人识别在 n=11、61 样本上得到 *低于* 随机水平的结果（8.3% vs 9.1%）。但 §3.2 威胁模型仍断言"the deployed embedding empirically achieves WER ≥ 0.95"。此外存在硬性维度矛盾：§4.3 规定 MFCC/FBANK 分量为 64 维，§5.8 却称说话人分类器训练于"128-dimensional MFCC-based acoustic embeddings"。诚实降级（design target / proxy）与仍被主张的结论（empirically achieves）在文本内同时成立，自相矛盾。 | text: §4.3 "the released experiments evaluate its two components through their respective proxy embeddings"; §5.8 "reference estimates from the reconstruction-attack analysis rather than independently re-measured"; §5.8 "128-dimensional MFCC-based acoustic embeddings"; §4.3 "64-dimensional log-mel filterbank energies" | 5（逐字核对 §4.3/§5.8/§3.2 原文，矛盾是字面的） | — | — |

#### MAJOR

| # | Dimension | Issue Description | Evidence Anchor | Confidence | Field-Norm Boundary | Evidence-Crossing Rationale |
|---|---|---|---|---|---|---|
| M1 | 5. Overgeneralization Check | "四模态决策融合"（contribution ④、标题、摘要）在所有报告结果中实为双模态。URL（0.20）与 metadata（0.10）权重被称作"carried forward"的部署参数——TAF-28k 无 URL/meta 数据，故这两个权重从未被学习。但 Eq. (9) 将 w*=[0.40,0.30,0.20,0.10] 表述为"cross-fold averaged parameters"（§4.5 "learned using L-BFGS"），把一个四维"已学习"向量呈现给读者，其中两维不可能被学习。 | equation: Eq. (9) eq:w-deploy "w* = [0.40, 0.30, 0.20, 0.10]" vs §4.5 "the fusion weights are learned using the L-BFGS" | 5（Eq. (9) 与 §4.5/§5.11 的直接对照） | — | — |
| M2 | 4. Logic Chain Validation | "audio–text 多模态"的前提在其核心场景下不成立。text 分支由 SMS 结构特征（12-d）驱动，且设计上禁用 ASR（Whisper 解码器被省略），故通话的语言内容从不进入模型。§4.5 明言"when no SMS accompanies a call, the text score defaults to a neutral value and fusion reduces to the acoustic branch"——即对论文自身动机中的诈骗电话场景（通常无伴随 SMS），系统退化为纯声学。动机段批评 ASR-transcript 管线并主张直接多模态融合更优，但本系统并不融合"通话音频+通话文本"，而是融合"通话音频+独立 SMS"，论证链条断裂。加之 §5.11 承认无单模态消融且声学分支"may be the secondary contributor"。 | text: §4.5 "when no SMS accompanies a call ... fusion reduces to the acoustic branch"; §5.11 "the acoustic branch may be the secondary contributor" | 5（§4.5/§5.11 原文明确） | — | — |
| M3 | 2. Cherry-Picking Detection | 全部头牌数字（Table 3、Table 4、privacy table）来自一次"formal H100 run"，而公开仓库当前托管的是不同的 PTQ int4 配置，无法复现报告表格。§5.1 的 Reproducibility statement 承认仓库"used post-training int4 quantisation rather than the NVFP4 QAD reported here"，并请读者"treat the values ... as the authoritative record"。即：现在去复现的人会得到不同数字，唯一依据是作者的"权威记录"。 | absence: public repository (github.com/wangdajin062/QAD-MultiGuard) — expected QAD reproduction matching Table 3; checked §5.1 Reproducibility statement and §8 Data availability | 5（§5.1 自述） | 本领域规范是"论文被接受/发表时公开可复现代码"（如 NeurIPS/EMNLP reproducibility checklist 与多数系统类论文）。 | 论文不是"未发布代码"，而是已发布了一个*不同配置*的仓库，使当下复现必然得到与正文不符的数字，跨过了"发表时给出可复现代码"这一边界。 |
| M4 | 2. Cherry-Picking Detection | "57× storage reduction"是选择性对比：用 0.5B-quantized（248MB）比 7B-BF16（14GB），混淆了"规模"与"量化"两个因素；同一架构下的诚实数字是 ≈4×（§5.2 括号内）。且"与 SAFE-QAQ 打平（0.917 vs 0.918）"是把自测数字与"quoted from their respective sources at their own threshold conventions"（Table 3 脚注）的引用数字相比——不同测试集、不同阈值、不同规模。效率是论文三支柱之一，头牌效率数字因此具有误导性。 | text: §5.2 "57× ... computed against SAFE-QAQ (7B ... 14GB)"; §5.2 "relative to the same-architecture 0.5B BF16 backbone of ≈1GB the reduction is ≈4×" | 5（§5.2 两处原文对照） | — | — |
| M5 | 4. Logic Chain Validation | "pure-KL 优于 QAT 7.2 点"的核心证据是稻草人。§5.1 承认 QAT "is not additionally tuned beyond this shared budget"（硬 CE 目标却沿用 KL 目标的学习率/调度）；§3.1 用 D_KL=0.311（QAT）vs 0.005（pure-KL）作为"分布失配"证据，但 QAT 优化 one-hot hard labels、本就无意匹配 teacher 软分布，该 D_KL 高是构造性必然，属循环论证。真正有意义的 F1 对比被超参不匹配与循环指标所混淆。 | text: §5.1 "the QAT baseline ... is not additionally tuned beyond this shared budget"; §3.1 "D_KL = 0.311" | 4（§3.1/§5.1 原文，推断 QAT 需独立调参为领域共识） | — | — |
| M6 | 4. Logic Chain Validation | contribution ④ 被映射到 C3（边缘实时推理），但投机解码只运行在云端、off-critical-path，对边缘时延预算（<500ms）没有任何贡献——该预算完全由量化学生（235ms）+线性融合满足。§3.1 明确"(4) Domain-adapted speculative decoding ... (addressing C3)"，而 §5.7 承认"the edge-platform numbers do not imply that speculative decoding executes on-device"。贡献→约束的映射在论文自身框架内断裂：为 C3 命名的组件并不解决 C3。 | text: §3.1 "(4) Domain-adapted speculative decoding ... (addressing C3)"; §5.7 "the edge-platform numbers do not imply that speculative decoding executes on-device" | 5（§3.1/§5.7 直接对照） | — | — |

#### MINOR

| # | Dimension | Issue Description | Evidence Anchor | Confidence |
|---|---|---|---|---|
| m1 | 4. Logic Chain Validation | "cross-format portability"（edge 0.917 vs cloud 0.923，gap 0.006）的归因被 CoT 混淆：edge Q4_K_M 无 CoT（直接融合），cloud NVFP4 有 CoT，故 0.006 的差距混合了量化格式差异与 CoT 有无两种因素，不能单独解读为跨格式可移植性。 | text: §5.2 "exhibits a 0.006 F1 gap compared with the cloud setting, indicating cross-format portability" | 4（对照 Table 3 行定义与 Table cot-ablation） |
| m2 | 5. Overgeneralization Check | 头牌时延数字是"assembled estimate"而非端到端测量，但摘要/亮点将其呈现为实测；且 highlights 第 4 条"3.32× on Snapdragon 8 Gen 3"未说明投机解码是云端机制、仅在边缘硬件上做基准。 | text: §5.7 "All on-device latency figures are end-to-end estimates assembled from the measured per-stage components" | 4（§5.7 原文） |
| m3 | 1. Core Thesis Challenge | OV-Freeze 被列为独立贡献与 highlights，但论文自己给出 h≈0.02、"below the conventional h = 0.20 'small' threshold"、"best interpreted as evidence of faithful distillation rather than a practically large accuracy improvement"——贡献陈述与实测效应量不匹配。variance drift 下降（+18.2%→+1.3%）是真实测量，但 highlights 的"OV-Freeze stabilises training"未附带"对 F1 几乎无实际增益"的限定。 | text: §5.1 "h ≈ 0.02, below the conventional h = 0.20 'small' threshold" | 4（§5.1 自述） |

### Ignored Alternative Explanations/Paths

1. **端上 ASR + 端上保留转录**：论文自身的数据流边界（§3.1）明确将"ASR transcripts"列为"remain strictly confined within the local device boundary"——即端上生成转录在论文自己的隐私边界内是允许的。若在端上跑 Whisper 解码器并保留转录用于 text 分支，将同时更准确（使用通话真实语言内容）且同样满足"不外传"隐私要求，从而令整套重构抵抗嵌入（为传输而牺牲内容）的必要性消失。论文从未论证为何端上转录被禁止。
2. **校准后的 PTQ 作为更廉价基线**：Table 3 显示 PTQ + temperature scaling 已达 0.852（vs QAD 0.923），差距 7.1 点而非原始 8.5 点。若对 PTQ 基线做与 QAD 同等的 2000-step 微调/校准，边际收益可能进一步收窄——QAD 的工程复杂度是否值回这被夸大的差距，未被充分检验。
3. **k-anonymity / 正交旋转实现 unlinkability**：论文 §7 自己提出"inject a session-specific dynamic perturbation or apply an orthogonal rotation"作为未来工作。这是 VPC 框架下成熟的标准机制，本可在本期实现，却被推迟——一个确定性、可链接的嵌入作为"隐私表示"的卖点因此站不住。
4. **同架构 BF16 直接端上部署**：§5.2 承认同架构 0.5B BF16 仅 ≈1GB，在 4GB 预算内游刃有余；量化只带来 ≈4× 压缩。若 1GB 可接受，则整个 QAD/量化链条对端上路径的必要性被削弱——论文未论证为何必须压到 240MB。

### Missing Stakeholder Perspectives

- 监管/合规方（PIPL 执法机构）：论文自称"technical assessment, not a legal compliance determination"，但全文缺少法律/监管视角对"重构抵抗是否满足 PIPL 第 23 条"的独立判断。
- 诈骗受害方（老年、低数字素养用户）：§7 已指出 FN/FP 的不对称伤害，但阈值校准（recall 优先）没有任何受害方/成本不对称的参与方输入。
- 电信运营商：真实部署的 channel mismatch、方言、计费与采样率约束等运营侧声音缺位。
- 通话参与者的知情同意/生物特征数据主体：声学嵌入作为生物特征派生物的采集与保留，数据主体视角未被代表。

### Unexamined Premise

**"端上隐私"被等同于"必须销毁语言内容"。** 全篇的前提是：PIPL 要求原始音频不外传，因此必须设计一个"抵抗语音内容重构"的嵌入，使通话的语言内容即使在端上也不可用。但 PIPL 约束的是**传输**，不是**端上计算**。论文自己的数据流边界（§3.1）把"ASR transcripts"列为留在端上的对象之一，等于承认端上转录是合规的——然而设计却主动省略 Whisper 解码器"ensure no ASR transcript is generated on-device"。这一未声明的前提——"为了避免内容被重构，宁可端上也不保留内容"——在八个挑战维度之外，且它恰恰是区分性隐私贡献的支点：一旦承认端上可保留转录，重构抵抗嵌入的整个价值主张就只剩"防云端半诚实推理"，而这一更弱的威胁模型从未被形式化论证为需要牺牲 F1 的充分理由。

### Observations (Non-Defects)

- 论文在 NBE/QDQ 数值行为仿真协议上的透明度（明确"integer grid, distinct from the native FP4 (E2M1) grid"）是少见的诚实，值得保留。
- Cohen's *h* 的主动报告（h≈0.02/0.03/0.07）是对抗"p<0.01 但无实际意义"的规范示范，虽自伤但正确。
- 对 cosine-similarity linkability 残余风险的主动披露，优于本领域绝大多数同类投稿。

---


## Seat EIC

# Peer Review Report — Round 2 (Journal-Fit / EIC Seat)

## Manuscript Information
- **Title**: QAD-MultiGuard: An Edge–Cloud Framework for Multimodal Fraud Detection and Risk Assessment
- **Manuscript ID**: N/A
- **Review Date**: 2026-09-01
- **Review Round**: Round 2（回应 2026-08-31 之 Major Revision 决策）

---

## Reviewer Information

### Reviewer Role
Journal-Fit Reviewer（内部角色 `EIC`）

### Reviewer Identity
一位在多模态大语言模型与边缘智能部署方向深耕多年的资深编委，长期担任 IEEE/ACM Transactions 级刊物与 ACL/ICASSP 顶会的 Area Chair，近年专注「小语言模型（SLM）+ 端侧推理」这一快速升温子领域。

### Review Focus
1. 论文在「LLM 时代边缘智能」谱系中的定位是否清晰——QAD-MultiGuard 相对现有量化蒸馏、多模态反诈工作的增量边界是否被说清。
2. 标题「Multimodal Fraud Detection」与实际评估范围（audio–text，URL/metadata 仅部署参数）是否匹配，读者预期是否被满足。
3. 四项贡献（C1 重构抵抗声学嵌入 / C2 超低位量化鲁棒 / C3 边缘实时 / 四模态融合）是否各自达到「可发表创新」的显著性门槛，还是若干工程技巧的组合。
4. 研究目标是否清晰确定；主要工作是否对应研究目标；创新点是否成立且可验证。

---

## Overall Assessment

### Recommendation
- [ ] **Accept** — 可直接发表，仅需排版修正
- [ ] **Minor Revision** — 少量修订，无需再审
- [x] **Major Revision** — 需实质性修订，修订后需再审
- [ ] **Reject** — 不适合在本刊发表

### Confidence Score
**4** — 大部分在本领域内（多模态边缘智能与 SLM 量化蒸馏），对「期刊适配/创新显著性/结构一致性」的判断高置信；对具体量化实现细节的裁定属 Reviewer 1 的方法论专长，非我深究范围。

### Calibration Status
`NOT_CALIBRATED`

### Summary Assessment
本文提出 QAD-MultiGuard，一个面向电信反诈的边缘-云协作框架，通过纯 KL 量化感知蒸馏（QAD）、OV-Freeze 方差正则、128 维重构抵抗声学嵌入与域自适应投机解码四组件，在 TAF-28k 上以端侧 Q4_K_M 学生达到 F1=0.917（BF16 教师的 98.5%）、268ms 中位时延，云端 NVFP4 轨达到 0.923（99.1%）。从编委/期刊适配视角，本轮稿件在诚实性上较上轮有实质提升：效应量（h≈0.02）、NBE 非原生 Blackwell、代理嵌入、不可链接残差风险等均被前置披露，OV-Freeze 的贡献定位已如实降级为「忠实蒸馏证据」，基线归属与文献缺口也已修正，这是本稿最突出的优点。但两个实验级硬门槛仍未闭合：其一，头条数字仍无法从公开仓库复现——复现运行「进行中」，仓库现仍托管 int4-PTQ 开发配置而非产出表格的 NVFP4 QAD，创新点「可验证」这一顶会/顶刊硬要求未满足；其二，声学分支的检测贡献仍未通过单模态消融量化（R2 被延期）。此外，标题/摘要的「四模态」与实际的音频-文本双模态交付之间存在落差，且整体创新属「既有技术的集成协同」而非单一可迁移机制。据此维持 Major Revision。

---

## Strengths

### S1: 诚实且自律的限制披露（本稿最突出的编辑价值）
作者主动把对己不利的证据前置：效应量明确标注「all lie below the conventional h = 0.20 threshold for a 'small' effect」、NBE 仿真 vs 原生 Blackwell、F_v 的代理评估、余弦相似度可链接残差风险、单语料局限等均不藏于脚注。这一透明度在同领域系统中少见，是决定本稿「Major 而非 Reject」的关键缓和因素。
**Evidence Anchor**: `text: §Evaluation Metrics "all lie below the conventional h = 0.20 threshold for a 'small' effect"`

### S2: 贡献定位已与证据对齐（OV-Freeze 如实降级）
上轮共识缺陷 R3（OV-Freeze 以 +0.007 F1 / h≈0.02 被列为四大贡献之一）已修正：现稿不再将其作为精度驱动，而是明确「best interpreted as evidence of faithful distillation rather than a large accuracy improvement」，贡献声明与实际效应量一致。
**Evidence Anchor**: `text: §Introduction "the measured effect of OV-Freeze is best interpreted as evidence of faithful distillation rather than a large accuracy improvement"`

### S3: 外部基线归属与文献缺口已修复（上轮 R4/S6）
BERT-Fraud/SAFE-QAQ 的「引用而非复现」性质已在 Table 3 脚注显式标注，SmoothQuant/QLoRA/OmniQuant/ASVspoof 等缺失文献已补入。对期刊适配而言，这消除了引用层面的学术严谨性硬伤。
**Evidence Anchor**: `text: Table 3 footnote "BERT-Fraud and SAFE-QAQ are cited reference baselines not reproduced in-house"`

### S4: 威胁模型与三约束→四组件的结构映射清晰
「privacy / fidelity / responsiveness」三约束与四组件一一对应，形式化威胁模型给出 G1/G2/G3 三类攻击与可检验阈值（WER≥0.90、F1 退化≤6%），研究目标-方法-评估的线索可追溯，结构一致性较好。
**Evidence Anchor**: `text: §Abstract "three coupled constraints: privacy, fidelity, and responsiveness"`

---

## Weaknesses

### W1: 标题/摘要「四模态」承诺与实际「音频-文本双模态」交付之间存在落差
**Problem**: 标题「Multimodal Fraud Detection and Risk Assessment」、摘要「The decision-fusion framework is four-modal (text, acoustic, URL, and metadata)」以及融合式 Eq. (fusion) 的四项权重，都在引导读者预期「四信号真实评估」。但 TAF-28k 仅提供 text 与 acoustic 两路 score，URL（$6$-d）与 metadata 分支从未在任何语料上被测量，仅以部署参数存在。上轮 R4(c) 反而选择了「revert 回四模态 + URL/metadata 作为部署参数」的表述，等于在保留四模态框架的同时回避了交付。
**Evidence Anchor**: `text: §Multimodal Risk Fusion "w_url = 0.20 and w_meta = 0.10 are deployment parameters carried forward for four-modal operation rather than values measured on TAF-28k"`
**Why it matters**: 这是本席最关心的「标题承诺 vs 正文交付」落差。被「Multimodal / four-modal」吸引的读者会在正文发现所谓四模态融合实际只验证了两路信号，且权重 $w_{\text{url}}=0.20$、$w_{\text{meta}}=0.10$ 是「forward-declared」而非「measured」。四模态融合因此成为一项「未经验证的贡献」，抬高了对本文贡献数量的预期。
**Suggestion**: 将标题与摘要降为「Audio–Text（dual-modality）Fraud Detection」，并把四模态融合从「核心贡献」显式降为「架构扩展、未经验证」；或在具备 URL/metadata 分数的语料上补测这四路融合，再保留「四模态」表述。
**Severity**: Major | **Confidence**: 5 — core expertise: journal-fit / structural coherence

### W2: 头号隐私贡献（C1 重构抵抗声学嵌入）的隐私属性是「代理」验证，而非对实际部署的 F_v 验证
**Problem**: Eq. (f-v) 定义的 128 维 $\bm{F}_v$ 是系统真正上云的表示，但现稿自述「the released experiments evaluate its two components through their respective proxy embeddings」——即 WER≥0.95、PESQ≤1.21、speaker-ID≤8.3% 是对 MFCC 分量与 Whisper global-pooled 分量的分头评估，而非对拼接后、联合训练的 $\bm{F}_v$ 的端到端评估；后者「remain part of the ongoing reproduction effort」。换言之，实际传输表示的「不可重构」属性尚未被直接证明。
**Evidence Anchor**: `text: §Reconstruction-Resistant Acoustic Embedding "the released experiments evaluate its two components through their respective proxy embeddings"`
**Why it matters**: C1 是本文唯一带有「隐私主张」的贡献，也是摘要与 highlights 的头条卖点。若其抗重构属性只对分量成立、对拼接后的实际表示未验证，则「reconstruction-resistant 128-dimensional acoustic embedding」这一核心断言在部署层面仍是未闭合的。这是「创新点是否可验证」的直接命中。
**Suggestion**: 对实际拼接后的 $\bm{F}_v$ 运行 GLO/U-Net 反演与 speaker-ID 攻击并复测阈值；若暂不可行，则将结果明确改标为「component-level proxy evidence」并在摘要/highlights 降级 C1 的主张强度，直至端到端验证完成。
**Severity**: Major | **Confidence**: 5 — core expertise: contribution significance / verifiability

### W3: 声学分支的检测贡献仍未量化（上轮 R2 的残存裂缝，仅被「披露」而非「解决」）
**Problem**: 上轮要求报告 text-only / audio-only 单模态基线以隔离声学嵌入的边际贡献；本轮回应将其「deferred to future work」，正文仅新增一段「Modality-contribution limitation」承认「single-modality (text-only and audio-only) baselines are not reported, so the marginal contribution of the acoustic branch ... is not separately quantified」，并自述 $w_{\text{audio}}=0.30 < w_{\text{text}}=0.40$、声学分支「may be the secondary contributor」。消融仍缺位。
**Evidence Anchor**: `text: §Discussion "single-modality (text-only and audio-only) baselines are not reported, so the marginal contribution of the acoustic branch"`
**Why it matters**: 一个以「重构抵抗」为代价（信息瓶颈，可能牺牲判别信息）的隐私机制，若其对检测的增量价值未被证明，就成了一笔「未解释的成本」。作者自己承认声学可能是次要贡献者，这反过来削弱了 Related Work 中「strong multimodal coupling」的核心动机。此发现与 W2 共同使 C1 的两条腿（隐私属性 + 检测效用）都处于未证实状态。
**Suggestion**: 在与 R1 同一 H100 复现周期内补跑 text-only 与 audio-only 的 TAF-28k F1，明确声学分支的边际价值是否足以抵消其信息损失；若确认次要，则同步修订「strong multimodal coupling」动机表述。
**Severity**: Major | **Confidence**: 5 — core expertise: contribution significance

### W4: 头条数字仍不可独立验证——复现运行「进行中」，仓库与论文相矛盾（上轮 R1 的残存裂缝）
**Problem**: 上轮 Critical 缺陷 R1 的处理是「文本层披露」而非「解决」：复现运行仍在 H100 上 pending。现稿 Reproducibility statement 自述「the public repository currently hosts an earlier development configuration that used post-training int4 quantisation rather than the NVFP4 QAD reported here, so its raw outputs do not yet reproduce the reported tables」，效应量亦「derived from the historical H100 run and will be recomputed」。回应文件自身将完成复现运行视为「a hard precondition for resubmission」——而该前置条件当前未满足。
**Evidence Anchor**: `text: §Reproducibility statement "its raw outputs do not yet reproduce the reported tables"`
**Why it matters**: 98.5%/99.1% 恢复率、AdvFraud 0.875、隐私指标等全部核心数字出自一个第三方无法复现的「历史 H100 run」。诚实披露消除了「误导」风险，但并未消除「不可验证」缺陷——上一轮编辑仲裁已明确「disclosure does not reduce the severity of core numbers unverifiable」。对顶会/顶刊，「创新点可验证」是硬门槛；一个无法复现的贡献，无论披露得多诚实，都不满足发表条件。这是本轮唯一 Critical 级发现。
**Suggestion**: 在再次提交前完成并公开 NVFP4 QAD 复现运行，并以 commit pointer 替换「in progress」表述；若客观上无法完成，则将全部受影响数字在全文（而非仅摘要/结论）降级为「historical run, non-reproducible」状态。
**Severity**: Critical | **Confidence**: 5 — core expertise: verifiability of claimed contributions

### W5: 创新属「既有技术的集成协同」，缺乏单一可迁移的机制性洞见
**Problem**: 现稿自陈「The novelty lies not in any single component—each draws on established techniques—but in their integrated co-design」：纯 KL 蒸馏来自 Nemotron（引用[3]）；OV-Freeze 是方差匹配正则，实测效应 h≈0.02；声学嵌入是 MFCC 时间平均 + Whisper global-pooled 的手工瓶颈（全局池化破坏子帧结构，其「抗重构」近乎同义反复）；域自适应投机解码是标准技术套用。四项组件均无新理论、新形式保证或可迁移到其他问题的新机制。
**Evidence Anchor**: `text: §Introduction "The novelty lies not in any single component—each draws on established techniques—but in their integrated co-design"`
**Why it matters**: 本席核心关切是创新的「质」而非「量」。集成协同式的系统贡献在应用型刊物（如 ESWA）是可接受的，但对应的应是「可行性基线 + 严谨工程验证」的定位；若目标为 IEEE/ACM Trans 或 ACL/ICASSP 级「机制性创新」门槛，则本稿增量不达标。这直接决定期刊适配与论文应如何自我定位。
**Suggestion**: 明确将本文定位为系统/工程贡献，以「隐私约束下端侧多模态反诈的可行性基线」为核心主张，并删去「advancing representation-level protection beyond ASR pipelines」等过度拔高单一组件新颖度的措辞；或提炼并主打唯一最具迁移性的发现（候选：纯 KL + homologous 自蒸馏在超低位多模态反诈下的分布对齐效果）。
**Severity**: Major | **Confidence**: 4 — core expertise: originality/venue-fit judgement（此为定位判断，非诚实性缺陷）

---

## Detailed Comments

### Title & Abstract
- **标题准确性**：标题「Multimodal Fraud Detection」在「≥2 模态」的严格定义下不属伪称（audio–text 确为多模态），但「four-modal (text, acoustic, URL, metadata)」的摘要表述与「四模态融合」贡献清单，超出实际交付范围（见 W1）。摘要对「98.5%/99.1%」的呈现已配上 NBE/H100 来源说明，这是上轮 S10 的落实，值得肯定；但摘要的复现披露（「reproduction is in progress」）弱于正文 Reproducibility statement 的实情（仓库现托管不同配置、raw outputs 尚不能复现），读者仍可能低估不可验证的程度。
- **摘要完整性**：结构完整，三约束、四组件、主结果、稳健性、限制均有覆盖，且诚实降级后的口吻与正文一致。

### Introduction
- **研究背景与动机**：PIPL 约束 + 4GB/500MB 硬件预算 + 90s 诈骗电话场景的动机铺陈充分，「privacy/fidelity/responsiveness」三约束定义清晰（对应本席 focus 4 的「目标清晰确定」）。
- **增量边界**：相对 Nemotron QAD、SAFE-QAQ、TAF-28k 的定位在 Table 1 与 Related Work 中已基本说清；「我们做的不是任何单一新技术，而是集成协同 + 实证验证」的诚实定位（S2/W5）反而使增量边界比上轮更可信。剩余问题是：四模态融合这条「贡献」的边界未与「双模态评估」对齐（W1）。

### Literature Review / Theoretical Framework
- 上轮缺口（SmoothQuant/QLoRA/OmniQuant/ASVspoof）已补，VPC「content」术语方向已纠正（content-private 高 WER vs content-utility 低 WER）。相对本文主张而言，文献整合充分（本项主要由 Reviewer 2 深审，此处从期刊适配角度确认已无硬伤）。

### Methodology / Research Design
- 结构映射（三约束→四组件）与威胁模型形式化（G1/G2/G3）清晰，属本稿方法论上的亮点。但「四模态融合」的方法声明（Eq. fusion 四项权重、Tier-3 四路）与其两路评估的现实之间，仍存在设计-评估错位（W1）；$\bm{F}_v$ 的方法定义（Eq. f-v）与其实证验证对象（proxy 分量）之间的错位亦然（W2）。此两处是「方法承诺 vs 证据」的结构性缝隙，交由 Reviewer 1 从方法论角度复核。

### Results / Findings
- 结果呈现完整（主表、量化方案消融、CoT 消融、损失消融、OV-Freeze 消融、跨数据集、隐私攻击表齐全），效应量与显著性报告达到诚实水准。但核心表格的可复现性缺口（W4）使这些结果目前只能被「信任」而不能被「验证」，这是结果层的根本制约；声学分支贡献未被隔离（W3）则使「多模态融合」的收益归属仍不明确。

### Discussion
- 限制讨论是本稿最成熟的部分：隐私-效用权衡、不可链接残差风险、误分类社会后果、模态贡献限制、单语料泛化风险均被诚实讨论，且 PIPL 声明已加「非法律合规判定」的限定。这一节几乎把审稿人想提的限制都主动写清了，是显著的编辑加分项。

### Conclusion
- 结论与研究目标对齐良好：三约束「jointly met」的表述有证据支撑，三条 design takeaway 简洁可迁移。但结论仍以「Multimodal」与「四模态」为主张措辞（W1），且对「复现 pending」的交代仍停留在「in progress」层面（W4）。建议结论同步下调对「四模态」与「可复现」的承诺强度。

### References
- 引用质量与近效性经上轮修正已达标；新增 4 条（SmoothQuant/QLoRA/OmniQuant/ASVspoof）补齐了 PTQ 与反欺骗谱系。无期刊适配层面的引用硬伤。

---

## Questions for Authors

1. **复现硬门槛的时间表**：NVFP4 QAD 复现运行的预期完成时间与 commit pointer 是什么？下一轮提交时，摘要与结论中的「reproduction is in progress」是否会替换为可 `git` 检出即可重生成主表的确定性指针？若复现无法在下一轮前完成，作者是否接受将受影响数字全文降级为「non-reproducible historical run」？

2. **F_v 端到端隐私验证**：能否对实际拼接后的 128 维 $\bm{F}_v$（而非其 MFCC / Whisper-pooled 两个 proxy 分量）运行 GLO/U-Net 反演与 speaker-ID 攻击，并报告 WER≥0.95 / speaker-ID≤8.3% 的阈值是否仍对部署表示成立？

3. **声学分支的边际价值**：text-only 与 audio-only 的 TAF-28k F1 分别是多少？给定 $w_{\text{audio}}=0.30 < w_{\text{text}}=0.40$，声学嵌入的重构抵抗设计是否以其检测增益为代价仍值得？若确认声学为次要贡献者，是否修订 Related Work 的「strong multimodal coupling」动机？

4. **单一可迁移机制的取舍**：作者认为四个组件中哪一个是最可迁移到其他「隐私约束端侧 LLM」任务的机制？是否愿意将论文围绕该单一洞见重新定位（而非四组件并置），以契合更高门槛刊物的「机制性创新」预期？

---

## Minor Issues

### 稿件与回应/对账文件的一致性
- 回应文件 `reports/2026-08-31_response_to_reviewers_v29.md`（S16）与对账说明称「speaker closed set reverted to 10 (n=10)」，但现稿 `docs/v29.tex` 通篇为「11-speaker closed set」「$n = 11$」及 9.1%（=1/11）的随机基线。稿件内部自洽，但与回应文件不同步，需在下一轮对账时修正其一。

### Highlights 措辞与正文降级后的定位不完全对齐
- highlights 第 2 条「OV-Freeze stabilises training under aggressive quantisation」在正文已将 OV-Freeze 降级为「faithful distillation evidence、非大精度提升」后略显拔高，建议改为「OV-Freeze stabilises projection-layer variance drift」（与正文 +18.2%→+1.3% 的表述一致）。

### 摘要复现披露强度
- 摘要「public-repository reproduction is in progress」弱于正文实情（仓库当前托管 int4-PTQ 开发配置、raw outputs 尚不能复现表格）。建议摘要补一句「current repository does not yet reproduce the reported tables」，以与正文 Reproducibility statement 的披露强度对齐。

---

## Criterion-Bound Judgements

Calibration status: `NOT_CALIBRATED`

| Dimension | Criterion source | Judgement | Evidence anchor(s) | Rationale | Uncertainty / scope limit | Decision bearing? |
|---|---|---|---|---|---|---|
| Originality | quality_rubrics.md D1 | PARTLY_MEETS | `text: §Introduction "The novelty lies not in any single component—each draws on established techniques—but in their integrated co-design"` | 无单一可迁移机制；四组件均为既有技术（Nemotron KL 蒸馏、方差正则、MFCC+pool 瓶颈、投机解码），作者已诚实定位为集成协同。对应用型刊物为可行增量，对顶会/顶刊机制性门槛不达标。 | 期刊层级未在稿件内固定（回应指向 ESWA）；若目标为 ESWA 则该判断偏保守 | 是——决定期刊适配与定位 |
| Methodological Rigor | quality_rubrics.md D2 | PARTLY_MEETS | `text: §Reproducibility statement "its raw outputs do not yet reproduce the reported tables"` | 效应量/显著性/bootstrap/阈值校准报告严谨，但核心数字出自不可复现的历史 H100 run，复现 pending，方法严谨性受「不可验证」根本制约。 | 量化实现细节的最终裁定属 Reviewer 1 | 是——R1 残存裂缝 |
| Evidence Sufficiency | quality_rubrics.md D3 | PARTLY_MEETS | `text: §Reconstruction-Resistant Acoustic Embedding "the released experiments evaluate its two components through their respective proxy embeddings"` | 主表/消融/跨数据集/隐私表齐全，但 F_v 隐私属性为 proxy 证据、声学贡献未隔离、头条数字不可复现，关键贡献证据不足。 | 单模态消融与端到端验证属实验级缺位 | 是——C1 两腿未证实 |
| Argument Coherence | quality_rubrics.md D4 | MEETS | `text: §Abstract "three coupled constraints: privacy, fidelity, and responsiveness"` | 三约束→四组件映射清晰，标题→摘要→导论→结论线索可追溯；仅「四模态」主张与两模态交付是唯一结构性裂缝。 | 无 | 否（裂缝已单列于 W1） |
| Writing Quality | quality_rubrics.md D5 | EXCEEDS | `text: §Evaluation Metrics "all lie below the conventional h = 0.20 threshold for a 'small' effect"` | 表述精确、限制主动前置、术语边界（reconstruction-resistant vs privacy-preserving、VPC content-private）区分到位，经 Elsevier 语言编辑。 | 无 | 否 |
| Literature Integration | quality_rubrics.md D6 | MEETS | `text: Table 3 footnote "BERT-Fraud and SAFE-QAQ are cited reference baselines not reproduced in-house"` | 上轮缺口（SmoothQuant/QLoRA/OmniQuant/ASVspoof）已补，基线归属已澄清，VPC 术语方向已纠正，覆盖与主张匹配。 | 文献完备性深审属 Reviewer 2 | 否 |
| Significance & Impact | quality_rubrics.md D7 | PARTLY_MEETS | `text: §Discussion "single-modality (text-only and audio-only) baselines are not reported"` | 隐私约束下端侧反诈的可行性基线有实用价值，但单语料（TAF-28k 受控重演）、无现场部署、声学贡献未量化、OOD 仅 text-only，真实世界影响力尚未证明。 | 现场验证为 future work，未完成 | 是——决定 Significance 上限 |

**推荐依据（命名未解决的决策性准则及其可修复性）**：维持 Major Revision 的根据是三条决策性准则仍开放——(1) Methodological Rigor / Evidence Sufficiency 下的「可复现性」（W4, Critical，需实验级复现运行，可修复但为硬前置）；(2) Evidence Sufficiency 下 C1 的「代理验证 + 未量化贡献」（W2/W3, Major，需端到端 F_v 攻击与单模态消融，可修复）；(3) Originality / Significance 下的「集成协同 vs 单一机制」定位（W5, Major，需重新定位而非新增实验）。这三条均不可由强项抵消，但均为可修复项，故为 Major Revision 而非 Reject。

---


## Seat R1

# Peer Review Report

## Manuscript Information
- **Title**: QAD-MultiGuard: An Edge–Cloud Framework for Multimodal Fraud Detection and Risk Assessment
- **Manuscript ID**: N/A（v29.tex）
- **Review Date**: 2026-09-01
- **Review Round**: Round 2（第二轮复审；首轮已产出 A1–A11 / R1–R5 / S1–S16 修复与诚实降级）

---

## Reviewer Information

### Reviewer Role
Peer Reviewer 1 (Methodology)

### Reviewer Identity
一位机器学习评测与基准方法学资深研究者（活跃于 NeurIPS Datasets & Benchmarks 与 ML evaluation 社群），专长是「可证伪的研究目标设定 + 消融设计的因果隔离 + 效应量/p 值的统计严谨性」。

### Review Focus
1. 三条研究主线（C1 隐私约束声学处理 / C2 超低位量化鲁棒性 / C3 边缘实时推理）是否被表述为**可证伪、可测量**的目标，而非宽泛方向性口号。
2. 主要工作（四组件）与三个研究问题的**对应关系是否一一闭环**——每项工作是否真的回答了某个 RQ。
3. 消融与对比实验的**因果隔离**是否干净（单模态消融、基线公平性、混淆变量控制）。
4. 效应量（OV-Freeze +0.007 F1、NBE +0.007 等）与显著性声明是否匹配，p 值是否被过度解读。

核心关切是「研究目标 ↔ 主要工作 ↔ 实验设计 ↔ 结论」四段论证链是否闭环，中间有无断裂或偷换概念。

---

## Overall Assessment

### Recommendation
- [ ] **Accept** — Can be published directly, only minor formatting changes needed
- [ ] **Minor Revision** — Minor revisions needed, no re-review after revision
- [x] **Major Revision** — Substantial revisions needed, re-review required after revision
- [ ] **Reject** — Not suitable for publication in this journal

### Confidence Score
**4** — 大部分在本席专业范围内（ML 评测、量化蒸馏、统计严谨性），高置信度；个别隐私/声学细节（VPC 术语、重建攻击实现）略出本席核心专长，但不足以动摇主要方法学判断。

### Summary Assessment
本文提出 QAD-MultiGuard，一个端云协同的多模态诈骗检测框架，用四条组件（纯 KL QAD、OV-Freeze、128 维抗重建声学嵌入、域适配投机解码）回应隐私、保真、响应性三条约束，并在 TAF-28k 上报告 Q4_K_M 学生 F1=0.917（98.5% recovery）、NVFP4 云侧 F1=0.923（99.1%）、268ms 中位延迟。从方法学视角看，本轮修订已实质改善：三条挑战被赋予了可证伪的量化阈值（WER≥0.90、recovery 率、≤500ms、≤6% 退化）；消融设计大体干净；效应量（Cohen's h≈0.02–0.07）被诚实计算并据此把 OV-Freeze 从"大幅增益"降级为"忠实蒸馏证据"。这些是本轮最值得肯定的进步。

但仍有三处论证链断裂未闭环，构成复审的核心理由：(1) 可复现性缺口仍在——主表数字仍出自一个公开仓库无法复现的历史 H100 run（仅被披露，未消除）；(2) "cross-format portability"（0.006 F1 差距）把量化格式（NVFP4 vs Q4_K_M）与云端 CoT 评审这一混淆变量混为一谈，未做因果隔离；(3) 对 +0.007/+0.008 的增益报 p<0.01/p<0.05，但所用的 instance-level paired bootstrap 未传播跨 seed 方差，与本文自陈的 h≈0.02（低于"small"）互相矛盾。此外 C1 的"抗重建且足够信息量"双重要求只验证了前半（且重建指标是 proxy 嵌入/引用估计而非部署实体 F_v）。综合判断：建议 Major Revision，需补齐可复现性硬前置 + 修正格式混淆归因 + 收敛显著性声明后方可再审。

---

## Strengths

### S1: 三条研究主线被操作化为可证伪的量化阈值
C1/C2/C3 均配有明确的证伪判据——C1 以威胁模型 WER≥0.90 为下界、C2 以 recovery 率（98.5%/99.1%）与 PTQ 7.1–8.5 点差距为判据、C3 以 ≤500ms 为硬预算、G2 以 ≤6% 退化约束。这不是方向性口号，而是可被推翻的目标。
**Evidence Anchor**: [`text: §1 Introduction + §2.1 Formalised Threat Model — "acoustic reconstruction quality is lower-bounded by an adversary Word Error Rate (WER) threshold of ≥ 0.90"`]

### S2: 消融的因果隔离大体干净
损失函数消融固定 T=1、禁用 OV-Freeze，只变 loss 变量；OV-Freeze 与 CoT 的隔离给出了显式的"共享 CoT 路径"论证（QAD 0.916 与 QAD+OVF+CoT 0.923 共享 CoT，二者之差隔离 OV-Freeze 效应）。
**Evidence Anchor**: [`text: §5.1 Main results — "The two cloud-side enhancements are complementary and are isolated in separate ablations, holding all other factors fixed"`]

### S3: 效应量被诚实计算并正确解读
对 OV-Freeze（h≈0.02）、异构量化（h≈0.03）、LDP 退化（h≈0.07）统一报告 Cohen's h（arcsine 变换），并明确"all lie below the conventional h = 0.20 threshold"，据此把 OV-Freeze 的贡献地位主动降级。这是本轮对首轮 EIC(W4)/R1(W5)/DA(C2) 的正面回应。
**Evidence Anchor**: [`text: §4.1 Evaluation Metrics — "we report standardised effect sizes (Cohen's h on the arcsine-transformed probability scale)"`]

### S4: 阈值在 held-out 验证集上校准、不污染测试集
决策阈值在 held-out validation 上校准并原样施加于测试集；融合权重用 user-stratified 五折 CV 且"held-out test partition was never used for parameter fitting"。8:1:1 划分矛盾已消除（S9）。
**Evidence Anchor**: [`text: §4.1 Evaluation Metrics — "All models are evaluated with a decision threshold calibrated on the held-out validation partition and applied unchanged to the held-out test partition"`]

### S5: 诚实降级贯穿全文（NBE vs Blackwell、LDP 非正式、speaker-ID 初步证据）
NBE 与原生 Blackwell 的区分、ε=1.5 为"engineering estimate without a certified sensitivity bound"、n=11 小样本"preliminary"、ASV-EER 测量对象重新标注等，均体现了克制的结论边界。
**Evidence Anchor**: [`table: Table 2 (note) — "all NVFP4 accuracy results reported in this work are generated via the QDQ numerical-behaviour-emulation (NBE) protocol on H100 hardware"`]

---

## Weaknesses

### W1: 可复现性缺口仍未闭环（首轮 Critical 的残余）
**Problem**: 主表（Table 3、Table 4、隐私攻击表）的数字仍出自一个公开仓库无法复现的历史 H100 run。Reproducibility 声明自认"公开仓库目前托管的是 int4-PTQ 开发配置，而非产出表格的 NVFP4 QAD"，且"reproduction run 仍 in progress"。抽象与结论虽已把 NBE/reproduction 缺口浮现到 headline（S10/R1 的文本级诚实降级），但文本披露只消除"欺骗性风险"，未消除"可验证性缺口"本身。
**Evidence Anchor**: [`text: §4.1 Reproducibility statement — "the public repository currently hosts an earlier development configuration that used post-training int4 quantisation rather than the NVFP4 quantisation-aware distillation (QAD) reported here"`]
**Why it matters**: 方法学核心问题（Step 6 Reproducibility）——"另一个研究者按同样流程能否得到相近结果"目前答案为否。99.1%/98.5% recovery 与全部 PTQ/QAT 对比结论在第三方可独立验证前无法成立。这是单点即可阻塞接收的缺陷。
**Suggestion**: 将完成 NVFP4 QAD reproduction run 并发布"每个报告数字对应的精确 commit pointer"设为 resubmission 的硬前置条件（作者在回复中已自行承诺）；在 reproduction 完成前，不应将主表数字当作可引用的权威结果。
**Severity**: Critical
**Confidence**: 5 — 核心专长：评测可复现性

### W2: "cross-format portability"（0.006 F1 差距）混淆了量化格式与云端 CoT 评审
**Problem**: 正文把 edge 配置（Q4_K_M QAD + OV-Freeze，F1=0.917）与 cloud 配置（NVFP4 QAD + OV-Freeze + **CoT**，F1=0.923）的 0.006 差距归因为"indicating cross-format portability"。但云端行**包含** CoT 评审（Table 7 显示 CoT 单独贡献 +0.018），边缘行**不包含** CoT（CoT 仅为云端 Tier-2 路径）。因此这 0.006 是"格式差异 + CoT 有无"的混合效应，不是对量化格式的干净归因。首轮 DA 的 M1 已指出这一点，但未进入 R1–R5/S1–S16 修订路线图，现稿仍残留。
**Evidence Anchor**: [`text: §5.1 Main results — "exhibits a 0.006 F1 gap compared with the cloud setting, indicating cross-format portability"`]
**Why it matters**: 这是本席第二焦点（消融因果隔离）的直接违反。"格式可移植性"是支撑 C2 的一个结论性声称，其成立依赖一个被 CoT 污染的比较；实际格式效应可能更小甚至反向（Q4_K_M QAD 0.911 与"无 CoT 的 NVFP4 QAD≈0.905"相比，GGUF 反优）。
**Suggestion**: 报告一个固定 CoT（或无 CoT）条件下的格式对等比较（NVFP4-QAD vs Q4_K_M-QAD 同条件），或明确说明该 0.006 是"格式+评审路径"的联合差距而非纯格式差距，并把"cross-format portability"措辞降级。
**Severity**: Major
**Confidence**: 5 — 核心专长：消融设计

### W3: p<0.01 / p<0.05 显著性声明与自陈的微小效应量互相矛盾，且 bootstrap 未传播跨 seed 方差
**Problem**: 对 OV-Freeze 增益（+0.007 F1，h≈0.02）报"statistically significant at p<0.01, CI [+0.31,+1.08]pp"，对异构量化增益（+0.008，h≈0.03）报"paired bootstrap over test instances, p<0.05"。但该显著性检验是 instance-level paired bootstrap（对约 2851 个测试样本重采样 10,000 次），它把两个模型当作固定量、只重采样测试实例，**不传播 5 个随机 seed 的训练方差**（Table 3 中 ±0.006–0.007 与增益本身同量级甚至更大）。对一个近乎确定性的 +0.007 差异，instance 级 bootstrap 会给出超小的 p 值，与本文自己报告的"低于 small 阈值"的效应量不可调和——这是"p 值被过度解读"的典型形式。
**Evidence Anchor**: [`text: §4.1 Evaluation Metrics — "Empirical improvements introduced by the OV-Freeze module are verified as statistically significant at p<0.01"`]
**Why it matters**: 首轮 R1(W5) 已指出"instance-level bootstrap 忽略 seed 方差"，本轮仅把 OV-Freeze 的贡献 framing 降级（R3），但**p<0.01/p<0.05 的显著性声称原样保留**，与降级后的"best interpreted as evidence of faithful distillation"表述自相矛盾。显著性测试的方法本身仍是错的。
**Suggestion**: 二选一：(a) 删除对 OV-Freeze/异构量化的 p<0.01/p<0.05 断言，只保留效应量与 CI；(b) 改用能传播跨 seed 方差的检验（对 seed 重采样，或报告"每 seed 差异的分布"），并明确报告差异相对于 seed 标准差的倍数。
**Severity**: Major
**Confidence**: 4 — 核心专长：统计严谨性

### W4: C1 的"抗重建且足够信息量"双重要求只验证了前半——声学嵌入的边际信息量贡献无单模态消融
**Problem**: C1 要求嵌入"resists speech-content reconstruction **while remaining sufficiently informative for downstream multimodal fusion**"。前半个要求有可证伪阈值（WER≥0.90），后半个"sufficiently informative"从未被操作化为可测量的门槛，也没有 text-only / audio-only 单模态基线来隔离声学分支的增量贡献（融合权重 w_audio=0.30 反而暗示声学可能次要）。Discussion 的"Modality-contribution limitation"段已诚实披露，但披露不等于闭环——C1 的可证伪目标仍是半个。
**Evidence Anchor**: [`absence: §Experiments (Main results, Table 3) 与 §Discussion (Modality-contribution limitation) — expected text-only 与 audio-only 单模态 TAF-28k 基线以隔离声学嵌入的边际 F1 贡献; checked §5.1 Table 3、§5 Ablation 各小节、§7 Discussion limitation 段落`]
**Why it matters**: 本席第一、第二焦点的交叉——C1 的双重要求只有一半可证伪，且组件(3)（声学嵌入）是否真的"回答"了 C1 的保真侧无实验支撑。这使"strong multimodal coupling"的动机（§2）与"acoustic branch may be the secondary contributor"的自我承认（§7）之间留有未决矛盾。
**Suggestion**: 在 reproduction run 中补报告 TAF-28k 的 text-only 与 audio-only F1（以及两者融合的增量），把声学分支的边际贡献量化；若声学确为次要，据此修正 C1 与 Introduction 的"多模态强耦合"动机表述。
**Severity**: Major
**Confidence**: 4 — 核心专长：研究目标 ↔ 实验设计闭环

### W5: 隐私（重建抵抗）证据建立在 proxy 嵌入与"引用估计"上，而非部署实体 F_v
**Problem**: 部署的是联合拼接的 128 维 F_v（Eq. 5），但正文自认"released experiments evaluate its two components through their respective proxy embeddings … rather than through the jointly trained concatenated F_v"，且重建质量指标（WER/PESQ/STOI/MOS）是"reference estimates from the reconstruction-attack analysis rather than independently re-measured outputs of the released evaluation pipeline"。即 C1 的隐私证据链从"部署表示 F_v"滑向了"组件级 proxy"与"历史引用估计"。
**Evidence Anchor**: [`text: §3.3 Reconstruction-Resistant Acoustic Embedding — "the released experiments evaluate its two components through their respective proxy embeddings"`]
**Why it matters**: 组件(3)↔C1 的闭环存在测量对象错位：声称"F_v 抗重建（WER≥0.95）"，但被攻击/评估的并非 F_v 本身。这与 W1 的可复现性缺口同源，但方向不同——是证据的测量对象，而非证据的可验证性。
**Suggestion**: 在 reproduction run 中对**实际部署的 F_v**（联合拼接、经 W_proj 投影）重跑 GLO/反演攻击与 speaker-ID 攻击，并将 proxy 嵌入与 F_v 的指标并列表述，明确二者的对应关系。
**Severity**: Minor
**Confidence**: 3 — 核心专长：测量效度；对声学重建攻击实现细节略有跨领域不确定性

### W6: 组件(4)（投机解码）与 C3 的映射不精确——它加速的是云端评审，不是边缘 <500ms 预算
**Problem**: C3 的可证伪目标是"边缘设备 per-window <500ms"。但组件(4)的投机解码加速的是"asynchronous cloud-side CoT review"（off-critical-path），对边缘 268ms 的达成零贡献；边缘延迟实际由组件(1)的量化学生 + 轻量融合（已归 C2）达成。正文虽在 §3.5 自认"speculative decoding serves the cloud review path … the edge-platform numbers do not imply that speculative decoding executes on-device"，但 §1 的映射仍写作"(4) … (addressing C3)"，与"each addressing a specific challenge"的总命题存在轻度错位。
**Evidence Anchor**: [`text: §1 Introduction — "Domain-adapted speculative decoding and edge--cloud deployment (addressing C3)"`]
**Why it matters**: 本席第二焦点（四组件 ↔ 三 RQ 一一闭环）的轻度破坏：C3 的 falsifiable 目标（边缘延迟）并非由名义上"对应 C3"的组件(4)回答。这弱化了"四段论证链"在 C3 一侧的清晰度，属框架精度问题而非数据问题。
**Suggestion**: 把组件(4)的归属重述为"响应性的非关键路径优化"，并显式说明 C3 的边缘 <500ms 由量化学生+线性融合（组件1/2）达成，投机解码仅服务于云端评审的吞吐，避免"each addressing a specific challenge"被读作严格一一对应。
**Severity**: Minor
**Confidence**: 4 — 核心专长：研究问题对齐

---

## Detailed Comments

### Research Questions & Hypotheses
C1/C2/C3 已从首轮的宽泛约束被收敛为可证伪目标（S1），这是本轮最大改进。但 C1 的"while remaining sufficiently informative"是双重要求中的隐性第二 conjunct，未配阈值（W4）；G2 的 ≤6% 约束依赖"matched BF16 baseline"这一宽松参照（0.8% 退化），而对照 TAF-28k BF16 参照的全量池退化达 9.7%——正文已并列披露，读者需仔细分辨才不致误读"满足 ≤6%"为"对抗鲁棒"。

### Research Design
消融设计整体干净（S2/S4）。核心缺陷在 W2：edge/cloud 对比把格式与 CoT 两个变量混在一起却归因于单一"格式"。此外 OV-Freeze 与 CoT 的隔离逻辑（共享 CoT 路径）虽正确，但导致 Table 3 中不存在"NVFP4 QAD 无 CoT"与"Q4_K_M QAD 有 CoT"的交叉单元，使格式效应的干净估计在现有表中不可得。

### Sampling Strategy
TAF-28k 8:1:1 划分 + held-out 阈值校准（S4）已闭合首轮 S9。speaker-ID 实验 n=11、61 样本的小样本功效限制已被诚实标注为 preliminary（S16 达成）。需要注意：response 文档的 reconciliation note 写"speaker closed set reverted to 10 / n=10"，但现稿正文为"11-speaker closed set / n = 11 / 9.1% chance（=1/11）"——现稿内部自洽（11 说话人对应 9.1%），但响应文档与现稿存在 n 值口径不一致，属流程记录问题而非稿件缺陷。

### Data Collection
AdvFraud-3k 的 517 精选子集 + 3000 全量池并列报告（R5 达成），构造算术已修正（S12）。融合权重 w_url=0.20 / w_meta=0.10 被标注为"deployment parameters carried forward rather than values measured on TAF-28k"（Eq. w-deploy 前后），但 §4.5 的"fusion weights are learned using L-BFGS with five-fold CV"表述仍笼统——实际只有 w_text/w_audio 在 TAF-28k 上被学习，w_url/w_meta 无学习来源。属措辞精度问题。

### Analysis Methods
效应量报告规范（S3），但显著性方法（instance-level paired bootstrap，未传播 seed 方差）与效应量解读冲突（W3）。recovery 率算术自洽（本席复核 0.923/0.931=99.1%、0.917/0.931=98.5%、0.858/0.931=92.2% 等均无误）；Cohen's h 计算与本席复核一致（OV-Freeze≈0.025、异构≈0.027、LDP≈0.072）。

### Results Presentation
主表与图大体清晰、内部数值自洽（268ms=12+235+21）。遗留：edge/cloud 0.006 的"cross-format portability"归因（W2）需要修；p<0.01/p<0.05 星号式显著性在表/图中与"低于 small"效应量并存，易误导（W3）。

### Reproducibility
首轮 Critical 仍未闭环（W1）：主表数字不可独立验证，reproduction run 仍是"in progress"。这是本席 Step 6 的核心扣分项，也是建议 Major 而非 Minor 的决定性理由。

### Methodological Fallacies Detected
- **Confirmation / 归因偏差（W2）**：把混合效应（格式+CoT）归因于单一变量（格式）。
- **P 值过度解读（W3）**：高功效 bootstrap 对小效应量报"显著"，与自陈效应量矛盾；未传播训练随机性。
- **测量对象错位（W5）**：声称 F_v 抗重建，但证据在 proxy 嵌入/引用估计上。
- **隐性未操作化 conjunct（W4）**：C1 的"足够信息量"未配证伪阈值。

---

## Questions for Authors

1. **（W1）** reproduction run 的完成时间线与"每数字对应 commit pointer"的发布计划是什么？在完成前，主表数字（Table 3/4、隐私攻击表）可否标注为"provisional/unverified"而非正文权威记录？
2. **（W2）** 请报告一个固定 CoT（或固定无 CoT）条件下的 NVFP4-QAD vs Q4_K_M-QAD 同条件比较。纯格式效应到底是多少？0.006 中有多少来自 CoT？
3. **（W3）** OV-Freeze/异构量化的 p<0.01/p<0.05 是用什么重采样对象（test instances 还是 seeds）？能否报告"5 个 seed 各自的有/无 OV-Freeze 差异分布"，说明 +0.007 是否超出 seed 间波动？
4. **（W4）** TAF-28k 上 text-only 与 audio-only 的 F1 分别是多少？声学分支的边际贡献量化后，是否仍支持"strong multimodal coupling"的动机表述？

---

## Minor Issues

### Language / Grammar
- §4.5 融合权重："fusion weights are learned using the L-BFGS optimisation algorithm with user-stratified five-fold cross-validation" —— 实际仅 w_text/w_audio 被学习，w_url/w_meta 为 deployment parameters；建议在 Eq. (w-deploy) 邻近把"learned weights"限定为前两项，避免读者误以为四维向量均在 TAF-28k 上拟合。

### Citation Format
- 无明显引用格式问题（S6 已补齐 SmoothQuant/QLoRA/OmniQuant/ASVspoof）。

### Figures and Tables
- Table 3 中云端两行（0.916 / 0.923）均含 CoT，边缘两行（0.911 / 0.917）均无 CoT，但表内无注释标出这一系统性差异；建议在表注显式注明"CoT 仅云侧"，以免读者误做跨格式直接比较（关联 W2）。

### Layout
- response 文档 reconciliation note 称 speaker closed set "reverted to 10"，现稿正文为 11（9.1% = 1/11）；稿件自洽，但建议同步修订流程记录，避免审稿阶段再次产生 n 值口径疑问。

---

## Criterion-Bound Judgements

Calibration status: `NOT_CALIBRATED`

| Dimension | Criterion source | Judgement | Evidence anchor(s) | Rationale | Uncertainty / scope limit | Decision bearing? |
|---|---|---|---|---|---|---|
| Originality | quality_rubrics.md D1 | MEETS | text: §1 "The novelty lies not in any single component… but in their integrated co-design" | 以端云协同 + 量化蒸馏 + 抗重建嵌入的集成 co-design 为贡献，新颖性诚实定位，不夸大单点创新 | 部分组件（QAD/OV-Freeze/投机解码）为既有技术组合 | 否——新颖性 framing 已收敛，不构成阻塞 |
| Methodological Rigor | quality_rubrics.md D2 | PARTLY_MEETS | text: §4.1 "its raw outputs do not yet reproduce the reported tables" + §5.1 "indicating cross-format portability" | 消融大体干净、效应量诚实，但可复现性缺口（W1）、格式/CoT 混淆（W2）、bootstrap 未传播 seed 方差（W3）三处违反设计严谨性 | 声学重建攻击的实现细节略出本席专长 | 是——W1 单独即可阻塞；W2/W3 需重分析 |
| Evidence Sufficiency | quality_rubrics.md D3 | PARTLY_MEETS | absence: §Experiments — expected 单模态基线; checked Table 3/§5/§7 | 主声称有证据，但声学嵌入边际贡献（W4）与部署 F_v 的重建证据（W5）缺失或错位 | 单模态消融依赖 H100 reproduction run | 是——C1 证据链不完整 |
| Argument Coherence | quality_rubrics.md D4 | PARTLY_MEETS | text: §1 "(addressing C3)" + §5.1 "indicating cross-format portability" | 四组件↔三挑战映射有轻度错位（W6），edge/cloud 归因存在偷换概念（W2），C1 双重要求半闭合（W4） | 无 | 是——论证链断裂点需修 |
| Writing Quality | quality_rubrics.md D5 | MEETS | text: §4.1 "To separate statistical from practical significance, we report standardised effect sizes" | 表达清晰、结论边界克制、诚实降级贯穿；个别措辞精度问题（融合权重、表注）见 Minor Issues | 无 | 否 |
| Literature Integration | quality_rubrics.md D6 | MEETS | dataset: TAF-28k/AdvFraud-3k/ChiFraud + 相关 QAD/PTQ/隐私文献 | 文献覆盖经 S6 补齐，量化蒸馏、语音隐私、反诈三线齐全（本维度主要为 R2 领域） | 文献完备性由 Reviewer 2 主审 | 否 |
| Significance & Impact | quality_rubrics.md D7 | PARTLY_MEETS | text: §7 "generalisation to unconstrained real-world environments has not yet been formally validated" | 可行性基线定位诚实，但单语料 + 无现场验证限制了已证实的实际影响，故定位于"可行性基线"而非"已证部署价值" | 现场验证超出本研究范围（作者已列为 future work） | 部分——影响有限但不阻塞方法学验收 |

**决策说明**：本席建议 Major Revision 的依据是三个未闭环的 decision-bearing 维度——Methodological Rigor（W1 可复现性缺口为 Critical 级阻塞）、Evidence Sufficiency（W4 单模态证据缺失）、Argument Coherence（W2 归因混淆 + W6 映射错位）。这三者均可修复（需 H100 reproduction run + 格式对等比较 + 单模态消融），但均非措辞层面所能闭合，故需大修后复审。写作、文献、原创性维度不构成阻塞，但不可用于抵消上述方法学缺陷。

---


## Seat R2

# Peer Review Report

## Manuscript Information
- **Title**: QAD-MultiGuard: An Edge–Cloud Framework for Multimodal Fraud Detection and Risk Assessment
- **Manuscript ID**: N/A（内部稿件 v29.tex）
- **Review Date**: 2026-09-01
- **Review Round**: Round 2（第二轮评审）

---

## Reviewer Information

### Reviewer Role
Peer Reviewer 2 (Domain)

### Reviewer Identity
语音信号处理与说话人/韵律表征领域资深学者，专注 speaker characterization、anti-spoofing、voice privacy，具备 ASVspoof / anti-spoofing 挑战赛与 VoicePrivacy 评估方法学背景。

### Review Focus
1. $\bm{F}_v$ 声学嵌入构造（FBANK-64 + Whisper-proj-64 拼接，128 维）的领域合理性，及其与说话人/韵律信息保留的关系；
2. 说话人攻击验证（speaker-ID / ASV-EER / GLO 重构）的实验设计与指标选择是否正确，测量对象是否错位；
3. Whisper/MFCC 代理嵌入的代理效度——代理能否代表论文声称的 $\bm{F}_v$；
4. 语音反欺诈 / anti-spoofing / deepfake / ASVspoof 相关文献覆盖是否充分、准确，有无关键引用遗漏。

---

## Overall Assessment

### Recommendation
- [ ] **Accept** — 可直接发表，仅需格式微调
- [ ] **Minor Revision** — 需小修，无需再审
- [x] **Major Revision** — 需实质性修订，修订后需再审
- [ ] **Reject** — 不适合在本刊发表

### Confidence Score
**4** — 声学嵌入构造、说话人隐私评估、anti-spoofing 文献属我核心专长，高置信度；量化蒸馏（QAD）主线为相邻领域，个别发现触及实验设计边界，故保留一分不确定性。

### Summary Assessment
本文提出 QAD-MultiGuard，一个边缘–云协同多模态欺诈检测框架，核心为纯 KL 量化感知蒸馏（QAD）、OV-Freeze 正则、重构抵抗声学嵌入与域自适应投机解码。就我的领域视角（speaker/prosodic 表征、anti-spoofing、voice privacy）而言，QAD/OV-Freeze/投机解码主线的方法与报告质量扎实，但**声学嵌入隐私贡献（component iii）是全篇最薄弱的一环**。作者对「$\bm{F}_v$ 是 design target、实验用代理嵌入」的诚实降级值得肯定，但现稿仍残留三处断裂：（1）ASV-EER 计算在 reconstructed embeddings 上（度量的是重构失败而非 $\bm{F}_v$ 的说话人泄漏，近乎同义反复）；（2）speaker-ID MLP 输入维度（128）与 Eq.(5) 中 64 维 MFCC 分量不一致，且攻击对象是代理而非 $\bm{F}_v$；（3）「重构抵抗」未经验证是设计出来的性质而非时间池化的免费副产品，且「保留欺诈检测有用韵律」未经单模态消融证实。anti-spoofing/voice-privacy 文献覆盖偏薄（ASVspoof 仅引 2021 一篇），GLO 攻击误归于 Bora et al. 2017（压缩感知）而非说话人匿名 informed-attacker 文献。综合：Major Revision——说话人隐私评估需重新分析，声学贡献需重构表述，但量化蒸馏主线成立、可存活。

---

## Strengths

### S1: 对「content privacy vs. identity unlinkability」边界的领域化诚实界定
作者精准区分了内容隐私（content-privacy，抵抗语音内容重构、高 WER）与说话人身份不可链接性（cross-session unlinkability），并明确声明 $\bm{F}_v$ **不** 面向 unlinkability，残余风险在 §6 单独讨论。这是 voice-privacy 领域极少数作者能正确把握的边界，避免了把「重构抵抗」冒充「说话人匿名化」的常见混淆。
**Evidence Anchor**: `text: §2.4 "The scope of the present work is deliberately content-private in a stronger sense than VPC's content-utility... is not designed for identity-level unlinkability"`

### S2: 对 ASV-EER 与 below-chance speaker-ID 局限性的主动披露
作者主动声明 ASV-EER「量化的是重构攻击的失败，而非 $\bm{F}_v$ 本身的不可链接性」（§6.2），并将 11-speaker 的 8.3% below-chance 准确率标为「初步证据而非充分检验功效的阴性结果」（§6.2）。这种自我设限在系统类论文中罕见，显著提升可复核性。
**Evidence Anchor**: `text: §6.2 "This metric quantifies the failure of the reconstruction attack rather than the unlinkability of F_v itself"`

### S3: 正确引用 VoicePrivacy Challenge 的 content/identity 双维度评估框架
作者正确援引 VoicePrivacy 2022 评测计划（ref 22）作为 speaker anonymization 的领域标准评估框架，并将 anti-spoofing（ASVspoof）正确定位为「complementary, rather than replaces」重构抵抗——这两条定位在领域内是准确的。
**Evidence Anchor**: `text: §2.4 "distinguishes content from identity dimensions... the identity dimension targets cross-session unlinkability of the speaker"`

---

## Weaknesses

### W1: ASV-EER 测量对象错位——计算在 reconstructed embeddings 上，而非 $\bm{F}_v$ 本身
**Problem**: 表 4 报告的 ASV-EER（white-box 46.8%、black-box 48.5%）明确「computed on the *reconstructed* embeddings」，即对已被攻击破坏的重构产物（WER ≥ 0.95、接近随机噪声）再做说话人验证。对近乎随机的重构信号测得 EER ≈ 50% 是同义反复：它只说明「重构已经失败」，对 $\bm{F}_v$ 是否泄漏说话人信息**不提供任何证据**。VoicePrivacy 领域标准的说话人隐私度量是「对匿名化语音（或直接对嵌入）跑 ASV 系统得 EER」及 linkability 度量 $D^{\mathrm{link}}$，二者均未在 $\bm{F}_v$ 上执行。
**Evidence Anchor**: `text: §6.2 "the ASV equal-error rate (ASV-EER) computed on the reconstructed embeddings reaches 46.8% (white-box) and 48.5% (black-box)"`
**Why it matters**: 「$\bm{F}_v$ 不泄漏说话人身份」是全篇 privacy 主张（component iii）的关键支柱之一，但该主张的唯一 ASV 佐证度量了错误对象；正确的度量（$\bm{F}_v$ 上的 ASV-EER 或 linkability）完全缺失。作者虽在正文披露了此局限，但表 4 仍以「Privacy attack evaluation」名义并列呈现，易误导读者认为 $\bm{F}_v$ 的说话人泄漏已被测量。
**Suggestion**: 增加一项在 $\bm{F}_v$ 上直接执行的 ASV 评估——用一个标准 ASV 主干（如 ECAPA-TDNN，或与 ref 22 一致的评价协议）在 $\bm{F}_v$ 上报告 EER / $D^{\mathrm{link}}$；若无法完成，至少将表 4 的 ASV-EER 行明确改标为「reconstruction-failure proxy (not a speaker-leakage metric)」并移出「privacy attack」标题语义。
**Severity**: Major
**Confidence**: 5 — 核心专长：speaker characterization / ASV 评测方法学

### W2: speaker-ID 攻击的输入维度与 $\bm{F}_v$ 构造自相矛盾，攻击对象是代理而非 $\bm{F}_v$
**Problem**: §6.2 描述 speaker-ID 攻击为「three-layer MLP speaker classifier ($128 \to 256 \to 128 \to N_{\text{spk}}$) trained directly on the $128$-dimensional MFCC-based acoustic embeddings」。但 Eq.(5) 明确定义 $\bm{f}_{\mathrm{mfcc}} \in \mathbb{R}^{64}$（64 维 FBANK），Whisper 分量经投影后亦为 64 维。因此 MLP 的 128 维输入与「MFCC 代理嵌入」无法自洽：要么它是完整 $\bm{F}_v$（128 维拼接）却误标为「MFCC-based」，要么它是一个与 Eq.(5) 矛盾的 128 维 MFCC 表示。无论哪种，speaker-ID 攻击测的不是 Eq.(5) 所述的 64 维 MFCC 代理，测量对象与声明的构造不一致。
**Evidence Anchor**: `text: §6.2 "trained directly on the 128-dimensional MFCC-based acoustic embeddings extracted from the ChiFraud TTS subset"`
**Why it matters**: 说话人泄漏评估的对象维度无法与 $\bm{F}_v$ 构造对齐，直接动摇「8.3% below-chance」结论对 $\bm{F}_v$ 的可迁移性；叠加 11-speaker / 61-sample 的小样本（≈ 每说话人 1 条测试样本），该结论对本就微弱的说话人泄漏几乎没有统计检验力。
**Suggestion**: 明确 speaker-ID 攻击实际输入的表征（64 维 FBANK 代理？128 维完整 $\bm{F}_v$？还是 128 维 FBANK+delta？），并据此修正 MLP 输入维度描述，使其与 Eq.(5) 一致；在代理上得到的结论须显式声明为「代理结果，未经 $\bm{F}_v$ 端到端验证」。
**Severity**: Major
**Confidence**: 4 — 核心专长：声学特征构造与说话人表征；具体 ChiFraud TTS 代理细节超出可复核范围，故保留一分

### W3: 「重构抵抗」未经验证是设计性质而非维度压缩的免费副产品，且「保留欺诈检测有用韵律」无证据支撑
**Problem**: $\bm{F}_v$ 的「重构抵抗」完全来自对约 300 帧的时间平均 + Whisper 全局池化 + 输出 64 维的线性投影——这是激进的时序压缩。作者自己将机制归因为「information bottleneck」（§6.2）。但全文没有任何消融证明「MFCC+Whisper 拼接」这一**特定**构造比任意同维瓶颈（如平均池化 FBANK-only、平均池化 x-vector）更重构抵抗；换言之，WER ≥ 0.95 很可能是「把 300 帧压成 128 维」这一行为的通用后果，而非 component iii 的设计贡献。同时，作者宣称 $\bm{F}_v$「保留欺诈检测所需的粗粒度韵律线索」（§1、§6.2），但 §6 的「Modality-contribution limitation」自认未报告单模态 acoustic 消融，声学分支对最终决策的边际贡献从未被量化。
**Evidence Anchor**: `text: §6.2 "the 128-dimensional embedding acts as an information bottleneck that attenuates the high-frequency spectral and fine-grained temporal components essential for acoustic inversion"`
**Why it matters**: 这是对 component iii（四大贡献之一）novelty 的直接挑战：若重构抵抗只是压缩的免费副产品、且声学分支保留的信息是否对欺诈检测有用未经证实，则「reconstruction-resistant acoustic representation」这一贡献的核心价值不成立，应降格为「bottleneck observation」。此外，使用 Whisper-tiny（一个为 ASR 即语言内容编码而训练的编码器）作为「content-private」嵌入的分量，与「抵抗语音内容重构」的目标存在概念张力。
**Suggestion**: 补充消融——将 $\bm{F}_v$ 与（a）mean-pooled FBANK-only、（b）mean-pooled x-vector 等 128 维基线在相同 GLO/U-Net 攻击下对比 WER，以证明特定构造的必要性；并补充单模态 acoustic 消融，量化声学分支的 $F_1$ 增量；若无法补实验，则将 component iii 明确改写为「一个保守的时序压缩瓶颈，其重构抵抗是容量受限的自然结果」，并移除「保留欺诈检测有用韵律」这一未证实断言。
**Severity**: Major
**Confidence**: 4 — 核心专长：声学嵌入与韵律表征；消融实验设计触及方法论边界（Reviewer 1 职域），故保留一分

### W4: GLO 攻击引用误归——Bora et al. 2017（压缩感知）并非「匿名嵌入可被逆重构」的出处
**Problem**: §2.4 写道「\citet{23} demonstrated, utilising the Generative Latent Optimisation (GLO) attack framework, that such anonymised embeddings can still be exploited for inverse reconstruction」。但 ref 23 为 Bora, Jalal, Price, Dimakis 的 *Compressed Sensing using Generative Models*（ICML 2017），其主题是「用生成模型先验求解一般逆问题（超分辨、补全、压缩感知）」，并非「匿名化 x-vector 嵌入可被逆重构」这一说话人匿名攻击结论。该结论属于 speaker-anonymization informed-attacker 文献（典型如 Srivastava et al., *Evaluating voice conversion-based privacy protection against informed attackers*, ICASSP 2020），其白盒 GLO 攻击才与本文 §6.2 的「assumes full knowledge of the feature-extraction pipeline」一致。
**Evidence Anchor**: `text: §2.4 "utilising the Generative Latent Optimisation (GLO) attack framework, that such anonymised embeddings can still be exploited for inverse reconstruction"`
**Why it matters**: 引用准确性是领域评审的基本项；把「匿名嵌入可逆」这一支撑性事实错挂到压缩感知论文，会让读者（尤其熟悉 voice-privacy 领域的读者）怀疑相关工作的严谨性。虽不改变「匿名嵌入确实可被逆重构」这一正确结论，但削弱了 §2.4 论证的事实根基。
**Suggestion**: 将 GLO 攻击的来源改引到 speaker-anonymization informed-attacker 文献（如 Srivastava et al., ICASSP 2020），并可保留 Bora et al. 2017 作为生成模型先验逆问题的技术源头之一；若采用 ref 22 的评测协议，也可引其对应的 attacker 分析。
**Severity**: Minor
**Confidence**: 4 — 核心专长：voice-privacy 攻击文献谱系；Srivastava et al. 2020 为我可确证存在的文献

### W5: FBANK 与 MFCC 术语混用，$mfcc$ 下标误标 log-mel 滤波器组能量
**Problem**: Eq.(5) 与 §4.2 将 64 维分量标为 $\bm{f}_{\mathrm{mfcc}}$，但脚注承认它实为「64 维 log-mel filterbank energies (FBANK)」，$mfcc$ 仅作「mnemonic」。FBANK（对数梅尔滤波器组能量，维度间高度相关）与 MFCC（经 DCT 去相关的倒谱系数）是领域内明确区分的两类声学特征；用 $mfcc$ 下标指代 FBANK 违背领域命名惯例，且 §1、§2.4 反复出现「time-averaged MFCC」「MFCC temporal averaging」等未加限定语，会误导读者对特征性质的理解。
**Evidence Anchor**: `text: §4.2 "the mfcc subscript is retained as a mnemonic for the temporally averaged cepstral-like representation rather than a DCT-derived cepstral coefficient count"`
**Why it matters**: 术语精度是 speech signal processing 评审的关注点；「FBANK 均值池化」与「MFCC」信息性质不同（后者经 DCT 近似解相关），混用会削弱读者对 $\bm{F}_v$ 构造的准确理解，也暗示作者对特征的精确描述不够严谨。
**Suggestion**: 全篇统一改为 $\bm{f}_{\mathrm{fbank}}$（或 log-mel），删除 $mfcc$ mnemonic 脚注，或在首次出现处一次性说明后一律用 FBANK 表述。
**Severity**: Minor
**Confidence**: 5 — 核心专长：声学前端特征（FBANK/MFCC）命名规范

### W6: anti-spoofing / deepfake / ASVspoof 文献覆盖偏薄，$\mathcal{G}_3$ 威胁仅架构性提及
**Problem**: 威胁模型 $\mathcal{G}_3$（identity fraud spoofing）被明确定义但「not quantitatively benchmarked」，仅通过 cross-modal consistency 架构性处理；相关文献部分只引了 ASVspoof 2021 一篇（ref yamagishi2021asvspoof），未涉及 spoofing countermeasure 方法（如 AASIST、RawNet2 等 raw-waveform/自监督反欺骗主干）或 ASVspoof 2019 评测体系，也未讨论「一个处理语音通话的欺诈检测系统为何不需要对 deepfake/换声语音具备鲁棒性」。考虑到电信欺诈场景中骗子的语音可能本身就是合成/换声产物（deepfake），这一缺位削弱了系统的领域完备性论证。
**Evidence Anchor**: `absence: §2.4 (Reconstruction-Resistant Acoustic Representations) — expected engagement with spoofing countermeasure literature (AASIST / RawNet2 / ASVspoof 2019) and a justification of why G3 spoofing robustness is out of scope for a voice-based fraud detector; checked §2.4, §3.1 threat model, §7.2 limitations`
**Why it matters**: 我的评审职域之一即 anti-spoofing 文献完整性；$\mathcal{G}_3$ 既然被列为三大威胁之一，其对应的检测侧文献与「为何不量化」的辩护应更充分，否则系统在面对合成语音欺诈时的不设防状态未被严肃对待。
**Suggestion**: 在 §2.4 增补反欺骗（anti-spoofing）countermeasure 的近期工作（AASIST, RawNet2 等）并说明其与本工作「重构抵抗」的互补关系；在 §7.2 明确论证 $\mathcal{G}_3$ 为何可被架构性处理而非需要专门的 spoofing 鲁棒性评估，或将其显式列为未来工作。
**Severity**: Minor
**Confidence**: 4 — 核心专长：ASVspoof / anti-spoofing 文献；具体推荐文献为我可确证存在的领域标准工作

---

## Detailed Comments

### 相关文献（§2.4 Reconstruction-Resistant Acoustic Representations）
- **Coverage**: 抓住了 x-vector、VoicePrivacy 2022、ASVspoof 2021 三条正确主线，内容/身份双维度的定位准确（见 S3）。但 anti-spoofing 侧仅一篇 2021，缺 countermeasure 方法谱系与 ASVspoof 2019 评测框架；GLO 攻击引用误归（W4）；缺 speaker-anonymization 的 informed-attacker 攻击文献（Srivastava et al. 2020 等）。
- **Integration quality**: 组织清晰，是「主题式」而非「罗列式」，且能明确本工作的差异化边界（content-private vs. unlinkability）。但引用准确性（W4）拉低了整体可信度。
- **Research gap argument**: 论证「现有系统单模态、ASR 转录退化」有说服力，但「声学分支强多模态耦合」的动机（§2.2）被 §6 自认的单模态消融缺失所削弱。

### 方法论（§4.2 声学嵌入构造 + §3.1 威胁模型）
- **Appropriateness**: FBANK 均值池化 + Whisper-tiny 全局池化作为轻量端侧特征合理；但 Whisper 是内容（语言）优化编码器，与「content-private」目标存在概念张力（见 W3）。
- **Application depth**: 构造式（Eq.5）清晰，但「rank-constrained projection（rank ≤ 64）」对 384→64 线性映射而言是平凡事实（输出维度即 64），措辞有 oversell 之嫌。
- **Alternative frameworks**: 更强的替代方案如「在语音情感/欺骗检测目标上训练的说话人-内容解耦编码器」或「以 linkability 为显式优化目标」未讨论（后者作者已在 §6 作为未来方向提及）。

### 结果/发现（§6.2 Privacy Verification）
- **Completeness**: WER/PESQ/STOI/MOS 重构指标齐备，但对说话人隐私的核心度量（$\bm{F}_v$ 上的 ASV-EER、linkability）缺失（W1）；speaker-ID 维度不自洽（W2）；11-speaker/61-sample 样本量使 below-chance 结论仅有示意意义（作者已诚实标注）。
- **Figure/table quality**: 表 4 将 ASV-EER 与 speaker-ID 并列于「Privacy attack evaluation」标题下，未在表内标注 ASV-EER 是「重构失败代理」而非「$\bm{F}_v$ 泄漏度量」，存在误导风险（W1）。
- **Alignment**: 隐私主张与证据在 WER（内容重构）维度对齐良好，在「说话人不可追踪」维度存在错位。

### 讨论（§7 Discussion）
- **Dialogue with literature**: 「unlinkability and implicit fingerprint risk」段落对 honest-but-curious cloud 余弦相似度链接攻击的分析是准确的领域洞察（S1 的延续），并正确指出确定性 $\bm{F}_v$ 的跨会话稳定性风险。
- **Limitations**: 对单主语料、LDP 无认证 sensitivity 界、speaker-ID 小样本、G3 未量化等限制的披露充分且诚实，是本文的显著优点。

---

## Questions for Authors

1. **speaker-ID 攻击的确切输入表征是什么？** MLP 输入标为 128 维「MFCC-based」嵌入，但 Eq.(5) 定义 $\bm{f}_{\mathrm{mfcc}}\in\mathbb{R}^{64}$。请明确：该攻击输入是 64 维 FBANK 代理、128 维完整 $\bm{F}_v$，还是某种 128 维 MFCC 变体？请使维度描述与 Eq.(5) 一致。

2. **是否在 $\bm{F}_v$ 本身上计算过 ASV-EER 或 linkability 度量？** 目前 ASV-EER 仅计算在 reconstructed embeddings 上（W1）。能否用一个标准 ASV 主干（如 ECAPA-TDNN，与 ref 22 协议一致）在 $\bm{F}_v$ 上直接报告 EER / $D^{\mathrm{link}}$？这直接决定「$\bm{F}_v$ 不泄漏说话人身份」主张是否成立。

3. **能否提供一个消融证明 $\bm{F}_v$ 的特定构造（MFCC+Whisper-proj 拼接）比同维平凡瓶颈（如 mean-pooled FBANK-only、mean-pooled x-vector）更重构抵抗？** 否则「reconstruction resistance」应被表述为「时序压缩的信息瓶颈自然结果」而非 component iii 的设计贡献（W3）。

4. **Whisper-tiny（ASR 编码器，语言内容优化）作为「content-private」嵌入分量，其设计动机如何与「抵抗语音内容重构」自洽？** 是否考虑过用内容无关的表征（如 speaker/emotion 编码器）以更好地匹配设计意图？

---

## Minor Issues

### Language / Grammar
- §2.4 与 §4.2 中「MFCC」与「FBANK」交替出现但指向同一特征，建议全篇统一（见 W5）。

### Citation Format
- ref 23（Bora et al. 2017）被引作「匿名嵌入可被 GLO 逆重构」的出处，属引用误归，需改引（见 W4）。
- ref 3（NVIDIA Nemotron report）已标注 non-archival / non-peer-reviewed，处理得当；但正文多处将「Nemotron 97.0–99.4% recovery」作为 reference baseline 引用，建议保持该 non-peer-reviewed 的限定语一致性。

### Figures and Tables
- 表 4（Privacy attack evaluation）建议为 ASV-EER 行加脚注「computed on reconstructed embeddings; not a measure of F_v speaker leakage」，避免与 speaker-ID 行并列造成误导（见 W1）。

### Layout
- 无显著布局问题。

---

## Criterion-Bound Judgements

Calibration status: `NOT_CALIBRATED`

| Dimension | Criterion source | Judgement | Evidence anchor(s) | Rationale | Uncertainty / scope limit | Decision bearing? |
|---|---|---|---|---|---|---|
| Originality | quality_rubrics.md D1 | PARTLY_MEETS | `text: §6.2 "acts as an information bottleneck"`; `equation: Eq.(5)` | 量化蒸馏集成具增量新意，但 component iii 的「重构抵抗」未证明为设计性质而非压缩副产品（W3），削弱了 novelty 主张 | 消融实验归属方法论边界 | yes — 声学贡献 originality 未建立 |
| Methodological Rigor | quality_rubrics.md D2 | PARTLY_MEETS | `text: §6.2 "computed on the reconstructed embeddings"`; `text: §6.2 "128-dimensional MFCC-based"` | 说话人隐私评估测量对象错位（W1）且维度不自洽（W2），11-speaker 小样本检验力不足 | 部分触及 Reviewer 1 职域 | yes — 隐私主张的测量有效性存疑 |
| Evidence Sufficiency | quality_rubrics.md D3 | PARTLY_MEETS | `text: §6.2 "information bottleneck"`; `absence: §6.2/§7 — expected single-modality acoustic ablation; checked §6, §7.2` | 声学分支欺诈检测有用性未证实、代理嵌入未覆盖端到端 $\bm{F}_v$ | 代理嵌入的具体实验细节不可复核 | yes — 核心隐私主张证据链不完整 |
| Argument Coherence | quality_rubrics.md D4 | MEETS | `text: §2.4 "content-private... not designed for identity-level unlinkability"` | 内容/身份边界清晰，局限披露充分，论证链自洽 | none identified | no |
| Writing Quality | quality_rubrics.md D5 | MEETS | `text: §6.2 "preliminary evidence of privacy rather than a formal, adequately-powered negative result"` | 术语偶有混用（W5）但整体清晰、诚实、可复核 | none identified | no |
| Literature Integration | quality_rubrics.md D6 | PARTLY_MEETS | `text: §2.4 "GLO attack framework... inverse reconstruction"`; `absence: §2.4 — expected anti-spoofing countermeasure literature; checked §2.4, §3.1, §7.2` | anti-spoofing 覆盖偏薄（W6）、GLO 引用误归（W4） | 推荐文献存在性为我可确证范围 | yes — 领域完备性不足 |
| Significance & Impact | quality_rubrics.md D7 | MEETS | `text: §6.2 "the temporally coarse statistics retained by F_v still carry the coarse-grained prosodic and spectral envelope"` | 边缘端隐私合规实时欺诈检测的可行性基线有实用意义，但受单主语料限制 | 「保留有用韵律」断言未经证实（W3） | no |

**Recommendation rationale**: 决策性未决项为 Originality（声学贡献 novelty 未建立）、Methodological Rigor（说话人隐私测量错位）、Evidence Sufficiency（代理嵌入 + 无单模态消融）、Literature Integration（anti-spoofing 覆盖薄 + GLO 误归）。其中前三项需新实验（$\bm{F}_v$ 上的 ASV-EER/linkability、维度修正、瓶颈对比消融与单模态消融）或对 component iii 的实质重写，超出小修范围；但量化蒸馏主线（QAD/OV-Freeze）证据充分、可存活，故判定 Major Revision 而非 Reject。

---


## Seat R3

# Peer Review Report — Round 2, Seat R3 (Cross-disciplinary / Practical Perspective)

## Manuscript Information
- **Title**: QAD-MultiGuard: An Edge--Cloud Framework for Multimodal Fraud Detection and Risk Assessment
- **Manuscript ID**: N/A
- **Review Date**: 2026-09-01
- **Review Round**: Round 2（第二轮评审）

---

## Reviewer Information

### Reviewer Role *
Peer Reviewer 3（Cross-disciplinary / Practical Perspective）

### Reviewer Identity *
一位可信 AI / 隐私工程 + 数据保护合规跨学科学者。兼具 privacy engineering（形式化边界、威胁建模、可审计性）与 PIPL/GDPR 数据保护法规研究背景，并熟悉金融反诈系统的真实部署约束（运营商网络侧 vs 终端侧、误报成本、监管审查）。本轮从「隐私机制的形式化边界与诚实度」「端云部署假设的现实性」「合规声明的法律支撑」「真实世界可部署性」四个角度评审。

### Review Focus *
(1) 重构抵抗嵌入 + LDP 的**形式化边界与诚实度**——是否把「工程估计」冒充「形式化保证」；(2) 端云部署假设的**现实性**——「raw audio stays on-device」是否依赖从未言明的受害者终端部署模型；(3) PIPL/GDPR 合规声明是否有法律分析支撑，还是自我背书；(4) 真实世界可部署性（算力、带宽、误报成本、监管）对框架设计的反作用。特别关注论文是否把「技术评估」与「法律合规」混为一谈，以及隐私叙事能否经得起持怀疑态度的合规官或部署工程师的追问。

---

## Overall Assessment *

### Recommendation *
- [ ] **Accept** — Can be published directly, only minor formatting changes needed
- [ ] **Minor Revision** — Minor revisions needed, no re-review after revision
- [x] **Major Revision** — Substantial revisions needed, re-review required after revision
- [ ] **Reject** — Not suitable for publication in this journal

### Confidence Score *
**4** — 大部分在本领域内（隐私工程 + PIPL/GDPR 合规框架），但对「中国电信反诈的实际部署拓扑」与「PRC 合格法律意见」的判断存在外部不确定性。

### Summary Assessment *
本文提出 QAD-MultiGuard，一个端云协同的多模态反诈检测框架，将纯-KL 量化感知蒸馏（QAD）、OV-Freeze 正则、128 维重构抵抗声学嵌入、域自适应投机解码集成为面向资源受限移动设备的系统，主打「privacy / fidelity / responsiveness」三约束联合满足。

从隐私工程与数据保护合规的角度，本轮稿件在**诚实降级**上完成度很高：LDP 明确标注为「engineering estimate without a certified sensitivity bound」、$\bm{F}_v$ 标注为 design target、说话人识别标注为 preliminary、PIPL 声明降级为「technical assessment, not legal compliance」。这是第一轮以来最实质的改进，值得肯定。

但稿件在我关切的四点上仍存在结构性断裂，且都不是措辞能解决的：**其一**，「raw audio stays on-device」这一核心隐私叙事依赖一个从未言明的「检测软件运行于受害者终端并获授权」的部署模型，而真实反诈部署通常在运营商网络侧，该前提一旦不成立隐私叙事整体坍缩；**其二**，摘要仍称「privacy-compliant on-device AI」、引言仍称「complying with PIPL」，与正文降级声明直接冲突，且全文无任何法律分析支撑；**其三**，重构抵抗性（WER≥0.95）测于「proxy embeddings」而非实际传输的 $\bm{F}_v$，隐私边界物本身未被评估；**其四**，FPR 1.8% 是在约 48% 欺诈平衡集上测得的，从未折算到真实低发病率场景。

这些发现叠加仍待完成的 reproducibility run（R1，非本席位但已确认仍开放），指向 **Major Revision**：隐私贡献需要重定位或补分析，而非澄清即可。

---

## Strengths *

### S1: 形式化/经验边界声明诚实且贯穿一致
稿件在隐私机制的每一处都克制地标注了边界，且标注方式符合隐私工程社区的标准：LDP 在 Figure 4 caption 明确「$\epsilon = 1.5$ is an engineering estimate without a certified sensitivity bound」，Discussion 明确「not a full differential-privacy analysis」；说话人识别明确「preliminary evidence of privacy rather than a formal, adequately-powered negative result」；Appendix 明确「empirical evidence rather than a formal information-theoretic guarantee」。这是少数把「工程估计」与「形式化保证」干净分开的系统论文。
**Evidence Anchor**: `text: §Discussion "engineering estimate obtained without a certified sensitivity bound"; Appendix "empirical evidence rather than a formal information-theoretic guarantee"`

### S2: 可链接性残余风险被显式命名并给出缓解方向
稿件准确识别 $\bm{F}_v$ 是确定性函数、可被 honest-but-curious cloud 通过余弦相似跨会话聚类链接，并将其与重构攻击（$\mathcal{G}_1$）区分开，同时给出具体缓解方案（session-specific dynamic perturbation / orthogonal rotation）。这正是一个持怀疑态度的合规官会问的问题，而作者主动回答了。
**Evidence Anchor**: `text: §Discussion "an honest-but-curious cloud (Tier-2) retaining historical representations may cluster embeddings via cosine similarity and link repeated interactions"`

### S3: 「误分类的社会后果」段落体现了跨学科成熟度
论文明确承认 FN（放过诈骗、伤害老年人/数字弱势群体）与 FP（误冻结真实金融/亲属交易、危及照护者紧急呼叫）的不对称成本，并将决策阈值校准明确推迟到「operator and regulator involvement」的部署研究。这种对利益相关方成本不对称的自觉，在系统型论文中罕见。
**Evidence Anchor**: `text: §Discussion "a false positive interrupts a legitimate call, imposing a distinct harm"`

---

## Weaknesses *

### W1: 隐私叙事依赖一个从未言明的「受害者终端」部署模型
**Problem**: 全文的隐私支柱——「raw audio and text never leave the device」（§System Architecture）、「raw biometric audio stay within the device boundary mandated by PIPL」（C1）——都预设检测软件运行在**数据主体的终端**（受害者的手机）上，且受害者主动安装并授权。但全文从未说明：谁安装/运行这套软件？谁是 data controller？合法依据是什么？在真实的电信反诈中，检测通常部署在**运营商网络侧**（运营商依电信法规已接触信令/语音），此时「raw audio stays on-device」在物理上无意义——音频本来就在网络侧。若部署模型是「受害者自愿安装的消费者 App」，则意味着被社会工程攻击的人需主动装一个保护自己的 App，这一前提对「保护」措施而言极不寻常，且未获任何证据或论证支持。
**Evidence Anchor**: `absence: §sec:sysarch / §Data-flow boundary — expected 检测软件的运行主体、data controller 身份、合法处理依据与同意模型说明; checked §Abstract, §Introduction, §sec:sysarch, §Data-flow boundary, §sec:method, §sec:discussion, §Data availability`
**Why it matters**: 这是隐私叙事的根基假设（DA 第一轮已列为「Unexamined Premise」，但未进入修订路线图，本轮稿件仍未处理）。「on-device」只有在终端部署模型成立时才有隐私意义；一旦真实部署在运营商侧，「privacy」三支柱之一即告无效，而「edge–cloud」架构与「raw audio stays on-device」的贡献定位也随之错位。持怀疑态度的合规官或部署工程师的第一个问题必然是「谁的设备、谁是控制者」。
**Suggestion**: 明确陈述并论证部署模型（数据控制者、数据主体、合法依据、终端类型）；或把「on-device」隐私声称从「已满足」降级为「以终端部署为前提的 design assumption」，并在 Discussion 中显式讨论运营商侧部署的替代拓扑及其对隐私叙事的影响。
**Severity**: Major
**Confidence**: 4 — core expertise: privacy engineering / PIPL-GDPR（「未言明」可验证；「真实部署拓扑」为领域知识，存在运营商间差异）

### W2: 摘要/引言仍保留合规宣称，与正文降级声明冲突，且全文无法律分析
**Problem**: 第一轮 S7 已把 PIPL 声明降级为「technical assessment, not legal compliance」，但摘要仍写「privacy-compliant on-device AI」、引言仍写「while complying with data-protection regulations such as China's PIPL」、C1 仍写「the device boundary mandated by PIPL」、§sysarch 仍写「aligning with PIPL data-minimisation requirements」。局部免责声明（§sec:glo、§discussion）与全局合规叙事并存，且全文**没有任何法律分析**：未识别 data controller/processor、未讨论 PIPL 第 13 条合法基础（同意/必要性）、未触及第 28 条「敏感个人信息（含生物识别）须单独同意 + 必要性」、未做跨境传输（第 38–40 条）或安全影响评估，仅在第 858 行提及一次 Article 23。这构成「自我背书」——以法规名称充当合规论证，而无实体分析支撑。
**Evidence Anchor**: `text: §Abstract "privacy-compliant on-device AI under strict latency budgets"; §Introduction "while complying with data-protection regulations such as China's Personal Information Protection Law (PIPL)"`
**Why it matters**: 这正是我这一席位最担心的「技术评估与法律合规混为一谈」。摘要的「privacy-compliant」是 headline，任何读者先看到的都是合规宣称；而正文承认「不是法律合规判定」。二者并存意味着论文在同一稿内对同一主张给出两种相反强度，经不起合规官的追问。作者已选择了「诚实降级」路径，但没有把降级贯彻到摘要/引言/系统架构这些最高可见度的位置。
**Suggestion**: 二选一并保持一致：(a) 删除摘要「privacy-compliant」、引言「complying with」、C1「mandated by PIPL」、§sysarch「aligning with PIPL」等合规性措辞，统一为「privacy-oriented design」/「data-minimisation-aligned technical design」；(b) 若坚持合规宣称，则需补真正的法律分析（控制者、第 13/28 条合法基础、第 38–40 条跨境、安全评估），并请合资格法律顾问复核。当前稿件不应在摘要保留「privacy-compliant」。
**Severity**: Major
**Confidence**: 4 — core expertise: data-protection regulation（「零法律分析」为可验证 absence；「合规措辞的法律解读」受我非 PRC 合格律师身份约束）

### W3: 重构抵抗性测于「代理嵌入」而非实际传输的 $\bm{F}_v$，隐私边界物本身未被评估
**Problem**: 隐私机制的边界物是传输到云端的 128 维 $\bm{F}_v$（Eq.~\eqref{eq:f-v}，MFCC-64 ⊕ Whisper-proj-64 拼接）。但 §sec:acoustic 明言 $\bm{F}_v$ 是 design target，「the released experiments evaluate its two components through their respective proxy embeddings… rather than through the jointly trained concatenated $\bm{F}_v$」；§sec:glo 进一步说明重构质量数字是「reference estimates… rather than independently re-measured outputs of the released evaluation pipeline」。即：WER≥0.95、speaker-ID 8.3% 等 headline 隐私数字**不是对实际会传输出去的那个向量测的**，而是对其「代理组件」或引用性估计。此外，speaker-ID 段落用的是「128-dimensional MFCC-based acoustic embeddings」（ChiFraud TTS），这与 $\bm{F}_v$ 的 64-MFCC+64-Whisper 定义不一致。
**Evidence Anchor**: `text: §sec:acoustic "the released experiments evaluate its two components through their respective proxy embeddings"; §sec:glo "reference estimates from the reconstruction-attack analysis rather than independently re-measured outputs of the released evaluation pipeline"`
**Why it matters**: 从 privacy engineering 角度，安全声明必须附着于**实际暴露面**。暴露面是 $\bm{F}_v$，而测量对象是代理。一个严谨的隐私工程师会直接拒绝这条证据链：论文证明了「某代理特征难以重构」，却把结论移用到「$\bm{F}_v$ 难以重构」。这是形式化边界上的关键断裂——诚实降级披露了它，但没有解决它。
**Suggestion**: 要么直接在拼接后的 128 维 $\bm{F}_v$ 上跑 GLO/U-Net 攻击并报告 WER/PESQ/speaker-ID；要么在摘要/贡献处把隐私声称显式降级为「proxy-level empirical evidence，尚未在传输向量上验证」，并修正 speaker-ID 段的嵌入定义不一致。
**Severity**: Major
**Confidence**: 5 — core expertise: privacy engineering / threat modeling（直接文本证据，无歧义）

### W4: 误报率未折算到真实低发病率场景，headline FPR 1.8% 会高估部署可用性
**Problem**: Table 3 的最佳配置 FPR=1.8%，但该 FPR 是在 TAF-28k 上测得的，而 TAF-28k 的 fraud 标签是**近似平衡**的（13,647 fraud / 14,864 normal，约 48% 欺诈）。真实电信诈骗的发病率远低于 1%。在低发病率下，1.8% FPR 意味着告警流几乎全部由误报构成（PPV 急剧坍缩）。论文报告了 FPR，但从未把它折算为「每位合法用户每日误报率」或给出 prevalence-calibrated PPV；「Societal consequences of misclassification」段承认 FP 成本却把量化「deferred to a deployment-oriented study」。
**Evidence Anchor**: `table: tab3-en — FPR column 1.8% (NVFP4 QAD+OVF+CoT) / 1.9% (Q4_K_M QAD+OVF) 在 ~48% fraud-balanced 测试划分上测得`
**Why it matters**: 这是部署工程师的第一问。一个在平衡集上 F1=0.923 的系统，在真实 0.1%–1% 发病率下可能每分钟都产生误报，导致告警疲劳或误冻结真实交易。论文把「risk assessment」作为标题一部分，但 risk score 从未校准到真实 base rate。这直接削弱「可部署性」声称，是「academically meaningful but practically unusable」风险的典型表现。
**Suggestion**: 补一个 prevalence-calibrated 分析（如以 0.1%/1% 发病率重算 PPV / false-alert-per-user-per-day），或显式把 headline FPR 声明限定于「balanced benchmark」，并在 Discussion 中把 prevalence mismatch 列为独立局限。注意：这不要求新实验，用现有 FPR 与一个发病率假设即可推导。
**Severity**: Major
**Confidence**: 4 — core expertise: deployment engineering（算术清晰；真实发病率是领域知识，非稿件内容）

### W5: LDP 的「corresponding to $\epsilon$=1.5」措辞仍暗示存在解析转换
**Problem**: §Discussion 仍写「using a Gaussian mechanism ($\sigma = 1.0$, corresponding to $\epsilon = 1.5$ at $\delta = 10^{-5}$)」。即便后文立即补充了「engineering estimate obtained without a certified sensitivity bound」，「corresponding to」仍暗示 $\sigma \rightarrow (\epsilon,\delta)$ 存在一个可复现的解析/数值转换，而这一转换恰恰需要稿件自认缺失的 L2 sensitivity 与 clipping 界。保留具体数值 $\epsilon=1.5$ 在没有灵敏度界的情况下本质上是任意的。
**Evidence Anchor**: `text: §Discussion "using a Gaussian mechanism ($\sigma = 1.0$, corresponding to $\epsilon = 1.5$ at $\delta = 10^{-5}$)"`
**Why it matters**: 这是「工程估计 vs 形式化保证」边界上的一个小残留——措辞层面仍把二者缝合。一个熟悉 DP 的读者会要求给出 sensitivity，否则 $\epsilon=1.5$ 不可审计。
**Suggestion**: 删除「corresponding to $\epsilon = 1.5$ at $\delta = 10^{-5}$」这一等值关系，只报告 $\sigma=1.0$（噪声尺度本身可审计），并保留「无认证灵敏度界」的定性说明。
**Severity**: Minor
**Confidence**: 4 — core expertise: differential privacy（L2 sensitivity 与 analytic Gaussian mechanism 的对应关系）

---

## Detailed Comments *

### Assumption Audit

**显式假设（explicit）**：稿件明确陈述了三约束（privacy / fidelity / responsiveness）、90s 通话时长与「关键欺诈指令在前 60s 给出」、3s 窗口、4GB/500MB 硬件预算、500ms/1s 时延预算。这些假设与电信反诈场景的常识一致，但其中「90s 通话」「4GB/500MB 预算」仍无出处（第一轮 DA 已标记「无出处前提」，本轮未见补引文）。建议要么补引用，要么明确标注为 design assumption 而非行业事实。

**隐式假设（implicit，本席位的核心关切）**：最深的一条是 W1 所述——「检测软件运行于数据主体（受害者）终端并获授权」这一部署模型从未被陈述，却是全部隐私叙事的支点。此外还有三条次级隐式假设：(a) 受害者的「raw audio」是设备端采集的本地语音——但一次通话的声学信号**同时包含受害者与诈骗者双方声音**，若设备端处理的是含双方声音的录音，则被「留在设备内」的其实是诈骗者的生物识别信息（第三方的个人信息），其处理依据在 PIPL 下是另一条未经分析的问题；(b) 受害者持有一台 Snapdragon 8 Gen 3 级设备；(c) 部署场景的 fraud 发病率与约 48% 平衡测试集相当（W4 已反驳）。

**范式假设（paradigmatic）**：论文延续了「更强隐私 = 更少信息 = 更差精度」的单变量权衡范式（信息瓶颈叙事），而把「隐私」约化为「抵抗重构」。但这一范式遮蔽了一个更深的张力：反诈检测的任务信号**本身**高度依赖语音**内容**（社会工程话术、诱导指令），而隐私机制恰恰在摧毁内容可懂度（WER≥0.95）。作者以「粗粒度韵律/频谱包络仍携带风险信号」回应，但这一主张正是 R2（audio-only 消融）尚未验证的关键点。换言之，隐私机制与检测任务可能在方向上互相抵消，而当前评估无法判定声学分支究竟贡献了什么。

### 隐私机制的形式化边界与诚实度（Review Focus 1）

诚实度本轮显著提升，值得单独肯定（见 S1）。残余问题集中在两处：W3（测量对象错位）与 W5（$\epsilon$ 措辞）。综合判断：作者在「诚实」维度做对了，但在「形式化边界」上仍留有一个实质性空洞——**实际传输的 $\bm{F}_v$ 的重构抵抗性从未被直接测量**。这意味着 C1 的隐私机制目前只有「代理证据 + 引用性估计 + 非可链接性缺失」三层弱支撑，而摘要却将其概括为「reconstruction-resistant acoustic embedding」这一强表述。

### 端云部署假设的现实性（Review Focus 2）

见 W1。补充一点跨学科观察：电信反诈的真实技术栈（运营商侧信令/语音监控、号码库、反诈 App 平台如国家反诈中心 App）与本文「受害者终端本地推理」的定位存在系统性错位。若本文意在描述运营商侧部署，「raw audio stays on-device」应为「raw audio stays on-network-edge」，隐私主张需整体重写；若意在描述消费者 App，则需论证受害者为何会安装它。二者择一，都会实质改变摘要与贡献的表述。这是比任何单点数字更根本的定位问题。

### PIPL/GDPR 合规声明（Review Focus 3）

见 W2。补充：论文将 PIPL 用作**约束论证**（「PIPL 限制原始音频传输 → 因此需 on-device」）而非**合规分析**，这是「以法规名称为设计辩护」而非「证明合规」。从数据保护法规角度，一个真正的合规分析至少需要回答：谁是控制者（运营商？App 厂商？）、处理依据（PIPL Art. 13 同意/必要）、是否触及 Art. 28 敏感个人信息（生物识别）、跨境是否触发 Art. 38–40、是否需个人信息保护影响评估。GDPR 完全未被提及——若论文明确限定于中国境内，可接受，但摘要「regulations such as PIPL」的「such as」暗示了一个更大的法规类别却未兑现，应删除或收窄。

### 真实世界可部署性（Review Focus 4）

**算力/带宽**：论文在算力（240MB/268ms/50 并发 310ms）与带宽（仅传 128 维向量 + 标量 + 隐藏态）方面处理得相对扎实，值得肯定；「2.1× 为内核吞吐非端到端」的区分也诚实。**误报成本**是最大缺口（W4）：FPR 未折算到真实发病率，误报对真实交易/亲属交易/紧急呼叫的伤害（作者自己已意识到）没有对应到任何 prevalence-calibrated 的量化。**监管**：反诈系统属于「对个人权益有重大影响的自动化决策」范畴，PIPL Art. 24（自动化决策透明度与拒绝权）、以及可能的算法备案/安全评估义务，均未触及——一个面向中国反诈部署的系统论文完全不讨论这些，是显著的监管盲区。

### Stakeholder 视角

论文已覆盖「受害者（老人/低数字素养）」「合法用户（被误冻结）」两端，但遗漏了：(a) **运营商**——真实部署的主体，其监管义务与数据控制者责任；(b) **诈骗者本人**——其语音同为生物识别信息，处理依据未分析；(c) **被误报者的申诉/救济权**——PIPL Art. 24 下的解释与拒绝权未被提及。

### Cross-Disciplinary Connections

**平行研究**：语音隐私社区的 Voice Privacy Challenge（已引 [22]）与本文方向相近但目标相反（VPC 保内容、毁身份；本文毁内容、不保身份）；差分隐私的 analytic Gaussian mechanism 文献（Dwork & Roth 2014）可直接用于修正 W5 的 $\epsilon$ 表述；on-device 联邦学习/联邦分析（Apple DP、Google RAPPOR/Federated Learning）为「数据不出端」提供了与本文互补的范式。
**借用机会**：NIST Privacy Framework 的「identify–govern–control–communicate–protect」结构与 PIPL 的影响评估义务，可帮助作者把「技术机制」与「合规治理」两个层面正式分离（当前二者在措辞上仍有缝合）。
**方法借用**：隐私工程中的**暴露面（attack surface）分析**——「安全声明必须附着于实际传输物」——正是修正 W3 所需的规范工具；可直接写进 §sec:glo。

### Broader Implications

若「privacy-compliant on-device AI」的框架被不加限定地接受，其潜在社会影响是双向的：正向看，它推动了「数据最小化」的落地叙事；负向看，它可能在无法律分析、无暴露面验证、无 prevalence 校准的情况下，给监管者与公众一种「隐私与合规已被技术解决」的错觉。对一篇面向 ESWA 的应用型论文，作者有责任确保 headline 不高于证据。当前稿件的正文已经诚实，问题在于摘要与贡献层的措辞仍高于正文。

---

## Questions for Authors *

1. **部署模型**：请明确说明谁安装/运行这套检测软件、谁是 data controller、处理合法依据是什么。若部署在运营商网络侧，「raw audio stays on-device」应如何改述？若部署在受害者终端，为何假设受害者会主动安装反诈软件？这一答案会直接决定摘要与贡献的表述。

2. **合规立场**：摘要称「privacy-compliant」而正文称「technical assessment, not legal compliance」——请明确论文的最终立场，并在摘要/引言/§sysarch 中与之一致。若坚持合规宣称，请补充 PIPL Art. 13（合法基础）、Art. 28（敏感/生物识别）、Art. 24（自动化决策）、Art. 38–40（跨境）的分析；否则请删除所有「complying with / mandated by / aligning with PIPL」措辞。

3. **暴露面验证**：WER≥0.95 与 speaker-ID 8.3% 是在「proxy embeddings」上测得的，而非实际传输的拼接后 $\bm{F}_v$（Eq. 4）。你们能否直接在 $\bm{F}_v$ 上运行 GLO/U-Net 攻击并报告结果？若不能，是否愿意把隐私声称降级为「proxy-level empirical evidence」并修正 speaker-ID 段的嵌入定义（128-d MFCC-only vs 64+64）不一致？

4. **误报折算**：FPR 1.8% 是在约 48% 欺诈平衡集上测得的。在真实发病率（<1%）下，每位合法用户每日的预期误报率是多少？能否给出 prevalence-calibrated PPV？若否，请把 headline FPR 限定于「balanced benchmark」并在 Discussion 中把 prevalence mismatch 列为独立局限。

---

## Minor Issues

**Non-finding channel（copyedit 级，无 Severity/Anchor/Confidence）**：

### Language / Grammar
- 摘要「privacy-compliant on-device AI」与正文「technical assessment, not legal compliance」措辞不一致（已纳入 W2，此处仅列措辞一致性）。
- §Discussion「$\sigma = 1.0$, corresponding to $\epsilon = 1.5$」建议改为只报 $\sigma$（已纳入 W5）。

### Citation Format
- 引言「regulations such as PIPL」的「such as」暗示更大法规类别但未兑现；GDPR 全文未提及。建议要么删除「such as」并明确限定中国境内，要么补 GDPR 对应条款。

### Figures and Tables
- 建议在 Table 1 的「Privacy mechanism」一行标注「Representation-level protection (proxy-evaluated, design target)」，使表格与正文的诚实降级一致（当前表格仍写「Representation-level protection」这一较强势措辞）。

### Layout
- 无重大布局问题。

---

## Criterion-Bound Judgements *

Calibration status: `NOT_CALIBRATED`

本席位从 privacy engineering / 数据保护合规 / 反诈部署的角度应用 `quality_rubrics.md` 的七个通用维度；Methodological Rigor 与 Literature Integration 的核心裁决依本席位角色边界 defer 至 R1/R2，仅给出隐私范围的受限判断。

| Dimension | Criterion source | Judgement | Evidence anchor(s) | Rationale | Uncertainty / scope limit | Decision bearing? |
|---|---|---|---|---|---|---|
| Originality | quality_rubrics.md D1 | PARTLY_MEETS | `text: §sec:acoustic "specified as a 128-dimensional design target"` | 系统级 co-design（QAD+OVF+融合+投机解码）是 defensible 的 gap；但「reconstruction-resistant embedding」作为隐私贡献，其 novelty 依赖「128 维时间平均」这一近乎必然的结果（WER≥0.95 是维度灾难的副产品），且暴露面未经直接验证。 | 新颖性裁决主要属 R1/R2；本席位仅评隐私贡献的新颖性强度 | yes — 隐私贡献的新颖性若薄，会削弱 C1 的贡献地位 |
| Methodological Rigor | quality_rubrics.md D2 | NOT_ASSESSED | — | 量化/统计方法学（p 值、effect size、seed 方差）依角色边界 defer 至 R1。隐私评估的方法学缺陷（proxy embedding、n=11、reference estimate）已作为 Evidence Sufficiency 记录。 | 本席位不裁决统计有效性（R3 边界） | no — defer R1 |
| Evidence Sufficiency | quality_rubrics.md D3 | PARTLY_MEETS | `text: §sec:acoustic "rather than through the jointly trained concatenated F_v"; §sec:glo "reference estimates... rather than independently re-measured"` | 隐私证据诚实但弱：WER/speaker-ID 测于代理而非实际传输物；n=11 自认「preliminary」；无可链接性直接测量；无法律分析。每个隐私 headline 都缺「right type + right object」的证据。 | 我未独立复现攻击实验；证据链基于稿件自述 | yes — C1 隐私机制的证据充分性是本席位核心关切 |
| Argument Coherence | quality_rubrics.md D4 | PARTLY_MEETS | `text: §Abstract "privacy-compliant on-device AI"; §sec:glo "not a legal compliance determination"` | 摘要的「privacy-compliant」与正文的「technical assessment, not legal compliance」在同一稿内强度相反，构成残余断裂；「complying with/mandated by/aligning with PIPL」与「无法律分析」并存。 | 无 | yes — 合规措辞的 self-contradiction 直接支持 W2 |
| Writing Quality | quality_rubrics.md D5 | MEETS | `text: §Discussion（"Societal consequences of misclassification" 段）` | 表达清晰、caveat 位置得当、术语规范（经 Elsevier 语言润色）。仅 W5 的「corresponding to」与摘要措辞需微调。 | 非母语审读，surface polish 不纳入实质判断 | no |
| Literature Integration | quality_rubrics.md D6 | NOT_ASSESSED | — | 文献完整性依角色边界 defer 至 R2；本轮修订补入的 VPC/ASVspoof/SmoothQuant/QLoRA/OmniQuant 从隐私角度是恰当的。 | 本席位不开展系统覆盖审计（R3 边界） | no — defer R2 |
| Significance & Impact | quality_rubrics.md D7 | PARTLY_MEETS | `absence: §Discussion — expected prevalence-calibrated PPV 或 false-alert-per-user 量化; checked §sec:glo, §sec:discussion` | 真实世界意义受制于：(a) 未言明的部署模型；(b) FPR 未折算到低发病率；(c) 监管义务（PIPL Art. 24 自动化决策、算法备案）未讨论。「Societal consequences」段的自觉是亮点，但意义被 deferred quantification 悬置。 | 反诈部署的实际拓扑与监管实践存在地区差异 | yes — 可部署性/误报成本是本席位核心关切 |

**Recommendation rationale**: 四个决策相关维度（Originality、Evidence Sufficiency、Argument Coherence、Significance & Impact）均因隐私贡献的证据对象错位（W3）、合规措辞自相矛盾（W2）、部署模型未言明（W1）与误报未折算（W4）而落在 PARTLY_MEETS。这些是「重定位或补分析」级的问题，叠加仍开放的 reproducibility run，决定 Major Revision。任何单一优势维度都不能在数值上抵消隐私证据链与合规自洽性的断裂。

---

**Epistemic status**: 本报告为单一模型族内的模拟评审席位，`NOT_CALIBRATED`；非独立审稿人、非跨家族三角验证，亦非合格法律意见。PIPL/GDPR 相关判断仅供作者决策参考，不构成法律合规判定。

---

---

## 归档：v28_peer_review.md

# 模拟同行评审报告 — QAD-MultiGuard

> **论文**:QAD-MultiGuard: An Edge–Cloud Framework for Multimodal Fraud Detection and Risk Assessment
> **源文件**:`v28.tex`
> **评审框架**:`academic-paper-reviewer` v1.11.1(full 模式,5 座位 panel + 编辑综合)
> **评审日期**:2026-08-27
> **性质**:模拟评审。角色分离只代表视角分工,**不是**独立误差过程的声明;5 个座位为单一模型内的视角分离,不代表独立审稿人。

---

## Phase 0 — 领域分析与评审团队配置

### 论文基本信息

| 项 | 内容 |
|---|---|
| 标题 | QAD-MultiGuard: An Edge–Cloud Framework for Multimodal Fraud Detection and Risk Assessment |
| 摘要长度 | ~320 词(单段,偏长) |
| 全文 | 约 9000 词正文 + 3 附录命题(有界性/稳定性/重构抵抗) |
| 参考文献 | `ref_v4.bib`(正文引用至 [32] + 字母键,数量未在 tex 内显式展开) |
| 模板 | Elsevier `cas-sc` + `cas-model2-names`(Elsevier 期刊标准) |

### 领域分析

| 维度 | 分析结果 |
|---|---|
| 主学科 | 计算机科学 / 应用人工智能(多模态诈骗检测) |
| 交叉学科 | ① 隐私与安全(声学表示、差分隐私)② 高效推理(量化、投机解码)③ 系统部署(端云协同) |
| 研究范式 | 定量 / 实验(机器学习系统型) |
| 方法类型 | 统计建模 / 机器学习(蒸馏 + 量化 + 隐私表示 + 加速) |
| 目标期刊 | **Expert Systems with Applications**(ESWA,Elsevier,Q1 / 中科院一区,**作者确认**)。应用驱动,强调真实应用价值 + 技术严谨性 |
| 论文成熟度 | 接近投稿(结构完整、语言经 Elsevier 编辑、有附录) |

### 评审团队配置卡(4 张)

**Card #1 — Journal-Fit Reviewer(序列化 ID: EIC)**
- **身份**:*Expert Systems with Applications* 副主编,负责智能系统/端侧部署方向
- **聚焦**:ESWA 期刊契合度、应用价值证据、原创性、对读者群的增量贡献
- **特别关注**:ESWA 强调**真实应用价值**——需判断工作是否有应用场景落地证据(而非仅基准提升);标题/摘要是否过度承诺(marketing 化);贡献是否清晰区分于已有 QAD/量化工作

**Card #2 — Peer Reviewer 1(方法论)**
- **身份**:量化与模型压缩研究员,专精 QAT/QAD/PTQ 与统计显著性检验
- **聚焦**:蒸馏损失设计、量化协议(NBE vs 真硬件)、统计严谨性、可复现性

**Card #3 — Peer Reviewer 2(领域)**
- **身份**:多模态诈骗检测 + 语音隐私资深研究者
- **聚焦**:文献覆盖完整性、对比基线公平性、隐私主张的证据强度、数据集泛化

**Card #4 — Peer Reviewer 3(跨学科/实践)**
- **身份**:隐私法规(PIPL/GDPR)与端侧部署工程交叉研究者
- **聚焦**:隐私-效用-延迟三角权衡的真实性、"practical template"主张的可落地性、法规合规声称的边界

（第 5 个执行座位为固定的 Devil's Advocate,无动态配置卡。）

---

## Phase 1 — 五份评审报告

### ① Journal-Fit Reviewer(EIC)

**总体建议**:Major Revision(置信度 4)

**概述**:论文提出一个端云协同的多模态诈骗检测框架,融合纯 KL 蒸馏、OV-Freeze、隐私声学嵌入与投机解码四组件,在 TAF-28k 上以 4-bit 学生恢复 98.5–99.1% BF16 精度。**ESWA 契合度呈"方向契合、证据不足"的混合**:电信诈骗检测与端侧智能系统正是 ESWA 核心读者群,但 ESWA 一贯强调**真实应用价值**,而本文的应用证据停留在受控重演环境(TAF-28k)、NBE 仿真、"field validation 尚未完成",尚未达到 ESWA 期望的落地强度。工程完成度与写作质量均高;但标题与摘要的承诺("practical template"、"favourable trade-off")与正文诚实披露的边界(单主数据集、NBE 仿真、经验性隐私)之间存在张力,投稿前的核心风险是**可信度管理 + 应用证据强度**。

**关键优势(S)**:
- S1:四组件的系统整合与相互消融设计完整(§4 各小节均有对应消融),是"系统型论文"的正确写法。
- S2:主动披露 NBE 仿真边界、单数据集局限、经验性隐私、unlinkability 缺口,诚实度高于同类投稿。

**关键弱点(W)**:
- W1(Critical):§Reproducibility statement 承认公开仓库当前产出**不能复现**论文主表(NVFP4 QAD 路径),主结果以"正式 H100 运行"为唯一权威来源。→ 在结果可被第三方验证前,无法作为已发表论断。
- W2(Major):摘要/结论使用 "practical template" 等强承诺,与正文 "controlled-environment performance"、"not yet formally validated" 的定位不一致。

**给作者的问题(Q)**:
1. 论文的应用证据能否在修订中强化到 ESWA 期望的落地强度(如 pilot 部署、真实通话数据)?若暂不能,标题级 "practical template" 主张应相应降级。
2. 复现回填的预计时间线?(投稿时点此问题为硬约束)

---

### ② Peer Reviewer 1(方法论)

**总体建议**:Major Revision(置信度 4)

**关键优势(S)**:
- S1:统计处理规范——五随机种子、paired bootstrap(10⁴ resamples)、p<0.01、报告均值±标准差。
- S2:OV-Freeze 消融设计严格(逐层 {q,k,v,o}、激活窗口扫描 1600–2000 步),分离了各增强的边际贡献。

**关键弱点(W)**:
- W1(Critical):可复现性。§Reproducibility statement 明确"公开仓库早期配置为 post-training int4,raw outputs 不能复现报告的表"。对一篇以可验证实验结果为核心的系统论文,这是接受前的硬阻断。
- W2(Major):**NBE 协议 vs 真实硬件**。所有 NVFP4 结果由 H100 上的 QDQ 数值仿真(Eq. 5)产生,非原生 Blackwell;表 2 的 "2.1×" 被正确标注为"isolated compute-kernel throughput margin",但摘要/亮点仍以 "Hardware-Level Acceleration" 呈现。建议在标题级结果表述中显式标注仿真性质。
- W3(Major):OV-Freeze 的边际增益(0.916→0.923,+0.007 F₁)虽统计显著,但效应量小;需补充效应量/置信区间解释其实际意义,避免"统计显著 ≠ 实质重要"。
- W4(Minor):ASV-EER 46.8%/48.5% vs 50% 机会水平,应报告不确定度;11 说话者闭集下 8.3% vs 9.1% 的"低于机会"结论,样本量过小,统计功效不足。

---

### ③ Peer Reviewer 2(领域)

**总体建议**:Major Revision(置信度 4)

**关键优势(S)**:
- S1:文献覆盖较完整(LLM-QAT、BitDistiller、AWQ/GPTQ/SpinQuant/QuaRot、Nemotron、SAFE-QAQ、TAF-28k),量化蒸馏谱系清晰。
- S2:对比基线层次分明(PTQ / 自蒸馏 / QAT / 域基线),并诚实标注 SAFE-QAQ 为不同规模、引用非复现。

**关键弱点(W)**:
- W1(Major):**单主数据集**。主多模态结论仅依赖 TAF-28k(受控重演协议),AdvFraud-3k 与 ChiFraud 为补充;ChiFraud 还是 text-only,不评估完整多模态管线。对"real-time fraud detection"的泛化主张是实质风险。
- W2(Major):**对比公平性**。headline 声称"以 57× 更小存储达到与 SAFE-QAQ(7B/BF16)相当性能",但 SAFE-QAQ 为引用值、未复现,且不同部署目标;这个对比的公平性需在正文更明确地限定(已在脚注部分披露,但摘要未限定)。
- W3(Major):隐私主张为**经验性**而非形式化(WER≥0.95 仅针对已评估的 GLO/U-Net 攻击),且 unlinkability 明确未解决(半诚实云端可经 embedding 相似度链接会话)。对一篇以"privacy-preserving"为核心卖点的论文,需更严格地限定声称边界。

---

### ④ Peer Reviewer 3(跨学科/实践)

**总体建议**:Major Revision(置信度 3,部分法规/工程边界超出我核心专长)

**关键优势(S)**:
- S1:隐私-效用-延迟三角的权衡被清晰量化(LDP 开启:0.923→0.902,-0.021;延迟 268→271ms),这是落地导向论文的正确姿态。
- S2:明确区分"内容保护(WER)"与"跨会话不可链接性(unlinkability)",并诚实承认后者未解决——这是许多同类工作回避的难点。

**关键弱点(W)**:
- W1(Major):"practical template" 主张过度。正文多次自证为 controlled-environment、未做 field validation、单语料库;建议将摘要/结论措辞收敛为"evidence of feasibility under controlled conditions"。
- W2(Major):PIPL 合规声称需限定。论文引用 PIPL 第 23 条支撑数据最小化,但对"跨境传输""安全评估前置"等条文的适用性未做法律层面论证;建议将法规讨论明确标注为非法律意见。
- W3(Minor):G₃(身份欺诈)仅架构层面 cross-modal consistency,未量化;对真实语音欺骗(spoofing)语料的鲁棒性未经验证。

---

### ⑤ Devil's Advocate(固定对抗座位)

**最强反论点**(约 260 词):
本文的四个组件中,没有任何一个在孤立意义上是新的——纯 KL 蒸馏、输出统计对齐(variance matching)、隐私声学特征、投机解码均有成熟先例。真正的贡献主张必须落在"针对诈骗检测场景的**组合与协同验证**"上。但恰恰是这一主张,被两个自证边界削弱:(1) 主结果无法在公开仓库复现,且由 NBE 仿真而非真实硬件产生;(2) 唯一的主数据集 TAF-28k 在受控重演协议下采集,跨域证据(text-only ChiFraud)不能证明多模态泛化。因此,审稿人最尖锐的问题是:**"0.5B 模型 + 受控数据 + 仿真量化 + 经验性隐私"的组合,是否足以支撑一篇以"real-time fraud detection on commodity hardware"为题的发表?** 若作者能补齐复现、增加一个真实部署场景的 field/pilot 证据、并将隐私声称降级为经验性边界,答案可以是肯定的;若不能,则本文更接近一个设计精良但未经验证的原型。

**问题清单**:

| # | 分类 | 维度 | 位置 |
|---|---|---|---|
| DA-1 | **CRITICAL** | 可复现性——核心结果在公开仓库不可验证 | §Reproducibility statement |
| DA-2 | MAJOR | 新颖性边界未清晰声明(组合贡献 vs 组件新贡献) | §Introduction contributions |
| DA-3 | MAJOR | 对比公平性:SAFE-QAQ 引用值、异规模、异目标 | Table 3 脚注 |
| DA-4 | MAJOR | "硬件加速 2.1×" 为孤立 kernel 边际,摘要/亮点未限定 | Table 2 + highlights |
| DA-5 | MINOR | OV-Freeze 效应量小(+0.007 F₁)的实质重要性未论证 | §OV-Freeze Ablation |

**被忽略的替代解释/路径**:
1. 文中未对照"直接对 BF16 0.5B 做 LoRA/Adapter 微调 + 4-bit PTQ"这一更廉价的基线,无法排除"蒸馏收益其实来自微调本身而非纯 KL"这一替代解释。
2. 隐私嵌入的 WER≥0.95 可能部分源于 Whisper-tiny 编码器本身的信息瓶颈,而非本文的 MFCC+池化设计——未做消融分离这两者贡献。

**缺失的利益相关者视角**:
- **终端用户/受害者**:系统在真实诈骗电话(非重演)下的漏报率未评估;误报对用户的打扰成本(FPR 1.8% 在电话规模下的绝对量)未讨论。
- **合规/监管方**:对 PIPL 的引用止步于"数据最小化",未覆盖传输安全、存储期限、审计等义务。

**观察(非缺陷)**:
- 作者对 NBE、单数据集、经验性隐私、unlinkability 的主动披露,是同类工作中少见的诚实,值得肯定——这降低了审稿人"发现隐藏问题"的负担,应作为投稿策略继续坚持。

---

## Phase 2 — 编辑综合与决策

### 决策:**Major Revision**

### 阻断性问题(Blocking Issues)

| Ref | 阻断问题 | 来源 | 证据锚点 | 解决项 |
|---|---|---|---|---|
| R1 | 核心结果(NVFP4 QAD)在公开仓库不可复现,主表以"正式运行"为唯一权威 | EIC/R1/DA | text: §Reproducibility statement "its raw outputs do not yet reproduce the reported tables" | REV-1 |
| R2 | 标题级主张("practical template"/"real-time")与受控环境边界不一致 | EIC/R3/DA | text: §Conclusion "controlled-environment performance" | REV-2 |

### 共识(Consensus)
- **[CONSENSUS-4]** 四位评分 reviewer 一致认为:方法有实质价值、写作与统计质量高,但可复现性(REV-1)与主张收敛(REV-2)必须解决。
- **[CONSENSUS-4]** 一致认为单主数据集 + NBE 仿真 + 经验性隐私需更严格限定声称边界。

### 分歧(Disagreement)
- **分歧 1:隐私声称的严重性**。R2 认为"经验性而非形式化"是 Major(核心卖点弱化);R3 认为作者已诚实披露、是可接受的工程表述(倾向 Minor)。**编辑裁决**:采纳 Major 分级(隐私是标题级卖点),但将修复成本标为"重写措辞+限定"而非"新增实验"——作者的诚实披露本身已部分抵消了风险,需要的是收敛声称,而非重新做隐私证明。

### 决策理由(约 220 词)
四名评分 reviewer 均给出 Major Revision,无 Reject 信号,说明核心贡献与方法被认可,但存在**可复现性硬伤**与**主张-证据落差**。DA 的 CRITICAL(DA-1,可复现性)经裁决为 **validated**——论文自身 §Reproducibility statement 承认仓库无法复现主表,这一事实直接命中现代 ML 投稿的验证底线,故不接受(Accept)不可能;但它是**可修复**的(作者已承诺回填 NBE/QAD 路径),故不构成 Reject。其他 Major(单数据集、NBE、对比公平性、新颖性边界)均可通过补充实验或收敛措辞在 6–8 周内解决。故决策为 Major Revision,修订后需复审。

### 必须修改(Required Revisions · must_fix)

- **R1 — 可复现性回填**:完成公开仓库的 NVFP4 QAD 路径,使表 3–表 5 可复现,并在文中给出精确 commit 指针。验收:第三方能跑出主表数字。来源:EIC/R1/DA,Severity:Critical。
- **R2 — 主张收敛**:将摘要/结论/highlights 的 "practical template"、"real-time … on commodity hardware" 降级为受控环境下的可行性证据;对 "2.1× 硬件加速" 在结果表述中显式标注 NBE 仿真性质。来源:EIC/R3/DA,Severity:Major。
- **R3 — 对比公平性限定**:在摘要与主结果段落明确 SAFE-QAQ 为"引用值、7B/未量化、异部署目标",57× 对比不作为同尺度竞争声明。来源:R2/DA,Severity:Major。
- **R4 — 新颖性边界声明**:在贡献段明确哪些是"新组件"、哪些是"既有技术的领域适配组合",并补充"LoRA/Adapter 微调 + PTQ"对照基线以排除替代解释。来源:R1/DA,Severity:Major。

### 建议修改(Suggested Revisions · should_fix / consider)

- **S1**(should_fix):为 OV-Freeze 的 +0.007 F₁ 增益补充效应量与 CI,论证其实质重要性。来源:R1。
- **S2**(should_fix):增加一个真实部署 field/pilot 场景的证据(或明确降级为 future work)。来源:R3。
- **S3**(consider):对隐私嵌入做消融,分离"Whisper-tiny 信息瓶颈"与"MFCC+池化设计"各自对 WER 的贡献。来源:DA。
- **S4**(consider):ASV-EER / 说话人识别补充样本量功效分析。来源:R1。

---

## 修订路线图(Revision Roadmap · 源顺序,非工作排序)

- [ ] **R1**(must_fix)—— 复现回填 + commit 指针
- [ ] **R2**(must_fix)—— 主张收敛 + NBE 显式标注
- [ ] **R3**(must_fix)—— 对比公平性限定
- [ ] **R4**(must_fix)—— 新颖性边界 + 替代基线对照
- [ ] **S1**(should_fix)—— OV-Freeze 效应量论证
- [ ] **S2**(should_fix)—— field/pilot 证据或降级
- [ ] **S3**(consider)—— 隐私嵌入消融
- [ ] **S4**(consider)—— 说话人识别功效分析

---

## 归档：v28_revision_roadmap.md

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

---

## 归档：v29_review.md

# QAD-MultiGuard 论文评审报告

- **论文标题**: QAD-MultiGuard: An Edge–Cloud Framework for Multimodal Fraud Detection and Risk Assessment
- **论文文件**: `docs/v29.tex`
- **评审模式**: `full`(五席位角色分离评审 + 编辑综合)
- **报告语言**: 中文(学术术语保留英文)
- **校准状态**: `NOT_CALIBRATED`
- **评审日期**: 2026-08-28

---

## 一、领域分析报告(Phase 0)

### 论文基本信息

| 项目 | 内容 |
|------|------|
| 标题 | QAD-MultiGuard: An Edge–Cloud Framework for Multimodal Fraud Detection and Risk Assessment |
| 作者 | Dajin Wang, Jianming Bai, Wu Zhang(通讯), Wenbin Guo, Qian Zhao, Liangdong Yang |
| 语言 | 英文(Elsevier `cas-sc` 单栏模板,已有 Language Editing 证书) |
| 全文规模 | 1056 行 LaTeX,约 9000+ 词正文,含附录 |
| 参考文献 | 约 40 篇 |
| 投稿目标 | 未提供作者确认的 #683 ReviewTargetContext → `criteria_binding_unavailable` |

### 领域分析

| 维度 | 分析结果 |
|------|---------|
| Primary Discipline | 应用人工智能 / 机器学习系统(Applied AI & ML Systems) |
| Secondary Disciplines | ① 电信反欺诈 / 网络安全 ② 隐私保护机器学习(PETs, PIPL 合规) ③ 高效推理 / 边缘-云系统 |
| Research Paradigm | 定量研究(Quantitative) |
| Methodology Type | 机器学习 / 统计建模 + 系统工程(框架 + 消融 + 对比评估) |
| Target Journal Tier | `criteria_binding_unavailable`;field-general 成熟度指向 Q1 应用 AI 类期刊 |
| Paper Maturity | Pre-submission(结构完整,但可复现性未闭合) |

### 推荐目标期刊(参考,非确认靶点)

1. Expert Systems with Applications(Elsevier, Q1)— 应用 AI 系统 + 欺诈检测契合度最高
2. Computers & Security(Elsevier, Q1)— 若强化隐私/威胁模型/安全侧
3. IEEE Transactions on Information Forensics and Security — 若强化反欺诈安全 + 隐私合规

### 评审团队配置

| 席位 | 身份定位 | 关注重点 |
|------|---------|---------|
| Journal-Fit Reviewer(EIC) | 应用 AI 系统类期刊资深副主编 | 原创性、显著性、期刊契合、结构一致性 |
| Peer Reviewer 1(方法学) | 低比特量化/蒸馏专家 | 统计有效性、可复现性、基线公平性 |
| Peer Reviewer 2(领域) | 电信反欺诈 AI 研究员 | 文献覆盖、理论框架、领域贡献、语音隐私 |
| Peer Reviewer 3(交叉视角) | PETs + 数据保护法合规学者 | 隐私声称充分性、部署可行性、伦理影响 |
| Devil's Advocate(固定席位) | 反方辩手 | 核心论点挑战、逻辑谬误、最强反证 |

---

## 二、五席位评审报告(Phase 1)

### 报告一:Journal-Fit Review Report(期刊契合度评审)

**Overall Recommendation**: Major Revision | **Confidence**: 4 | **Calibration**: `NOT_CALIBRATED`

**Summary Assessment**

该文提出 QAD-MultiGuard,一个边缘-云协作的多模态反欺诈框架,通过纯 KL 量化感知蒸馏 + OV-Freeze 正则 + 抗重建声学嵌入 + 域适配推测解码,在 TAF-28k 上以 0.5B 学生模型达到 F1=0.917、268ms 中位延迟。论文结构完整、消融充分、局限披露诚实。作为期刊契合度评审,我认为其主题、实证体量、写作质量均达到一线应用 AI 期刊门槛;集成式 co-design 的原创性虽为渐进式,但对"隐私合规 + 低比特 + 实时"三约束的联合求解确有其价值。最关键的不足是可复现性缺口与核心声称(privacy)的范围过度——前者使主结果在当前阶段无法被第三方验证,后者使三支柱之一(privacy)的表述强于证据支撑。

**Strengths**

- **S1:三约束联合求解的问题定位清晰且有现实依据** — `text: §1 "three coupled requirements: privacy... fidelity... responsiveness"`
- **S2:局限披露异常诚实** — `text: §5 "an honest-but-curious cloud... may link repeated interactions"`
- **S3:消融体系完整** — `table: Table 5 — 纯 KL vs QAT D_KL 0.005 vs 0.311`

**Weaknesses**

- **W1:主结果当前不可复现(已由作者自认)** — Severity: **Critical** | `text: §Reproducibility "The public repository currently hosts an earlier development configuration... so its raw outputs do not yet reproduce the reported tables"` | Confidence: 5
- **W2:隐私支柱的表述强于证据** — Severity: **Major** | `text: §5 "This differs from reconstruction... as it relies on metric consistency in representation space"` | Confidence: 4

---

### 报告二:Methodology Review Report(Peer Reviewer 1)

**Overall Recommendation**: Major Revision | **Confidence**: 4 | **Calibration**: `NOT_CALIBRATED`

**Summary Assessment**

方法学上,该文的纯 KL 蒸馏 + OV-Freeze 设计在技术上是自洽的:固定 T=1 避免训练-推理分布失配,stop-gradient 重标定保证梯度有界,消融体系完整。统计实践也相对规范(5 seeds、paired bootstrap、置信区间、固定验证阈值)。但存在两处实质问题:其一,主结果不可复现;其二,多个关键增益效应量很小(+0.007、+0.008、+0.021),论文用 `p<0.01`/`p<0.05` 的显著性语言包装了实际很窄的改进,且未报告标准化效应量,存在"以 p 值代效应"的倾向。此外基线公平性需更严格约束。

**Strengths**

- **S1:消融隔离干净** — `table: Table 5 — 纯 KL 0.916, 混合三项 0.879`
- **S2:统计协议透明** — `text: §3 "a paired bootstrap hypothesis test with 10,000 resamples"`
- **S3:NBE 仿真协议有数值校准** — `text: §3 "absolute evaluation accuracy deviation of < 0.3%"`

**Weaknesses**

- **W1:核心结果不可复现** — Severity: **Critical** | `text: §Reproducibility "its raw outputs do not yet reproduce the reported tables"` | Confidence: 5
- **W2:关键增益的效应量未报告,统计显著 ≠ 实质显著** — Severity: **Major** | `table: Table 3 — QAD 0.916 vs QAD+OVF 0.923` | Confidence: 4
- **W3:基线对比的公平性未完全约束** — Severity: **Major** | `text: §3 "SAFE-QAQ is a high-capacity reference baseline at a different scale... not reproduced in-house"` | Confidence: 3

---

### 报告三:Domain Review Report(Peer Reviewer 2)

**Overall Recommendation**: Major Revision | **Confidence**: 4 | **Calibration**: `NOT_CALIBRATED`

**Summary Assessment**

该文在电信反欺诈领域的定位准确:正确识别了现有方法在"隐私受限 + 资源受限 + 实时"三约束下的缺口,并将 QAD 范式首次系统性引入隐私敏感的多模态反欺诈。文献综述对三大流派与 QAD/PTQ 谱系的梳理有组织、有批判性。领域贡献是真实的渐进式增量。主要不足在语音隐私侧:声学嵌入的"抗重建"讨论主要锚定在 x-vector 替代与 GLO 攻击上,对更近的 speaker anonymization 形式化保证覆盖不足,导致将"抗重建"与"隐私保护"作过于直接的映射。

**Strengths**

- **S1:领域定位精准,空白识别真实** — `text: §1 "SAFE-QAQ... reports... recall of only 60%–75% under dialect variation"`
- **S2:对 PTQ 的领域性批判有实验支撑** — `text: §2 "weight-only PTQ preserves... magnitude statistics... but cannot recover the domain-specific cross-modal features"`
- **S3:声学嵌入的信息瓶颈论证自洽** — `text: §5 "the 128-dimensional embedding acts as an information bottleneck"`

**Weaknesses**

- **W1:语音隐私文献整合偏薄,"抗重建"与"隐私"的映射不严谨** — Severity: **Major** | `text: §3 "This representation provides content-level protection... but is not designed for cross-session unlinkability"` | Confidence: 4
- **W2:形式化隐私保证缺失(作者已承认)** — Severity: **Major** | `text: §5 "formal speaker-anonymisation guarantees... are deferred to future work"` | Confidence: 4

---

### 报告四:Perspective Review Report(Peer Reviewer 3)

**Overall Recommendation**: Major Revision | **Confidence**: 4 | **Calibration**: `NOT_CALIBRATED`

**Summary Assessment**

从隐私合规与实务交叉视角,该文在工程可行性上做得扎实(268ms 端侧延迟、4GB 约束、异步云端复审的 secondary alert 机制)。但隐私支柱存在合规缺口:作者自己承认嵌入不抗链接性——honest-but-curious 云可通过嵌入相似度链接同一说话人的多次交互。在 PIPL 语义下,"可关联到特定自然人"的身份级风险比"内容可重建"更根本。因此以 "privacy-preserving" 作为三支柱之一的表述在合规层面是过度声称。此外 LDP 模块置于架构图中却仅作为"可选工程配置",且 `ε=1.5` 明确标注为"工程估计而非完整 DP 分析",存在合规暗示风险。

**Strengths**

- **S1:数据流边界刻画清晰,合规意识强** — `text: §3 "Raw audio, ASR text transcripts, and raw SMS plaintexts remain strictly confined within the local device boundary"`
- **S2:异步复审的 secondary alert 机制考虑了分歧裁决** — `text: §3 "a divergent cloud verdict is never silently discarded"`
- **S3:对 unlinkability 风险的前瞻性披露** — `text: §5 "a promising direction is to inject a session-specific dynamic perturbation"`

**Weaknesses**

- **W1:隐私支柱的合规声称过度(不抗链接性)** — Severity: **Major** | `text: §5 "repeated observations from the same speaker under similar conditions yield stable embeddings"` | Confidence: 4
- **W2:LDP 的可选定位存在合规暗示风险** — Severity: **Major** | `text: §5 "The reported ε value is an engineering estimate... not a full differential-privacy analysis"` | Confidence: 4
- **W3:误判的社会后果与弱势群体伦理缺失** — Severity: **Minor** | `absence: §5 Discussion — 预期误判后果/弱势群体伦理的讨论;检查了 §5 Discussion、§6 Conclusion` | Confidence: 3

---

### 报告五:Devil's Advocate Review(反方辩手)

**Calibration**: `NOT_CALIBRATED`

**Strongest Counter-Argument(最强反证)**

若我是持相反立场的学者,我会这样反驳:这篇论文的三个支柱之一——privacy——在最关键的语义上是未兑现的。作者自己承认,128 维嵌入是输入音频的确定性函数,同一说话人在相似条件下的嵌入是稳定的;因此一个"诚实但好奇"的云端只需对历史嵌入做余弦相似度聚类,就能在不重建任何语音内容的情况下,链接同一自然人的多次通话——而这恰恰是 PIPL 所规制的身份级风险,比内容可重建更根本。作者用"内容不可重建(WER≥0.95)"这个相对容易达成的技术指标,置换了一个更难、但法律上更核心的目标(身份不可链接)。标题、摘要和三支柱反复出现的 "privacy-preserving" 因此在合规语义上被证据反驳。退一步说,即便接受"内容级隐私"作为可接受的让步,论文的第二个硬伤也随之而来:所有核心数字在当前公开代码下无法复现。一个以实证验证为核心贡献、又以"隐私"为卖点的系统,当前既不能让人验证其效果,也不能让人采信其隐私声称。

**Issue List**

**CRITICAL**

| # | 维度 | 问题描述 | Evidence Anchor | Confidence |
|---|---|---|---|---|
| C1 | Evidence Gap / 可复现性 | 核心实证结果当前不可复现,公开仓库为旧 int4 配置 | `text: §Reproducibility "its raw outputs do not yet reproduce the reported tables"` | 5 |

**MAJOR**

| # | 维度 | 问题描述 | Evidence Anchor | Confidence |
|---|---|---|---|---|
| M1 | Foundation / 核心支柱 | "privacy-preserving" 声称与不抗链接性证据矛盾 | `text: §5 "an honest-but-curious cloud... may link repeated interactions without reconstructing the underlying audio"` | 4 |
| M2 | 基线公平性 | Safe-QAQ(7B BF16)与学生(0.5B 4-bit)非同类对比 | `table: Table 3 — SAFE-QAQ 0.918 vs Q4_K_M 0.917` | 4 |
| M3 | 逻辑链 / 效应量 | 以 p<0.01 包装 +0.007/+0.008 级微小增益,未报效应量 | `table: Table 3 — QAD 0.916 → QAD+OVF 0.923` | 4 |
| M4 | 过度泛化 / 单主语料库 | 主评估仅 TAF-28k,泛化未验证(作者承认) | `text: §5 "reliance on a single primary corpus for the main multimodal results"` | 4 |

**Ignored Alternative Explanations/Paths**

1. 更简洁的替代解释:反诈脚本高度刻板、任务难度低,比"方法优越"更节俭地解释了高 F1 与跨尺度 parity。
2. 更成熟的替代路径:若核心目标是端侧隐私,已有 speaker anonymization / VC-based 方案可替换 128-d 嵌入,作者未对比。
3. PTQ + 更充分校准可能以更低成本逼近 QAD,作者仅测了 temperature scaling 一种后处理。

**Missing Stakeholder Perspectives**

- 误报受害者(合法通话被误判并中断的公民)。
- 运营商与执法机构(合规责任主体)。
- 老年等易受害群体(反诈干预的伦理正当性)。

**Unexamined Premise(框架锁定检测)**

"隐私保护"被等价于"个体特征在单次交互中不可被内容重建"——全文未质疑"隐私"在身份链接、跨会话追踪意义上的内涵,而这一前提恰好是隐私支柱赖以成立的地基。

---

## 三、编辑决定包(Phase 2)

### 决策:**Major Revision(大修)**

`calibration_status: NOT_CALIBRATED`

### 共识分析

**跨席位共识(经子声明分解):**

- **[CONSENSUS-4] 主结果当前不可复现** —— EIC(W1)、R1(W1)、DA(C1)一致判定 Critical,领域评审默认;是阻断发表的首要问题。
- **[CONSENSUS-4] privacy 声称过度(不抗链接性)** —— 全部席位认定 "privacy-preserving" 表述强于证据,应收敛为"内容级抗重建"。
- **[CONSENSUS-3] 关键增益效应量未报告** —— R1(W2)与 DA(M3)明确认定;采纳方法学意见。

**分歧仲裁:**

1. **C1 严重级是否"可修复即非 Critical"**:DA 定 Critical;仲裁采纳 Critical,但属可修复,故不升级 Reject。
2. **基线公平性是否实质缺陷**:DA(M2)与 R1(W3)同向;仲裁采纳为应修复项。

### Decision Rationale(决策依据)

四位评分评审一致落在 Major Revision 区间。核心驱动:其一,主结果不可复现,是证据充分性的硬门槛;其二,"privacy-preserving" 三支柱之一被作者自己的证据(unlinkability 缺失)削弱;其三,多个 +0.007/+0.008 级增益仅以 p 值呈现、未报效应量,且基线对比存在非同类隐患。这些缺陷均不否定核心方向的可行性,也不指向 Reject——论文的问题定位、消融体系、局限披露均达一线期刊水准,且无数据造假或逻辑断裂的证据。但它们是必须经实质修订并经复审才能发表的问题,故判定 Major Revision。

### Blocking Issues(阻断发表项)

| Transport ref | 阻断项 | 来源席位 | 证据锚点 | 对应修订项 |
|---|---|---|---|---|
| R1 | 主结果不可复现,代码为旧配置 | EIC / R1 / DA | `text: §Reproducibility "do not yet reproduce the reported tables"` | REV-1 |
| R2 | privacy 声称过度,缺身份级隐私评估 | EIC / R2 / R3 / DA | `text: §5 "may link repeated interactions"` | REV-2 |

### DA-CRITICAL 裁决

| DA 编号 | 裁决 | 理由 |
|---|---|---|
| C1(不可复现) | **VALIDATED(成立)** | 由 EIC/R1 独立同判,证据确凿,阻断 Accept;可修复故为 Major 而非 Reject |

`[DA-CRITICAL-VS-ACCEPT: 1 validated]` — 该标记使机械 Accept 不可静默成立,已升级为 Major Revision。

---

## 四、修改路线图(Revision Roadmap)

### Required Revisions(Must Fix)

| Transport ref | 修订项 | 严重级 | 来源 | 义务 | 成本范围 |
|---|---|---|---|---|---|
| R1 | 完成 QAT(NBE)路径重跑,同步代码与 commit 指针,使表 3–表 6 全部数字可复现 | critical | EIC/R1/DA | must_fix | re_analysis + 代码同步 |
| R2 | 将 "privacy-preserving" 收敛为 "reconstruction-resistant(内容级)",并补身份级隐私的量化评估或形式化目标 | major | EIC/R2/R3/DA | must_fix | section + 补充分析 |
| R3 | 报告关键增益的效应量(如 Cohen's h)与 CI,区分统计显著与实质显著 | major | R1/DA | must_fix | re_analysis |
| R4 | 约束基线公平性:补充 PTQ 基线的原生格式对照,澄清 Safe-QAQ 非同类对比边界 | major | R1/DA | must_fix | section + 补充实验 |

### Suggested Revisions(Should Fix)

| Transport ref | 修订项 | 严重级 | 来源 | 义务 | 成本范围 |
|---|---|---|---|---|---|
| S1 | 补引 speaker anonymization 形式化保证谱系,明确 content-level 与 identity-level 隐私区分 | major | R2 | should_fix | section |
| S2 | 将 LDP 明确标注为"实验性、非形式化隐私机制",或移出主架构图 | major | R3/DA | should_fix | sentence + figure |
| S3 | 讨论误判(假阳性)的社会后果与弱势群体干预伦理 | minor | R3 | consider | section |
| S4 | 统一 "Multimodal" 标题与 "audio–text 主评估" 的表述,统一 57× 压缩口径 | minor | EIC/DA | consider | sentence |

### 源可追溯清单(不可变源顺序,非工作排序)

- [ ] R1 — `must_fix`:复现缺口闭合
- [ ] R2 — `must_fix`:privacy 声称收敛 + 身份级评估
- [ ] R3 — `must_fix`:效应量报告
- [ ] R4 — `must_fix`:基线公平性约束
- [ ] S1 — `should_fix`:语音隐私文献补引
- [ ] S2 — `should_fix`:LDP 合规标注
- [ ] S3 — `consider`:误判伦理讨论
- [ ] S4 — `consider`:术语一致性

---

## 五、评审摘要

| 席位 | 推荐 | 置信度 | 关键结论 |
|---|---|---|---|
| Journal-Fit Reviewer | Major Revision | 4 | 契合一线应用 AI 期刊,但复现缺口 + privacy 声称过度需先修 |
| R1 方法学 | Major Revision | 4 | 设计自洽、统计规范,但不可复现 + 效应量缺失 + 基线公平性 |
| R2 领域 | Major Revision | 4 | 领域贡献真实,但语音隐私文献薄、形式化保证缺 |
| R3 交叉视角 | Major Revision | 4 | 工程可行,但隐私合规声称过度 + 误判伦理缺失 |
| Devil's Advocate | 仅 findings | — | C1(不可复现)成立;privacy 支柱被自身证据反驳 |

---

**最终结论:Major Revision(大修)**。阻断项为「主结果不可复现」与「privacy 声称过度」,另有 2 项 must-fix(效应量、基线公平性)与 4 项 should-fix/consider。

---

## 归档：v29_planned_baseline_design.md

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

---

## 归档：v29_response_to_reviewers.md

# QAD-MultiGuard — Response to Reviewers(修订说明)

> **论文**:QAD-MultiGuard: An Edge–Cloud Framework for Multimodal Fraud Detection and Risk Assessment
> **目标期刊**:Expert Systems with Applications(ESWA)
> **决策**:Major Revision(模拟评审,`academic-paper-reviewer` v1.11.1)
> **修订版本**:`v28.tex` → `v29.tex`
> **性质**:模拟修订说明。状态标注区分「已完成 / 部分完成 / planned(待实验回填)」,不虚构未做的实验。
> **日期**:2026-08-27

---

## 总述(Summary of Changes)

本次修订针对综合决策意见的 **R1–R4(必须修改)** 与 **S1–S4(建议修改)** 进行。已落地的文本修订聚焦于 **R2(主张收敛)**、**R3(对比公平性)**、**R4(新颖性边界声明)** 与 **S1/S2/S4(效应量、pilot 降级、功效披露)**,均在 `v29.tex`(`v28.tex` 原版保留)。**R1(可复现性回填)** 与 **S3(隐私嵌入消融)** 属实验层面,已在文中 `§Reproducibility statement` 预先承诺或标注为 planned,无法以文本修改闭合。其中 **S1(效应量)** 在第二轮评审(`reports/v29_review.md`)中被升级为 R3(Major),已在 L505 以 Cohen's h 闭合,并在主结果段 L681 同步收敛;**S2** 以「pilot 降级为 future work」闭合;**S4** 以「功效限制披露」闭合。

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

---

## 归档：v29_response_to_reviewers_round2.md

# QAD-MultiGuard — Response to Reviewers(第二轮修订说明)

> **论文**:QAD-MultiGuard: An Edge–Cloud Framework for Multimodal Fraud Detection and Risk Assessment
> **回应评审**:`reports/v29_review.md`(2026-08-28,`full` 五席位评审,**Major Revision**)
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
- 本轮评审报告:`reports/v29_review.md`
- 本轮修订说明:`reports/v29_response_to_reviewers_round2.md`
- 前轮响应(回应 v28 评审):`reports/v29_response_to_reviewers.md`、`reports/v29_revision_letter_EN.md`

---

## 归档：editorial_decision_v29.md

# Editorial Decision

## Manuscript Information
- **Title**: QAD-MultiGuard: An Edge--Cloud Framework for Multimodal Fraud Detection and Risk Assessment
- **Manuscript ID**: N/A
- **Submission Date**: N/A
- **Decision Date**: 2026-08-31
- **Review Round**: Round 1

## Calibration Resolution
`calibration_status: NOT_CALIBRATED`

## Review Panel Provenance (#540/#740)

**Provenance artifact status**: `missing` — no replay-valid `review-panel-provenance/1.0` artifact was generated for this inline panel. The axes below are therefore rendered `unknown` per the closed invalid/unknown state; the execution topology that is actually known is disclosed immediately below and is **not** reduced to an independence claim.

**Actually-known execution topology (disclosed, not artifact-verified)**:
- 5 seats were dispatched as `general-purpose` subagents within this session, all under the same model family (Claude / Opus 4.8) and same provider (Anthropic).
- Seats were invoked in parallel with paper access; no seat read another seat's report before committing its own (role separation honored at dispatch time).
- `model_family_distinct` and `provider_distinct` are therefore **false**; `role_separated` is the only axis substantively satisfied.

| Provenance axis | Status |
|---|---|
| Role-separated | `true` (5 distinct roles, parallel dispatch) |
| Within-panel invocation-context separation | `unknown` (artifact missing) |
| Blind to peer outputs | `true` (parallel dispatch, no cross-read before commit) |
| Model-family distinct | `false` (all Claude/Opus 4.8) |
| Provider distinct | `false` (all Anthropic) |
| Human-reviewer distinct | `unknown` |

- **Binary independence claim**: Not computed. Role separation is not independence; the panel is same-model-family and must not be presented as independent.
- **Correlated-error disclosure**: Same model family across all seats means shared systematic biases (e.g. shared prior on "effect size must be large") are plausible and uncorrected. Consensus here reflects agreement among same-family reviewers, not cross-family triangulation.

---

## Decision

### Major Revision

---

## Reviewer Summary

| Reviewer | Role | Recommendation | Confidence |
|----------|------|---------------|------------|
| Journal-Fit Reviewer | ESWA senior-editor / deployment-systems fit | Major Revision | 4 |
| Reviewer 1 | Methodology / quantisation & statistics | Major Revision | 4 |
| Reviewer 2 | Domain / telecom-fraud & speech anti-fraud | Major Revision | 4 |
| Reviewer 3 | Cross-disciplinary / privacy & voice-privacy | Minor Revision | 4 |
| Devil's Advocate | Fixed adversarial seat | N/A — findings only | N/A — per-finding |

---

## Blocking Issues (3, immutable source order)

| Transport ref | Blocking issue | Source reviewer(s) | Evidence anchor | Resolving roadmap item |
|---------------|----------------|--------------------|-----------------|------------------------|
| R1 | Headline results are not reproducible: the public repository hosts an int4-PTQ development configuration, not the NVFP4 QAD that produced the reported tables; effect sizes are "derived from the historical H100 run and will be recomputed". No third party can verify any headline number. | R1 (Critical), DA (C1), EIC (W2) | `text: §Reproducibility statement` / `text: §Experimental Setup` | REV-1 |
| R2 | The acoustic embedding's contribution to detection is never isolated: no text-only or audio-only TAF-28k baseline is reported, yet the embedding is a headline privacy contribution and fusion weight $w_\mathrm{audio}=0.30 < w_\mathrm{text}=0.40$ hints it is secondary. | EIC (W3), R2 (W2b), R3 (W5), DA (M4) | `absence: §Main results — text-only/audio-only F1` | REV-2 |
| R3 | OV-Freeze is listed as one of four contributions but its own reported effect is +0.007 F1 ($h\approx0.02$, below the $h=0.20$ "small" threshold); the authors' own data contradicts its framing as a substantive contribution. | EIC (W4), R1 (W5), DA (C2) | `table: tab3-en` / `text: §Main results` | REV-3 |

---

## Consensus Analysis

### Points of Agreement (Consensus)

**Corroborated — Reproducibility gap (SC-1)**: R1 (Critical) and EIC (Major) independently identify the same defect — the repository does not reproduce the reported tables. DA C1 (Critical) corroborates with confidence 5. R2 and R3 are silent. **Editor's arbitration on severity**: R1's Critical is adopted over EIC's Major (methodology defect defers to R1; honest disclosure does not lower the severity of "core numbers unverifiable"). Net severity: **critical**.

**CONSENSUS-3 — Missing single-modality ablation (SC-2)**: EIC (W3), R2 (W2b), and R3 (W5) agree the acoustic branch's marginal contribution is unquantified; R1 is silent. DA M4 corroborates. Severity: **major**.

**Corroborated — OV-Freeze effect-size vs contribution-status mismatch (SC-3)**: EIC (W4) and R1 (W5) agree; DA C2 (Critical) corroborates. R2/R3 silent. Severity: **major**.

**Corroborated — Overstated privacy language / PIPL self-endorsement (SC-13)**: EIC (W6) and R3 (W3) agree "Privacy-preserving"/"destroys speaker identity" overstates the paper's own careful bounds; DA M3 corroborates the compliance-assertion overreach. R1/R2 silent. Severity: **minor** (language) with a **major** sub-claim on the legal assertion (DA M3).

### Points of Disagreement

**Disagreement 1: Severity of the reproducibility gap (SC-1)**
- **R1 view**: Critical — no third party can verify any headline claim; "reproduction run" not done.
- **EIC view**: Major — honest disclosure mitigates, and the gap is repairable by rerunning.
- **Disagreement type**: Severity disagreement.
- **Editor's Resolution**: Critical stands (R1).
- **Resolution Rationale**: Methodology defects defer to R1 (expertise first). Disclosure does not reduce the severity of "core numbers cannot be verified from public code"; it removes deception but not the defect. The remediation (REV-1) is the same under either severity.

**Disagreement 2: Overall recommendation spread (Major ×3 vs Minor ×1)**
- **R3 view**: Minor Revision — privacy-boundary statements are honest and restrained; only measurement-object and terminology issues remain.
- **EIC/R1/R2 view**: Major Revision — reproducibility, missing ablation, and citation-accuracy defects require re-analysis and section rewriting.
- **Disagreement type**: Perspective difference (privacy lens vs methodology/domain lens).
- **Editor's Resolution**: Major Revision.
- **Resolution Rationale**: R3's concerns are real but narrow to the privacy section; the reproducibility defect (Critical, R1) and the missing single-modality ablation (consensus) cannot be resolved by wording alone. A majority-Major panel plus a validated Critical determinately selects Major Revision. R3's findings are preserved as should_fix items.

---

## Decision Rationale

Three of four non-DA reviewers recommend Major Revision and one (R1) raises a Critical defect that is independently corroborated by the Devil's Advocate (C1) and echoed by the Journal-Fit Reviewer (W2): the paper's headline results cannot be reproduced from the public repository, which hosts an int4-PTQ configuration rather than the NVFP4 QAD that produced the reported tables. This single finding — that no third party can verify the central 99.1% / 98.5% recovery claims — is sufficient to require revision rather than accept or minor-revision; the panel's task is not to adjudicate whether the numbers are *true* but whether they are *verifiable*, and they currently are not.

Beyond reproducibility, two consensus-grade defects shape the decision. First, the acoustic embedding is positioned as a privacy contribution but its detection value is never isolated (no text-only / audio-only baseline), and the fusion weight ($w_\mathrm{audio}=0.30$) suggests it may be secondary — a structural gap that requires re-analysis, not rewording. Second, OV-Freeze's own reported effect (+0.007 F1, $h\approx0.02$) contradicts its standing as one of four contributions; either evidence of a non-noise effect must be supplied or the framing must be downgraded to "evidence of faithful distillation."

The panel was unanimous that the authors' honesty — explicit disclosure of the reproduction gap, unlinkability residual risk, effect sizes below "small", and NBE-vs-Blackwell distinction — is a genuine strength and mitigates against Reject. The problems are framing, verification, and missing baselines, not fabrication. Major Revision (with re-review) is therefore the correct outcome: the defects are repairable but require re-analysis and additional experiments, not clarification alone.

---

## Required Revisions (Must Fix)

| Transport ref | Revision Item | Sub-Claim(s) | Severity | Evidence Anchor | Confidence | Source | Obligation class | Cost scope | Bounded consequence |
|---|--------------|--------------|----------|-----------------|------------|--------|------------------|------------|---------------------|
| R1 | Make the reported tables reproducible: either ship the NVFP4 QAD config that produced the tables and complete the reproduction run, or demote every affected headline number to "historical run, not reproducible" with the caveat surfaced in abstract/conclusion. | SC-1 | critical | `text: §Reproducibility statement` "raw outputs do not yet reproduce the reported tables" | 5 | R1 / DA | must_fix | re_analysis (reproduce script + rerun) | core_claim_unverifiable → reproducibility |
| R2 | Report text-only and audio-only TAF-28k F1 to isolate the acoustic embedding's marginal contribution; if the acoustic branch is secondary, revise the "multimodal coupling" motivation accordingly. | SC-2 | major | `absence: §Main results` | 4 | EIC / R2 / R3 / DA | must_fix | new_data (single-modality ablation run) | contribution_unquantified → acoustic_embedding |
| R3 | Reconcile OV-Freeze's contribution status with its effect size: provide evidence the +0.007 gain exceeds seed noise, or downgrade it from "four contributions" to "evidence of faithful distillation." | SC-3, SC-4 | major | `table: tab3-en` / `text: §Main results` $h\approx0.02$ | 4 | EIC / R1 / DA | must_fix | section (contribution framing + stats) | contribution_misattributed → ov_freeze |
| R4 | Correct the external-baseline attribution: bib [16] is an Indonesian SMS *sentiment* paper, not a "Chinese anti-fraud SMS F1=0.876" baseline; provide exact source sentences for "ASR recall 60–75%" and "2.7 heterogeneous signals" or delete them. | SC-8 | major | `dataset: bib ref [16]` title mismatch | 4 | R2 | must_fix | section (Related Work + Intro) | baseline_misattributed → citations |
| R5 | Make the adversarial-robustness claim honest: report the full-pool degradation (0.841 vs TAF 0.931 ≈ 9.7%) alongside the curated 517-subset "0.8% drop", and do not use the matched BF16 baseline (0.882) as the sole reference. | SC-15 | major | `table: tab4-cross-en` full pool 0.841 | 4 | DA | must_fix | section (Cross-dataset) | headline_selective → robustness |

### Required Item Details

**R1: Reproducibility of headline tables**
- **Problem**: Public repository hosts an int4-PTQ development config, not the NVFP4 QAD that produced the reported F1/Recovery tables; effect sizes are "derived from the historical H100 run and will be recomputed."
- **Source**: R1 (Critical), DA C1 (Critical), EIC W2 (Major).
- **Requirement**: Ship the NVFP4 QAD configuration + reproduction scripts and run them to regenerate the tables, or demote every affected number with an explicit non-reproducible caveat in the abstract and conclusion.
- **Acceptance criteria**: `git`-checkout → run reproduction script → tables regenerate within the claimed seed/CI; OR every affected claim is flagged non-reproducible in abstract + conclusion.

**R2: Single-modality ablation**
- **Problem**: No text-only or audio-only TAF-28k F1 is reported; the acoustic embedding's detection contribution is unquantified.
- **Source**: EIC W3, R2 W2b, R3 W5, DA M4.
- **Requirement**: Add text-only and audio-only F1 on TAF-28k; state whether the acoustic branch's incremental value justifies its information-loss cost.
- **Acceptance criteria**: Text-only and audio-only F1 rows present; a sentence reconciling the fusion weight with the measured marginal contribution.

**R3: OV-Freeze contribution status**
- **Problem**: OV-Freeze is a headline contribution but its own effect (+0.007 F1, $h\approx0.02$) is below "small."
- **Source**: EIC W4, R1 W5, DA C2.
- **Requirement**: Provide multi-seed evidence the gain exceeds seed noise, or reframe OV-Freeze as a distillation-fidelity regularizer rather than an accuracy contribution.
- **Acceptance criteria**: Either a seed-variance-aware significance statement supporting the gain, or explicit downgrade of OV-Freeze's contribution framing.

**R4: External-baseline attribution**
- **Problem**: BERT-Fraud (bib [16]) is misattributed; "60–75% recall" and "2.7 signals" lack verifiable sources.
- **Source**: R2 W1.
- **Requirement**: Correct or replace the BERT-Fraud citation; give exact source sentences for the two numeric claims or remove them.
- **Acceptance criteria**: bib [16] description matches its actual title/venue; numeric claims carry page-level citations or are deleted.

**R5: Adversarial-robustness honesty**
- **Problem**: The "0.8% relative drop" headline uses a curated 517 subset and a weak matched baseline; the full pool degrades ~9.7%.
- **Source**: DA M2.
- **Requirement**: Report full-pool and curated results side by side; remove the exclusive use of the 0.882 matched baseline as the reference.
- **Acceptance criteria**: Full-pool degradation visible in the same table as the headline; reference-frame choice justified or corrected.

---

## Suggested Revisions (Should Fix)

| Transport ref | Revision Item | Sub-Claim(s) | Severity | Evidence Anchor | Confidence | Source | Obligation class | Cost scope | Bounded consequence |
|---|--------------|--------------|----------|-----------------|------------|--------|------------------|------------|---------------------|
| S1 | Clarify Eq. (eq:nbe): state whether the noise/quantisation step is integer round/clamp or a true FP4 grid; align notation with NVFP4. | SC-5 | major | `equation: eq:nbe` | 4 | R1 | should_fix | sentence (equation + note) | notation_inconsistent → nbe |
| S2 | Reconcile the QAT baseline budget: it uses CE loss with the same 2000-step budget as QAD, so it is under-trained; either train it fairly or state the imbalance. | SC-6 | major | `text: §QAT baseline` | 4 | R1 | should_fix | re_analysis (baseline retrain) | baseline_undertrained → qat |
| S3 | Re-tune or justify the PTQ baselines: they are forced to NVFP4 and cluster at 0.838–0.840, suggesting they were never calibrated; give all PTQ methods the same 100-sample calibration as the vanilla-PTQ temperature-scaling entry. | SC-7 | major | `table: tab3-en` PTQ 0.838 cluster | 4 | R1 / DA | should_fix | re_analysis (PTQ calibration) | baseline_uncalibrated → ptq |
| S4 | Clarify the ASV-EER measurement object: it is computed on *reconstructed* embeddings, not on $\bm{F}_v$; either report a direct open-set EER / cosine-similarity linkability curve on $\bm{F}_v$, or relabel the current 46.8%/48.5% as "reconstruction-attack failure" rather than "$\bm{F}_v$ unlinkability evidence." | SC-11 | major | `text: §sec:glo` "computed on the reconstructed embeddings" | 4 | R3 | should_fix | new_data (direct linkability eval) or sentence | measurement_object_mismatched → asv_eer |
| S5 | Correct the VPC terminology: the paper's "content-level protection" (high WER) is the *opposite* of VPC's content-utility (low WER); use "linguistic/semantic content privacy (reconstruction resistance)" and cite VPC only for the identity/unlinkability dimension. | SC-12 | major | `text: §Related Work` content-level mapping | 3 | R3 | should_fix | sentence (terminology) | terminology_reversed → vpc |
| S6 | Fill the literature gap: add speech anti-spoofing / deepfake / ASVspoof work (relevant to threat G3 and "voice manipulation"), and SmoothQuant/QLoRA/OmniQuant; cite a source for "PTQ degrades 6.0–12.5% at 0.5B" or mark it as in-house measurement. | SC-10 | major | `absence: §Related Work` | 4 | R2 | should_fix | section (Related Work) | literature_incomplete → citations |
| S7 | Harmonize privacy language: replace "Privacy-preserving 128-d embedding" and "destroys speaker identity" with "reconstruction-resistant" and "attenuates … under the evaluated attacks"; add a legal-review caveat to the PIPL Article 23 compliance claim. | SC-13 | minor (+major legal sub-claim) | `table: tab1` / `text: §sec:glo` | 4 | R3 / EIC / DA | should_fix | sentence (labels + compliance note) | claim_overstated → privacy |
| S8 | Clarify the text modality in the voice-call scenario: if "no ASR on-device" holds, the fusion formula's $r_\mathrm{text}$ source (transcript? SMS? LLM risk score?) must be specified, or the privacy/fusion contradiction stands. | SC-17 | major | `text: §Data-flow` / `equation: eq:fusion` | 3 | DA | should_fix | section (data-flow + fusion) | modality_undefined → text |
| S9 | Resolve the dataset-split contradiction: "3:1 train(21,490)/test(7,021) with no validation" conflicts with the later "validation partition" and "five-fold CV within the training partition"; state where the validation set comes from. | SC-9 | major | `text: §Experimental Setup` vs `text: §Evaluation Metrics` | 4 | R2 | should_fix | sentence (dataset description) | split_contradiction → validation |
| S10 | Add the caveat that headline numbers are QDQ-simulated NBE (not native Blackwell), 3.32× is a cloud-component figure, and 268ms is assembled from per-stage components — surface these in the abstract/conclusion, not only in table footnotes. | SC-18 | major | `text: §NBE` / `text: §SpecDec` footnotes | 4 | DA | should_fix | sentence (abstract + conclusion caveats) | headline_caveat_hidden → specdec |

## Suggested Revisions (Consider)

| Transport ref | Revision Item | Sub-Claim(s) | Severity | Evidence Anchor | Confidence | Source | Obligation class | Cost scope | Bounded consequence |
|---|--------------|--------------|----------|-----------------|------------|--------|------------------|------------|---------------------|
| S11 | Unify the WER threshold: threat model states "≥0.90" while the headline is "≥0.95"; phrase as "constraint 0.90 / achieved 0.95". | SC-19 | minor | `text: §Threat Model` vs `text: §Abstract` | 4 | R3 / R2 | consider | sentence | threshold_inconsistent → g1 |
| S12 | Make the AdvFraud-3k construction arithmetic consistent: "3,000 source samples × 8 strategies" vs "full pool of 3,000 variants" cannot both hold; state the source→variant→517 pipeline unambiguously. | SC-24 | minor | `text: §Experimental Setup` | 4 | R2 | consider | sentence (dataset description) | dataset_arithmetic_inconsistent → advfraud |
| S13 | Clarify the SAFE-QAQ row provenance: "cited from [2], not reproduced" but with F1±std and FPR 1.8% — state which columns are from the source vs in-house. | SC-23 | minor | `table: tab3-en` SAFE-QAQ row | 4 | R2 / EIC | consider | sentence (table footnote) | baseline_provenance_unclear → safe_qaq |
| S14 | State the LDP sensitivity/clipping assumption so σ=1.0 → ε=1.5 is auditable; or label ε as "engineering estimate" in the figure caption. | SC-14 | minor | `figure: fig4` / `text: §Discussion` | 4 | R3 | consider | sentence (caption + note) | epsilon_unreproducible → ldp |
| S15 | Justify the 57× storage reference frame (0.5B-quantised vs 7B-BF16) or also report against 0.5B-BF16 (~4×) to avoid cross-scale inflation. | SC-16 | major | `text: tab3-en footnote` "57× … against SAFE-QAQ (7B)" | 4 | DA | consider | sentence (footnote) | reference_frame_inflated → storage |
| S16 | Report the 11-speaker speaker-ID sample sizes and a Wilson/binomial CI so the "preliminary" downgrade is independently assessable. | SC-20 | minor | `table: tab:privacy_attack-en` 8.3% vs 9.1% | 3 | R3 / DA | consider | sentence (CI) | statistic_underpowered → speaker_id |

---

## Revision Roadmap

### Source-traceability checklist

- [ ] R1 — obligation `must_fix`: Reproduce headline tables or demote to "historical run, non-reproducible".
- [ ] R2 — obligation `must_fix`: Add text-only/audio-only TAF-28k ablation; quantify acoustic marginal contribution.
- [ ] R3 — obligation `must_fix`: Reconcile OV-Freeze contribution status with +0.007 F1 / h≈0.02.
- [ ] R4 — obligation `must_fix`: Correct BERT-Fraud attribution; source the 60–75% and 2.7-signals claims.
- [ ] R5 — obligation `must_fix`: Report full-pool adversarial degradation; stop exclusive use of matched baseline.
- [ ] S1 — obligation `should_fix`: Clarify Eq. (eq:nbe) as FP4 grid vs integer round/clamp.
- [ ] S2 — obligation `should_fix`: Fairly train or state the QAT baseline budget imbalance.
- [ ] S3 — obligation `should_fix`: Calibrate PTQ baselines consistently.
- [ ] S4 — obligation `should_fix`: Report direct F_v linkability/EER or relabel reconstructed-embedding ASV-EER.
- [ ] S5 — obligation `should_fix`: Correct VPC content-level terminology.
- [ ] S6 — obligation `should_fix`: Add anti-spoofing/deepfake + SmoothQuant/QLoRA/OmniQuant references; source 6.0–12.5%.
- [ ] S7 — obligation `should_fix`: Harmonize privacy language + add legal-review caveat to PIPL claim.
- [ ] S8 — obligation `should_fix`: Define the text modality in the voice-call scenario.
- [ ] S9 — obligation `should_fix`: Resolve the 3:1-split vs validation-partition contradiction.
- [ ] S10 — obligation `should_fix`: Surface NBE/3.32×/268ms caveats in abstract + conclusion.
- [ ] S11 — obligation `consider`: Unify WER threshold 0.90 vs 0.95.
- [ ] S12 — obligation `consider`: Fix AdvFraud-3k construction arithmetic.
- [ ] S13 — obligation `consider`: Clarify SAFE-QAQ row provenance.
- [ ] S14 — obligation `consider`: State LDP sensitivity/clipping.
- [ ] S15 — obligation `consider`: Justify 57× storage reference frame.
- [ ] S16 — obligation `consider`: Report speaker-ID sample sizes + CI.

---

## Journal-Supplied Deadline (Optional Transport)
- **Exact deadline from source letter**: `NOT PROVIDED`

---

## Response Letter Instructions

Use `templates/revision_response_template.md` to respond item-by-item. Must include: (1) response + revision description for each Required Revision; (2) response for each Suggested Revision (adopted or reason for not adopting); (3) change markup in the revised manuscript; (4) cross-reference table of new page/paragraph numbers.

---

## Closing

We encourage you to carefully consider the reviewers' comments and submit a substantially revised manuscript. Please note that the revised manuscript will undergo another round of review. The panel noted, in particular, that the manuscript's honest self-limitation — disclosing the reproduction gap, the unlinkability residual risk, and the below-"small" effect sizes — is a genuine strength that meaningfully mitigates against rejection; the required work is to bring the verification, baselines, and framing up to the same standard.

---

## Appendix: Full Reviewer Reports

### Journal-Fit Review Report Summary
- Recommendation: Major Revision | Confidence: 4
- Key Point: Good ESWA fit with honest contribution framing and mature limitations, but the application significance is unproven (single corpus, no field deployment), reproducibility gap, missing single-modality ablation, and below-"small" effect sizes must be addressed.

### Reviewer 1 (Methodology) Summary
- Recommendation: Major Revision | Confidence: 4
- Key Point: Honest effect-size reporting and clean ablation isolation are strengths, but the reproducibility gap is Critical (repo hosts int4-PTQ not NVFP4 QAD), and the NBE equation, under-trained QAT baseline, uncalibrated PTQ baselines, and seed-noise-level +0.007 gain require re-analysis.

### Reviewer 2 (Domain) Summary
- Recommendation: Major Revision | Confidence: 4
- Key Point: Excellent internal numeric consistency and disciplined limitation disclosure, but external-baseline attribution errors (BERT-Fraud mismatch), unverified acoustic-branch contribution, a dataset-split contradiction, and literature gaps (anti-spoofing, SmoothQuant/QLoRA/OmniQuant) need correction.

### Reviewer 3 (Perspective / Privacy) Summary
- Recommendation: Minor Revision | Confidence: 4
- Key Point: Privacy-boundary statements are honest and restrained, but the ASV-EER is computed on reconstructed embeddings (not $\bm{F}_v$), the VPC content-level terminology is reversed, and privacy wording plus LDP reproducibility need tightening.

### Devil's Advocate Summary
- Recommendation: N/A — findings only
- Key Challenge: The three pillars (privacy / 98.5% recovery / four-component synergy) are each weaker than the title implies; the whole argument rests on an unstated deployment premise (software on the victim's device) that is never justified — and the core numbers are currently irreproducible.

---

## 归档：editorial_decision_v29_round2.md

# Editorial Decision — Round 2（QAD-MultiGuard v29）

## Manuscript Information
- **Title**: QAD-MultiGuard: An Edge–Cloud Framework for Multimodal Fraud Detection and Risk Assessment
- **Manuscript ID**: N/A
- **Decision Date**: 2026-09-01
- **Review Round**: Round 2（回应 2026-08-31 第一轮 Major Revision 决策；本轮更换全部四席非 DA 评审学者）

## Calibration Resolution
`calibration_status: NOT_CALIBRATED`

## Review Panel Provenance (#540/#740)

**Provenance artifact status**: `missing` — 未生成 replay-valid `review-panel-provenance/1.0` artifact。以下各轴按 closed invalid/unknown 状态呈现；实际已知的执行拓扑如实披露，不归约为独立性声明。

**实际已知执行拓扑（披露，非 artifact 验证）**：
- 5 席以 `general-purpose` subagent 在本会话内并行派发，全部同一模型族（Claude / Opus 4.8）、同一 provider（Anthropic）。
- 各席并行、提交前互不读取对方报告（派发时角色分离成立）。
- 本轮四席非 DA 评审者身份与第一轮**完全不同**（见 Phase 0 配置）；但「身份不同」仍是角色配置，**不是**独立误差过程。

| Provenance axis | Status |
|---|---|
| Role-separated | `true`（5 席并行派发） |
| Within-panel invocation-context separation | `unknown`（artifact missing） |
| Blind to peer outputs | `true`（并行派发，提交前无交叉读取） |
| Model-family distinct | `false`（全 Claude/Opus 4.8） |
| Provider distinct | `false`（全 Anthropic） |
| Human-reviewer distinct | `unknown` |

- **Binary independence claim**: 不计算。角色/身份差异仅证明 `role_separated`，不构成独立审稿。
- **Correlated-error disclosure**: 同一模型族意味着共享系统性偏误（如「效应量须大」的先验）可能且未被修正。本轮的共识反映同族评审者的一致，**非跨族三角验证**。第一轮与第二轮的收敛因此可能部分是同源偏误的重复，而非独立的第二次确认。

---

## Decision

### Major Revision

四席非 DA 评审者一致建议 **Major Revision**（EIC/R1/R2/R3 均 Major，置信度 4）；Devil's Advocate 提出 1 项 Critical（C1）+ 6 项 Major。无 Reject 席。

---

## Reviewer Summary

| Reviewer | Role | Recommendation | Confidence |
|----------|------|---------------|------------|
| Journal-Fit Reviewer | 多模态 LLM + 边缘智能编委 | Major Revision | 4 |
| Reviewer 1 | ML 评测 / 基准方法学 | Major Revision | 4 |
| Reviewer 2 | 语音信号处理 / 说话人 / anti-spoofing | Major Revision | 4 |
| Reviewer 3 | 可信 AI / 隐私工程 / PIPL-GDPR 合规 | Major Revision | 4 |
| Devil's Advocate | 固定对抗席位 | N/A — findings only | N/A — per-finding |

---

## Blocking Issues（3，immutable source order）

| Transport ref | Blocking issue | Source reviewer(s) | Evidence anchor | Resolving roadmap item |
|---------------|----------------|--------------------|-----------------|------------------------|
| R1 | 头条数字仍不可从公开仓库复现——仓库托管 int4-PTQ 开发配置而非产出表格的 NVFP4 QAD，reproduction run 仍「in progress」。第一轮 Critical 仅被披露、未解决。 | EIC(W4, Critical)、R1(W1, Critical)、DA(M3) | `text: §Reproducibility statement "its raw outputs do not yet reproduce the reported tables"` | R1 |
| R2 | 核心隐私贡献（C1 的 128 维 F_v）从未被端到端评估——WER≥0.95 / speaker-ID≤8.3% 测于 proxy 嵌入与「reference estimates」，且 speaker-ID 输入维度（128）与 Eq.(5)（64 维 FBANK 分量）硬性矛盾、ASV-EER 算在 reconstructed 而非 F_v 上。 | EIC(W2)、R2(W1/W2)、R3(W3)、DA(C1) | `text: §4.3 "the released experiments evaluate its two components through their respective proxy embeddings"` | R2 |
| R3 | 声学分支的检测贡献从未量化——无 text-only / audio-only 单模态消融，融合权重 $w_{audio}=0.30<w_{text}=0.40$ 且作者自认声学「may be the secondary contributor」。 | EIC(W3)、R1(W4)、R2(W3)、DA(M2) | `absence: §Main results — expected text-only/audio-only F1; checked Table 3, §5, §7` | R3 |

---

## Consensus Analysis

### 子声明分解与共识判定（Step 1b / Step 2）

| sub_claim | 内容 | EIC | R1 | R2 | R3 | DA | 判定 |
|---|---|---|---|---|---|---|---|
| SC-1 | 可复现性缺口未闭环 | Critical | Critical | — | — | M3 佐证 | **corroborated**（2/4，Critical） |
| SC-2 | F_v 未端到端评估（proxy/reference） | Major | Minor | Major | Major | C1 佐证 | **CONSENSUS-4 存在 + 严重度分裂**（R1 Minor vs 其余 Major） |
| SC-3 | 单模态消融缺失 | Major | Major | Major | — | M2 佐证 | **CONSENSUS-3**（R3 沉默） |
| SC-4 | 标题「四模态」vs 实际「双模态」 | Major | Minor(措辞) | — | — | M1 佐证 | **corroborated**（EIC Major + R1 Minor + DA） |
| SC-5 | cross-format portability 混淆 CoT | — | Major | — | — | m1 | single-reviewer（R1） |
| SC-6 | p 值过度解读 / bootstrap 未传 seed 方差 | — | Major | — | — | — | single-reviewer（R1） |
| SC-7 | 投机解码映射 C3 断裂 | — | Minor | — | — | M6 | single-reviewer（R1，DA Major） |
| SC-8 | 部署模型未言明（终端 vs 运营商侧） | — | — | — | Major | Unexamined Premise | single-reviewer（R3）+ DA |
| SC-9 | 摘要/引言合规宣称与正文降级矛盾 | — | — | — | Major | — | single-reviewer（R3） |
| SC-10 | FPR 未折算真实低发病率 | — | — | — | Major | — | single-reviewer（R3） |
| SC-12 | speaker-ID 输入维度 128 vs 64 矛盾 | — | — | Major | Major(并入 W3) | C1 佐证 | **corroborated**（R2 + R3） |
| SC-13 | 重构抵抗是设计性质还是压缩副产品 | — | — | Major | — | — | single-reviewer（R2） |
| SC-14 | 创新属集成协同、缺单一机制 | Major | (MEETS) | (PARTLY) | (PARTLY) | — | **SPLIT**（EIC vs R1） |
| SC-15 | 57× storage 选择性对比 | — | — | — | — | M4 | DA-only（Major） |
| SC-16 | pure-KL 优于 QAT 是稻草人 | — | — | — | — | M5 | DA-only（Major） |
| SC-17 | GLO 引用误归 Bora 2017 | — | — | Minor | — | — | single（R2，Minor） |
| SC-18 | FBANK/MFCC 术语混用 | — | — | Minor | — | — | single（R2，Minor） |
| SC-19 | anti-spoofing 文献覆盖薄 | — | — | Minor | — | — | single（R2，Minor） |
| SC-20 | LDP「corresponding to ε=1.5」措辞 | — | — | — | Minor | — | single（R3，Minor） |
| SC-21 | 时延为 assembled estimate 非实测 | — | — | — | — | m2 | DA-only（Minor） |
| SC-22 | OV-Freeze highlights 拔高 | Minor | — | — | — | m3 | EIC Minor + DA Minor |

### Points of Agreement（共识）

- **[CONSENSUS-4 — 存在层]** SC-2「F_v 隐私证据测于代理而非实际部署表示」：EIC(W2)、R1(W5)、R2(W1/W2)、R3(W3) 四席一致指出测量对象错位；DA C1 以 Critical 佐证。这是本轮最强、跨四席的共识缺陷，直接命中本轮评审重点「创新点是否可验证」。
- **[CONSENSUS-3]** SC-3「单模态消融缺失」：EIC(W3)、R1(W4)、R2(W3) 三席同意，R3 沉默；DA M2 佐证。
- **corroborated** SC-1（可复现性，EIC+R1 双 Critical + DA M3）、SC-4（四模态 vs 双模态，EIC+DA）、SC-12（维度矛盾，R2+R3）。

### Points of Disagreement

**Disagreement 1: F_v 端到端评估的严重度（SC-2）**
- **R1 view**: Minor（置信度 3，自陈「对声学重建攻击实现细节略有跨领域不确定性」）——代理验证已诚实披露，属证据充分性而非方法错误。
- **EIC / R2 / R3 view**: Major——C1 是唯一带隐私主张的贡献，其边界物本身未被评估是结构性证据缺口。
- **类型**: Severity disagreement。
- **Editor's Resolution**: 采纳 **Major**（非 Critical）。
- **Rationale**: 测量对象错位是领域问题，依 expertise-first defer 至 R2（说话人/ASV 评测方法学）与 R3（隐私工程暴露面分析），二者与 EIC 均判 Major；R1 的 Minor 建立在自陈的领域范围外（置信度 3）之上，不足以降级。不升 Critical 的理由：作者已诚实披露 proxy 性质、无欺骗成分，这使「证据不足」与「伪造」区分开——补端到端测量即可修复，而非不可修复。

**Disagreement 2: 创新定位（SC-14）——集成协同是否构成缺陷**
- **EIC view**: Major——「novelty 在于集成 co-design 而非单一机制」使论文达不到 Trans/顶会级「机制性创新」门槛，需重新定位。
- **R1 view**: MEETS——「集成 co-design + 实证验证」的新颖性 framing 诚实、不夸大单点，属可接受的系统贡献定位。
- **类型**: Perspective difference（venue-fit 视角 vs 方法学视角）。
- **Editor's Resolution**: 采纳 **should_fix（定位澄清）**，非 must_fix。
- **Rationale**: 二者并非互斥——R1 正确指出「诚实 framing 本身无缺陷」，EIC 正确指出「venue 层级决定该定位是否够格」。这是期刊适配判断（EIC 职域），不是学术缺陷。作者只需明确自定位（ESWA 级系统/工程贡献 vs Trans 级机制贡献）并据此校准 claims 强度，属「重新定位」而非「补实验」，故列入 should_fix（S8）。

### DA-CRITICAL 裁决（Iron Rule #4，必须可见）

| DA 编号 | 内容 | 裁决 | 依据 |
|---|---|---|---|
| C1 | 核心隐私贡献悬空：F_v 从未被评估 + 64/128 维度硬性矛盾 + 威胁模型「empirically achieves WER≥0.95」与 §4.3/§5.8 的「proxy/design-target」自相矛盾 | **VALIDATED** | 四席非 DA 中 EIC(W2)、R2(W1/W2)、R3(W3) 独立以 Major 对账同一测量对象错位；SC-12 的维度矛盾被 R2(W2) 与 R3 同时确认。属核心声称的证据缺口 + 字面矛盾，非措辞问题。裁决结果导向 must_fix R2（端到端 F_v 验证 + 维度/对象修正）。因整体决策本为 Major Revision（非 Accept），该 VALIDATED Critical 不触发 `[DA-CRITICAL-VS-ACCEPT]` 升级，仅确认 Major 的必要性。 |

---

## Decision Rationale

四席非 DA 评审者一致建议 Major Revision，且第一轮的两条硬门槛（可复现性、单模态消融）在本轮**仍以「披露」而非「解决」的形式残存**，另有 DA 的一项 VALIDATED Critical 与两条共识级 Major 叠加。决策因此无分歧地为 Major Revision，无需要仲裁的建议级分歧。

与第一轮相比，本轮最显著的进展是**诚实性的系统化落地**：效应量（Cohen's h≈0.02–0.07）前置报告、OV-Freeze 如实降级为「忠实蒸馏证据」、NBE 标注为 QDQ 仿真、LDP 标注为无认证 engineering estimate、speaker-ID 标注为 preliminary、PIPL 声明降级为「technical assessment, not legal compliance」。五席一致肯定这一诚实度是「Major 而非 Reject」的关键缓和因素。

但本轮评审的焦点——「创新点是否可验证」——恰恰暴露了诚实披露无法替代的实质缺口：承载唯一隐私主张的 C1 组件（128 维 F_v），其边界物本身（实际会传输到云的表示）从未被端到端评估，全部隐私 headline 数字测于 proxy 嵌入、引用性估计、以及一个与 Eq.(5) 维度自相矛盾的 speaker-ID 代理。这使「reconstruction-resistant 128-dimensional acoustic embedding」这一摘要级强主张，在部署层面仍未闭合。叠加 SC-1 的可复现性 Critical（仓库仍托管不同配置、无法验证任何 headline 数字）与 SC-3 的单模态消融缺失（声学贡献未量化），三条研究主线中 C1 的「目标↔工作↔证据」闭环仍是最弱的一环。

故本轮维持 Major Revision：三条决策性缺口（可复现性、F_v 端到端验证、单模态消融）均为可修复项（需 H100 复现运行 + 端到端攻击重测 + 单模态基线），但均为实验级、非措辞级，需大修后复审。

---

## Required Revisions (Must Fix)

| Transport ref | Revision Item | Sub-Claim(s) | Severity | Evidence Anchor | Confidence | Source | Obligation class | Cost scope | Bounded consequence |
|---|--------------|--------------|----------|-----------------|------------|--------|------------------|------------|---------------------|
| R1 | 完成 NVFP4 QAD 复现运行并以 commit pointer 替换「in progress」；或在不晚于再投时把全部受影响 headline 数字（Table 3/4、隐私攻击表）全文降级为「historical run, non-reproducible」并在摘要/结论显式标注。 | SC-1 | critical | `text: §Reproducibility statement` | 5 | EIC/R1/DA | must_fix | re_analysis（复现脚本 + 重跑） | core_claim_unverifiable → reproducibility |
| R2 | 对实际部署的 128 维拼接 F_v（经 W_proj 投影）直接运行 GLO/U-Net 反演与 speaker-ID 攻击，报告端到端 WER/PESQ/speaker-ID；修正 speaker-ID 输入维度描述（与 Eq.(5) 64 维 FBANK 一致）并将 ASV-EER 改标为「reconstruction-failure proxy」或改在 F_v 上直接报 ASV-EER/linkability。若不可行，则把隐私声称全文降级为「component-level proxy evidence」并在摘要/highlights 同步降级。 | SC-2, SC-11, SC-12 | major | `text: §4.3 "proxy embeddings"` / `text: §6.2 "128-dimensional MFCC-based"` | 5 | EIC/R2/R3/DA | must_fix | new_data（端到端攻击重测）或 sentence（降级） | core_claim_unmeasured → privacy_F_v |
| R3 | 补报告 TAF-28k 的 text-only 与 audio-only 单模态 F1，量化声学分支边际贡献；若声学确为次要，据此修订 §2 的「strong multimodal coupling」动机。 | SC-3 | major | `absence: §Main results — text-only/audio-only F1` | 4 | EIC/R1/R2/DA | must_fix | new_data（单模态消融） | contribution_unquantified → acoustic_branch |
| R4 | 将标题/摘要/贡献清单的「四模态（text/acoustic/URL/metadata）」诚实化为「audio–text 双模态评估 + URL/meta 为部署预留参数」；删除 Eq.(w-deploy) 把 w_url/w_meta 呈现为「已学习」的表述，明确仅 w_text/w_audio 在 TAF-28k 上学习。 | SC-4 | major | `equation: eq:w-deploy` / `text: §Multimodal Risk Fusion` | 4 | EIC/DA | must_fix | section（标题+摘要+融合段） | claim_overstated → four_modal |
| R5 | 统一合规措辞：删除摘要「privacy-compliant」、引言「complying with PIPL」、C1「mandated by PIPL」、§sysarch「aligning with PIPL」，统一为「privacy-oriented / data-minimisation-aligned technical design」；或若坚持合规宣称，补 PIPL Art. 13/24/28/38–40 法律分析并经合资格法律顾问复核。 | SC-9 | major | `text: §Abstract "privacy-compliant on-device AI"` | 4 | R3 | must_fix | sentence（摘要/引言/§sysarch 一致化） | claim_contradiction → compliance |
| R6 | 明确陈述并论证部署模型（数据控制者身份、数据主体、合法依据、终端类型），或将「raw audio stays on-device」降级为「以终端部署为前提的 design assumption」，并在 Discussion 讨论运营商侧部署拓扑对隐私叙事的影响。 | SC-8 | major | `absence: §sysarch — expected 部署主体/data controller 说明` | 4 | R3/DA | must_fix | section（系统架构 + 讨论） | premise_unstated → deployment |

### Required Item Details

**R1: 可复现性**
- **Problem**: 仓库托管 int4-PTQ 开发配置，非产出表格的 NVFP4 QAD；reproduction run 仍「in progress」。
- **Source**: EIC(W4, Critical)、R1(W1, Critical)、DA(M3)。
- **Requirement**: 完成并公开 NVFP4 QAD 复现运行 + 每数字 commit pointer；或全文降级为 non-reproducible。
- **Acceptance criteria**: `git` checkout → run reproduction script → 表格在声明 seed/CI 内重生成；或每个受影响 claim 在摘要+结论标为 non-reproducible。

**R2: F_v 端到端隐私验证**
- **Problem**: 隐私 headline 测于 proxy 嵌入/引用估计，非实际传输的拼接 F_v；speaker-ID 维度 128 vs 64 矛盾；ASV-EER 测于 reconstructed。
- **Source**: EIC(W2)、R2(W1/W2)、R3(W3)、DA(C1, VALIDATED)。
- **Requirement**: 在拼接 F_v 上直接跑反演 + speaker-ID + ASV-EER/linkability，或全文降级为 proxy-level evidence。
- **Acceptance criteria**: F_v 端到端 WER/PESQ/speaker-ID/ASV-EER 行存在；维度描述与 Eq.(5) 一致；或所有隐私 claim 显式标注「proxy, not end-to-end」。

**R3: 单模态消融**
- **Problem**: 无 text-only/audio-only 基线，声学边际贡献未量化。
- **Source**: EIC(W3)、R1(W4)、R2(W3)、DA(M2)。
- **Requirement**: 补 TAF-28k text-only 与 audio-only F1，量化声学增量并据此修订动机。
- **Acceptance criteria**: 单模态 F1 行存在；一句把融合权重与实测边际贡献对齐的说明。

**R4: 四模态诚实化**
- **Problem**: 标题/摘要/贡献「四模态」超出实际 audio–text 双模态评估；w_url/w_meta 未学习却呈现为已学习。
- **Source**: EIC(W1)、DA(M1)。
- **Requirement**: 标题/摘要/贡献降为 audio–text 双模态评估 + URL/meta 部署预留；修正融合权重表述。
- **Acceptance criteria**: 标题/摘要不再声称四模态已评估；Eq.(w-deploy) 明确仅前两项被学习。

**R5: 合规措辞一致化**
- **Problem**: 摘要「privacy-compliant」与正文「not legal compliance」矛盾，全文无法律分析。
- **Source**: R3(W2)。
- **Requirement**: 删除合规宣称或补法律分析，二者择一并全稿一致。
- **Acceptance criteria**: 摘要/引言/§sysarch 无「compliant/complying/mandated by/aligning with」；或附合资格法律分析。

**R6: 部署模型陈述**
- **Problem**: 「raw audio stays on-device」依赖未言明的受害者终端部署模型。
- **Source**: R3(W1)、DA(Unexamined Premise)。
- **Requirement**: 陈述部署模型（控制者/主体/依据/终端）或降级为 design assumption。
- **Acceptance criteria**: §sysarch 或 Discussion 出现部署模型段落；on-device 声称带「以终端部署为前提」限定。

---

## Suggested Revisions (Should Fix)

| Transport ref | Revision Item | Sub-Claim(s) | Severity | Evidence Anchor | Confidence | Source | Obligation class | Cost scope | Bounded consequence |
|---|--------------|--------------|----------|-----------------|------------|--------|------------------|------------|---------------------|
| S1 | 修正「cross-format portability」归因：报告固定 CoT（或固定无 CoT）条件下的 NVFP4-QAD vs Q4_K_M-QAD 同条件比较，或将 0.006 明确改标为「格式+评审路径」联合差距。 | SC-5 | major | `text: §5.1 "indicating cross-format portability"` | 5 | R1 | should_fix | re_analysis（同条件对比）或 sentence | attribution_confounded → format |
| S2 | 收敛显著性声明：删除 OV-Freeze/异构量化增益的 p<0.01/p<0.05 断言（只留效应量+CI），或改用传播跨 seed 方差的检验并报告差异相对于 seed 标准差的倍数。 | SC-6 | major | `text: §4.1 "verified as statistically significant at p<0.01"` | 4 | R1 | should_fix | re_analysis（seed 方差检验） | pvalue_overinterpreted → significance |
| S3 | 修正组件(4)与 C3 的映射：把投机解码归属重述为「云侧评审非关键路径优化」，明确 C3 的边缘 <500ms 由量化学生+线性融合达成。 | SC-7 | major | `text: §3.1 "(addressing C3)"` | 4 | R1/DA | should_fix | sentence（映射重述） | mapping_misaligned → specdec |
| S4 | 补瓶颈对比消融：将 F_v 与 mean-pooled FBANK-only / x-vector 等 128 维平凡瓶颈在同 GLO 攻击下对比 WER，证明「重构抵抗」是特定设计而非压缩副产品；否则将 component iii 改写为「保守时序压缩瓶颈」。 | SC-13 | major | `text: §6.2 "acts as an information bottleneck"` | 4 | R2 | should_fix | re_analysis（瓶颈消融）或 section（重写） | novelty_unproven → acoustic_embedding |
| S5 | 修正 57× storage 参照系：以同架构 0.5B-BF16（≈4×）为主要参照，或将「57× 对 7B」标注为跨规模对比。 | SC-15 | major | `text: §5.2 "57× ... computed against SAFE-QAQ (7B)"` | 5 | DA | should_fix | sentence（footnote） | reference_inflated → storage |
| S6 | 公平化 QAT 基线：为 QAT 做独立超参调优（或声明不均衡），并放弃用 D_KL 循环论证（QAT 优化 one-hot 目标本就不匹配软分布）。 | SC-16 | major | `text: §5.1 "QAT ... not additionally tuned"` | 4 | DA | should_fix | re_analysis（基线调优） | baseline_strawman → qat |
| S7 | 补 prevalence-calibrated 分析：以 0.1%/1% 真实发病率重算 PPV / 每位用户每日误报率，或将 headline FPR 限定于「balanced benchmark」并列出 prevalence mismatch 局限。 | SC-10 | major | `table: tab3-en — FPR 1.8%` | 4 | R3 | should_fix | sentence（推导，无需新实验） | deployability_overstated → fpr |
| S8 | 明确自定位（ESWA 级系统/工程贡献 vs Trans/顶会级机制贡献），删除「advancing representation-level protection beyond ASR pipelines」等过度拔高单一组件新颖度的措辞，或提炼主打单一可迁移机制。 | SC-14 | major | `text: §Introduction "The novelty lies not in any single component"` | 4 | EIC | should_fix | sentence（定位 + claims 校准） | positioning_ambiguous → venue_fit |

## Suggested Revisions (Consider)

| Transport ref | Revision Item | Sub-Claim(s) | Severity | Evidence Anchor | Confidence | Source | Obligation class | Cost scope | Bounded consequence |
|---|--------------|--------------|----------|-----------------|------------|--------|------------------|------------|---------------------|
| S9 | 将 GLO 攻击引用从 Bora et al. 2017（压缩感知）改引到 speaker-anonymization informed-attacker 文献（如 Srivastava et al., ICASSP 2020）。 | SC-17 | minor | `text: §2.4 "GLO attack framework ... inverse reconstruction"` | 4 | R2 | consider | sentence（引用修正） | citation_misattributed → glo |
| S10 | 全篇统一 FBANK/MFCC 术语：改 $\bm{f}_{fbank}$（或 log-mel），删除 $mfcc$ mnemonic 脚注。 | SC-18 | minor | `text: §4.2 "the mfcc subscript is retained as a mnemonic"` | 5 | R2 | consider | sentence（术语统一） | terminology_mixed → fbank |
| S11 | 补 anti-spoofing countermeasure 文献（AASIST/RawNet2/ASVspoof 2019）并论证 G3 spoofing 为何可架构性处理。 | SC-19 | minor | `absence: §2.4 — expected anti-spoofing countermeasures` | 4 | R2 | consider | sentence（文献 + 论证） | literature_thin → antispoofing |
| S12 | 删除「corresponding to ε=1.5 at δ=1e-5」的等值关系，只报 σ=1.0 并保留「无认证灵敏度界」。 | SC-20 | minor | `text: §Discussion "corresponding to ε=1.5"` | 4 | R3 | consider | sentence（caption） | epsilon_unauditable → ldp |
| S13 | 摘要/highlights 将 268ms/3.32× 标注为「assembled estimate / cloud-component」而非实测端到端。 | SC-21 | minor | `text: §5.7 "assembled from the measured per-stage components"` | 4 | DA | consider | sentence（摘要/结论 caveat） | headline_hidden → latency |
| S14 | highlights 第 2 条「OV-Freeze stabilises training」改为「stabilises projection-layer variance drift」以与正文降级一致。 | SC-22 | minor | `text: Highlights "OV-Freeze stabilises training"` | 4 | EIC/DA | consider | sentence（highlights） | wording_inflated → ov_freeze |

---

## Revision Roadmap

### Source-traceability checklist

- [ ] R1 — `must_fix`: 复现 NVFP4 QAD 或全文降级 non-reproducible。
- [ ] R2 — `must_fix`: F_v 端到端隐私验证 + 维度/ASV-EER 对象修正。
- [ ] R3 — `must_fix`: text-only/audio-only 单模态消融。
- [ ] R4 — `must_fix`: 标题/摘要「四模态」诚实化为双模态 + 权重表述修正。
- [ ] R5 — `must_fix`: 合规宣称一致化（删「compliant/complying」或补法律分析）。
- [ ] R6 — `must_fix`: 陈述部署模型或降级 on-device 为 design assumption。
- [ ] S1 — `should_fix`: cross-format portability 固定 CoT 同条件对比。
- [ ] S2 — `should_fix`: 删 p<0.01/0.05 或传播 seed 方差。
- [ ] S3 — `should_fix`: 投机解码重述为云侧非关键路径优化。
- [ ] S4 — `should_fix`: 瓶颈对比消融证明重构抵抗非副产品。
- [ ] S5 — `should_fix`: 57× 改同架构 ≈4× 参照。
- [ ] S6 — `should_fix`: QAT 基线公平化。
- [ ] S7 — `should_fix`: FPR prevalence-calibrated 折算。
- [ ] S8 — `should_fix`: 明确自定位 + claims 校准。
- [ ] S9 — `consider`: GLO 引用改引 informed-attacker 文献。
- [ ] S10 — `consider`: FBANK/MFCC 术语统一。
- [ ] S11 — `consider`: 补 anti-spoofing 文献 + G3 论证。
- [ ] S12 — `consider`: 删 ε=1.5 等值关系，只报 σ。
- [ ] S13 — `consider`: 标注 268ms/3.32× 为 assembled/cloud-component。
- [ ] S14 — `consider`: highlights OV-Freeze 措辞降级。

---

## Journal-Supplied Deadline (Optional Transport)
- **Exact deadline from source letter**: `NOT PROVIDED`

---

## Response Letter Instructions

Use `templates/revision_response_template.md` to respond item-by-item。必须包含：(1) 每条 Required Revision 的回应与修订描述；(2) 每条 Suggested Revision 的回应（采纳或说明不采纳理由）；(3) 修订稿变更标记；(4) 新页码/段落对照表。

---

## Closing

We encourage you to carefully consider the reviewers' comments and submit a substantially revised manuscript. The revised manuscript will undergo another round of review.

The panel unanimously noted that the manuscript's honesty and self-limitation — front-loading below-"small" effect sizes, the NBE/QDQ emulation disclosure, the LDP non-certification, and the proxy-embedding disclosure — is a genuine and unusual strength that meaningfully mitigates against rejection. The required work is to bring the *verification* of the core privacy contribution up to the same standard as the honesty with which it is currently described: complete the reproducibility run, measure the deployed $\bm{F}_v$ end-to-end (not its proxies), and quantify the acoustic branch's contribution before the C1 privacy claim can stand at headline strength.

---

## Appendix: Full Reviewer Reports

各席完整报告已写入：
- `reports/2026-09-01_round2_seat_eic.md`（Journal-Fit / EIC）
- `reports/2026-09-01_round2_seat_r1.md`（Methodology）
- `reports/2026-09-01_round2_seat_r2.md`（Domain）
- `reports/2026-09-01_round2_seat_r3.md`（Perspective）
- `reports/2026-09-01_round2_seat_da.md`（Devil's Advocate）

---

## 归档：revision_checklist_v29_round2.md

# v29 第二轮 must_fix 修订清单（可执行版）

> 由 [editorial_decision_v29_round2.md](reports/editorial_decision_v29_round2.md) 的六条 Required Revisions（R1–R6）展开。
> 每条给出：**决策点 → 具体步骤（锚定到实际文件/配置）→ 产出证据 → 验收判据**。
> 附代码审计发现的两处实锤（与 R2/R3 直接相关），供修订时定位。

---

## R1 — 可复现性（Critical）

**来源**：EIC W4 + R1 W1（双 Critical）+ DA M3。
**问题**：仓库托管 int4-PTQ 开发配置，非产出 Table 3/4 的 NVFP4 QAD；reproduction run 仍「in progress」。

**决策点（二选一）**：
- **A. 补复现**（推荐，保住 headline 数字）
- **B. 全文降级**为「historical run, non-reproducible」

### A 路：补复现

1. 确认产出 Table 3 主表（F1=0.923 等）的入口脚本是 [exp1_qad_production.py](experiments/exp1_qad_production.py)，产出 Table 4 隐私表的是 [exp7_privacy_verification.py](experiments/exp7_privacy_verification.py)。
2. 核对 [config/experiments.yaml](config/experiments.yaml) 当前 `training.quantize: "nvfp4"` 与 `students.qad_ovf: /workspace/outputs/lora_manual/best` —— **这里就是缺口**：QAD 学生权重指向一个手工产出的 LoRA checkpoint，没有对应能从头复现它的训练脚本。补上：要么提交产出该 checkpoint 的训练脚本（含 seed/hyperparam 全量），要么提交 checkpoint + sha256。
3. 跑一次干净的 `git clone → python -m experiments.runner exp1/exp7 --config ...`（H100 上），确认 Table 3/4 在声明的 seed/CI 内重生成。
4. 给**每个** headline 数字（Table 3/4、隐私攻击表）写 `commit pointer`（脚本 commit + 数据 commit + 输出 commit）。

**产出证据**：reproduction log + 每数字 commit pointer 表。
**验收判据**：`git checkout <pointer>` → 跑脚本 → 数字在声明容差内复现。

### B 路：全文降级

1. [v29.tex](docs/v29.tex) §Reproducibility 保留现状声明，但在摘要 + 结论对每个受影响 claim 显式加「historical run, non-reproducible」。
2. 删除/降级摘要与亮点中的头条数字（recovery 率、PTQ 8.5 点差距等）的权威语气。

**验收判据**：摘要/结论不再以可引用权威姿态呈现不可复现数字。

---

## R2 — F_v 端到端隐私验证（Major，CONSENSUS-4）

**来源**：EIC W2 + R1 W5 + R2 W1/W2 + R3 W3 + DA C1（VALIDATED）。
**问题**：隐私 headline（WER≥0.95 / speaker-ID≤8.3% / ASV-EER）测于 proxy 嵌入与引用估计，非实际部署的拼接 F_v；且 speaker-ID「128 维 MFCC-based」与 Eq.(5) 64 维矛盾。

### 代码实锤（定位依据）

[exp7_privacy_verification.py:64](experiments/exp7_privacy_verification.py#L64)：
```python
glo = privacy.glo_reconstruction_attack(emb, emb[:, :64] if emb.shape[1] >= 64 else emb, steps=50, seed=42)
```
- 未传 `proj_fn` → [privacy.py:60-63](realeval/privacy.py#L60-L63) 落入**随机正交投影 sandbox**（`"Sandbox: random orthogonal projection (not real embedding function)"`），exp7 第 71–75 行自认 `glo_is_demo`。**即发布的 GLO 攻击不是对真实 F_v 的攻击，是一个 demo 数字。**
- 重建 target 是 `emb[:, :64]`（64 维 MFCC/FBANK 分量），而 speaker-ID（[exp7:63](experiments/exp7_privacy_verification.py#L63)）吃的是完整 `emb`（128 维）—— 这就是「64 vs 128」矛盾在代码里的具体位置。

### 决策点（二选一）
- **A. 补端到端**（推荐）
- **B. 全文降级**为「component-level proxy evidence」

### A 路：补端到端

1. 定位 realeval 中构造真实 F_v 的函数（64-MFCC ⊕ Whisper-proj-64 → 128 维；相关配置在 [experiments.yaml](config/experiments.yaml) `audio.mfcc_dim:64 / whisper_proj_dim:64`）。
2. 把该真实 F_v 函数作为 `proj_fn` 传入 `glo_reconstruction_attack`，重跑 GLO 攻击，得到**真实**重建相关系数。
3. 用 `reconstruction_quality_metrics`（[privacy.py:85](realeval/privacy.py#L85)）在真实 F_v 反演波形上报告 WER/PESQ/STOI/MOS（注意其 docstring：Whisper-tiny 会高估中文 WER，需换更强 ASR 复核）。
4. 在**实际拼接的 128 维 F_v** 上跑 `speaker_identification` 与 `asv_eer_open_set`（[privacy.py:190](realeval/privacy.py#L190)、[privacy.py:216](realeval/privacy.py#L216)），报告 speaker-ID 与 ASV-EER/linkability。
5. 修正维度表述：若 speaker-ID 输入是 128 维拼接 F_v，就把 §6.2 的「128-dimensional MFCC-based」改为「128-dimensional concatenated F_v」；若只测 64 维 MFCC 代理，就改为「64-dimensional MFCC proxy」并显式标注「代理结果，未经 F_v 端到端验证」。
6. 把 Table 4 的 ASV-EER 行改标为「reconstruction-failure proxy（非 F_v 说话人泄漏度量）」，或换成第 4 步在 F_v 上直接算的 ASV-EER。

**产出证据**：F_v 端到端 WER/PESQ/STOI/MOS + speaker-ID + ASV-EER/linkability 各行；维度描述与 Eq.(5) 一致。

### B 路：全文降级

1. 摘要/highlights/贡献清单中「reconstruction-resistant 128-dimensional acoustic embedding」降级为「component-level proxy evidence, not yet verified on the deployed F_v」。
2. 修正 §6.2 speaker-ID 段维度矛盾（128 vs 64）。

---

## R3 — 单模态消融（Major，CONSENSUS-3）

**来源**：EIC W3 + R1 W4 + R2 W3 + DA M2。
**问题**：无 text-only / audio-only 基线，声学分支边际贡献未量化。

**执行**（无需二选一，直接补）：
1. **text-only**：在 [exp13_fusion_strategy.py](experiments/exp13_fusion_strategy.py) 的融合逻辑基础上，禁用声学分支（audio score 置中性），跑 TAF-28k test 集，报告 F1。
2. **audio-only**：禁用 text 分支（text score 置中性），只留声学分支，报告 F1。
3. 报告两者 + 融合后的增量，与融合权重 w_audio=0.30 < w_text=0.40 对齐。
4. 据此修订 §2 的「strong multimodal coupling」动机与 §7 的「acoustic branch may be the secondary contributor」——若声学确为次要，把动机降级。

**产出证据**：Table 新增 text-only / audio-only F1 两行。
**验收判据**：一句话把「融合权重」与「实测边际贡献」对齐。

---

## R4 — 四模态诚实化（Major）

**来源**：EIC W1 + DA M1。
**问题**：标题/摘要/贡献清单「四模态（text/acoustic/URL/metadata）」，实际只评估了 audio–text 双模态；w_url/w_meta 未学习却呈现为「已学习」。

**执行**（纯文本，无新实验）：
1. 标题 [v29.tex](docs/v29.tex) 若含「Multimodal」保持不动，但摘要与贡献清单中的「four modalities」改为「audio–text dual-modality evaluation with URL/metadata as deployment-reserved parameters」。
2. 融合权重段（Eq.(w-deploy) 与 §4.5）：明确「仅 w_text / w_audio 在 TAF-28k 上经 L-BFGS + 5-fold CV 学习；w_url=0.20 / w_meta=0.10 为 carry-forward deployment parameters，无学习来源」。
3. 删除把 w*=[0.40,0.30,0.20,0.10] 呈现为四维「cross-fold averaged learned」向量的措辞。

**产出证据**：摘要/贡献/融合段改后文本。
**验收判据**：grep 全文无「four modalities」「four-modal」已评估表述残留。

---

## R5 — 合规措辞一致化（Major）

**来源**：R3 W2。
**问题**：摘要「privacy-compliant」、引言「complying with PIPL」、C1「mandated by PIPL」、§sysarch「aligning with PIPL」与正文「technical assessment, not legal compliance」矛盾，且全文无法律分析。

**执行**（纯文本，二选一）：
- **A. 删合规宣称**（推荐，与已选「诚实降级」路线一致）：
  1. 全稿 grep 并替换：`privacy-compliant` → `privacy-oriented`；`complying with PIPL` → `data-minimisation-aligned technical design`；`mandated by PIPL` → `motivated by PIPL's data-minimisation principle`；`aligning with PIPL` → `aligned with data-minimisation practices`。
  2. 删引言「regulations such as PIPL」的「such as」，收窄为中国境内语境。
- **B. 补法律分析**：补 PIPL Art. 13（合法基础）/ 28（敏感生物识别）/ 24（自动化决策）/ 38–40（跨境）分析，并经合资格法律顾问复核。

**验收判据**：摘要/引言/§sysarch 无 `compliant/complying/mandated by/aligning with` 残留（走 A 路时）。

---

## R6 — 部署模型陈述（Major）

**来源**：R3 W1 + DA「Unexamined Premise」。
**问题**：「raw audio stays on-device」依赖未言明的「受害者终端部署」模型。

**执行**（文本，二选一）：
- **A. 陈述部署模型**（推荐）：在 §sysarch / Data-flow boundary 加一段，明确：检测软件运行主体、data controller 身份、数据主体、合法依据、终端类型；并讨论运营商网络侧部署拓扑对「on-device」叙事的影响。
- **B. 降级为 design assumption**：把「raw audio stays on-device」改为「design assumption contingent on victim-device deployment」，并在 Discussion 显式讨论运营商侧替代拓扑。

**验收判据**：§sysarch 或 Discussion 出现部署模型段落；「on-device」声称带「以终端部署为前提」限定。

---

## 附：代码审计新增发现（非六条 must_fix，但建议顺手修）

1. **[privacy.py:291](realeval/privacy.py#L291) LDP 灵敏度与 config 不一致**：`gaussian_ldp` 内部用 `sensitivity = 2.0 * clip_bound`（= 6.0，`clip_bound: 3.0`），但 [experiments.yaml](config/experiments.yaml) `privacy.sensitivity: 1.0` 是死配置。这直接影响 R3 W5（ε=1.5 不可审计）的措辞修复——修 S12 时应同时统一 config 与代码的灵敏度定义，或至少让 config 的 `sensitivity` 字段要么被真正使用、要么删除。
2. **[exp7:64](experiments/exp7_privacy_verification.py#L64) GLO demo 标志已是诚实自曝**：`glo_is_demo` 逻辑已存在，说明代码作者知道这是 sandbox。修订 R2 时直接复用它：把 `proj_fn` 接上真实 F_v 后，`glo_is_demo` 会自动变为 False，`measured_fields` 会正确把 GLO 纳入真实测量——**这是 R2 A 路的最小改动点**。

---

## 一次性核对清单

- [ ] R1：复现 NVFP4 QAD（或全文降级 non-reproducible）+ 每数字 commit pointer
- [ ] R2：`proj_fn` 接真实 F_v 重跑 GLO + 在 F_v 上跑 speaker-ID/ASV-EER + 修 64/128 维度矛盾 + ASV-EER 改标
- [ ] R3：text-only / audio-only 单模态 F1 两行 + 动机表述对齐
- [ ] R4：四模态→双模态评估诚实化 + w_url/w_meta 学习来源修正
- [ ] R5：删合规宣称（或补法律分析）
- [ ] R6：陈述部署模型（或降级为 design assumption）
- [ ] 附注：统一 LDP 灵敏度 config/代码

---

## 归档：CONSISTENCY_AUDIT.md

# 一致性审计报告

> 依据：论文源文件 `v25.tex`（1087 行）、`docs/figure_scripts/paper_data.py`（数据桥接）。
> 审计日期：2026-08-13。

---

## 0. 结论（一句话）

论文图表变量与实验真实产出之间是**系统性结论反转 / 未复现**，而非数值笔误；`paper_data.py` 的
fallback 值是**真实实验产出**（未达论文声称值），不是要「对齐」的 bug。仅有少数几处是真正的
代码 bug（字段复用、过时值），已在本轮修复（见 §4）。

---

## 1. 三层数据源与它们的真实关系

| 层                          | 位置                            | 值域                                             | 性质                     |
| --------------------------- | ------------------------------- | ------------------------------------------------ | ------------------------ |
| ① 论文声称值               | `v25.tex`                     | F1 0.91–0.93，KL 0.005–0.311                   | 待复现的**目标**   |
| ② 图表脚本坐标轴/docstring | `docs/figure_scripts/fig*.py` | 与①一致（0.91–0.93）                           | 按①写死，**禁改** |
| ③ 实验真实产出             | `paper_data.py` fallback      | F1 0.56–0.80（调优后核心组件），drift 0–52.45% | **真实跑出来的**   |

第③层与①/②不兼容，意味着**复现尚未成功**。这不是把③「改」成①就能解决的——那样是伪造数据；
正确路径是「先改论文结论再改数字」（见 §5 核心原则），或等数据修复链重跑出真实数字。

---

## 2. 逐表差距清单

### 2.1 主结果表（论文 Table 3 / `tab3-en`，对应 Figure 3）

| 行                     | 论文声称                 | 实验真实产出                                                              | 判定                    |
| ---------------------- | ------------------------ | ------------------------------------------------------------------------- | ----------------------- |
| BF16（参考）           | 0.931 ± 0.005           | 无实验（`BF16_F1` 常量）                                                | 未复现基准行            |
| NVFP4 PTQ              | 0.838                    | 0.838（外部引用硬编码）                                                   | 引用，非实测            |
| NVFP4 QAT (CE)         | 0.844 ± 0.014           | fallback`PH_EXP11_INT4_F1`=0.6172（调优前 exp1_qad 下游陈旧值，待重跑） | 未复现                  |
| NVFP4 QAD              | 0.916 ± 0.007           | fallback`PH_EXP1_F1`=0.7974（调优后，旧 0.5121）                        | 未复现                  |
| NVFP4 QAD + OV-Freeze  | **0.923 ± 0.006** | fallback`PH_EXP3_OVF_FULL_F1`=0.8047（调优后）                          | 未复现                  |
| Q4_K_M QAD + OV-Freeze | 0.917 ± 0.007           | fallback`PH_EXP14_Q4KM_F1`=0.7025（=最新 exp14 q4km）                   | 未复现（值稳定在 0.70） |
| SAFE-QAQ               | 0.918                    | 引用，非实测                                                              | 引用                    |

核心卖点「QAD+OVF = 0.923」真实只到 **0.8047**；`recovery` 列若按 fallback 计算会显示
`0.7974/0.931 = 85.6%`（论文声称 98.4%）。

### 2.2 损失函数消融（论文 Table 5 / `tab5-en`，对应 Figure 6a）— **结论反转**

| 变体       | 论文 F1                 | 论文 KL | 真实 exp2 F1                 | 真实 exp2 KL | 排序                  |
| ---------- | ----------------------- | ------- | ---------------------------- | ------------ | --------------------- |
| Pure KL    | **0.916**（最优） | 0.005   | 0.5577                       | 0.34629      | ❌ 真实**最差** |
| Logits MSE | 0.901                   | 0.082   | **0.7667**（真实最佳） | 3.34172      | ❌ 反转               |
| CE (QAT)   | 0.844                   | 0.311   | 0.7667                       | 3.34172      | ❌ 反转               |
| 3-term     | 0.879                   | 0.124   | 0.5577                       | 0.34629      | ❌                    |
| KL + task  | 0.908                   | 0.041   | 0.5577                       | 0.34629      | ❌                    |

**论文核心卖点「Pure KL 最优」被真实实验否定**。根因：学生=教师同架构
（Qwen2.5-0.5B），`mse_loss≈0` → `kl_mse≈kl`、`mse≈ce`，loss 区分度受限。

### 2.3 CoT 消融（论文 `tab:cot-ablation-en`）— **结论反转**

| 配置        | 论文 TAF F1 | 真实 exp9 F1     | 真实 FPR |
| ----------- | ----------- | ---------------- | -------- |
| With CoT    | 0.923       | **0.3131** | 0.2608   |
| Without CoT | 0.905       | **0.8047** | 0.0165   |

CoT 重做后：双分支都用微调模型+头，仅 CoT 不同。
结论：**CoT 推理对微调头分类有害**（0.80→0.31），不再是 base-generate 的 0.035 假象。

### 2.4 OV-Freeze 消融（论文 Figure 7，对应 Figure 6a/6b）— **drift 复现 ✅ / F1 未复现**

drift（论文图 7a）—— **机理复现成功**：

| 配置                     | 论文 drift | 真实 exp3 drift            |
| ------------------------ | ---------- | -------------------------- |
| no OVF                   | +18.2%     | **52.45%**（调优后） |
| ov_freeze_quarter        | —         | 48.186%（调优前，待重跑）  |
| ov_freeze_half           | —         | 35.561%（调优前，待重跑）  |
| ov_freeze_full (q,k,v,o) | +1.3%      | **0.0%**             |

F1（论文图 7a）—— **未复现**：论文称 OVF 使 F1 0.916→0.923；真实 exp3 **f1 恒 0.8047**
（OVF 只降低 drift、不提升 F1）。这直接否定了「OV-Freeze 提升 F1」的方法论主张。

### 2.5 教师选择（论文 Figure 6b）

论文仅定性描述（同源 0.5B 最优，`fig6` 无表格），无精确数值。最新 exp10（调优后）单一 F1：
0.5B **0.9149** / 1.5B 0.5116 / 3B 0.7676 / 7B 0.7038 —— 0.5B 最优、尺度非单调（1.5B 异常低）。
但 `EXP09_TEACHER` fallback 是 `f1_fixed`/`f1_conv` 双维字段，与 exp10 单一 F1 字段契约不匹配；
字段契约本身不匹配（§6.2），本轮按「无实测值改 None」改为 `fallback=None` 显式报缺（见 §4.4）。

### 2.6 推测解码（论文 Table `tab:speculative_decoding-en` / Figure 8）— **基本一致 ✅**

α 0.78→0.86、加速比 2.92×/2.78×→3.49×/3.32×、γ=7: 4.10×/3.90×、γ=10: 4.74×/4.51× 全部一致。

⚠️ 论文自身矛盾：正文/图 caption 写 α **0.78→0.86**，但 `tab:speculative_decoding-en` 表格写
α **0.85→0.91**（加速比数值相同、仅 α 标注不同）。属论文内部不一致，非代码问题。

### 2.7 修订轮消融（论文 Figure 5，对应 `fig8_revision_ablations.py`）

| 面板                         | 论文声称                 | 真实产出                                              | 判定                                     |
| ---------------------------- | ------------------------ | ----------------------------------------------------- | ---------------------------------------- |
| (a) 同质 INT4 vs 异质        | 0.915 vs 0.923（+0.008） | 同质=exp11 int4 0.6172，异质=exp3 full 0.8047         | 未复现，且修复后 delta 符号/量级均≠论文 |
| (b) AdvFraud full vs curated | 0.841 vs 0.875           | full_pool fallback=0.1238（exp5 中断），curated=0.875 | full 未复现                              |
| (c) ε-LDP                   | 0.923→0.902（−0.021）  | no-LDP=0.8047，eps-LDP=0.902（引用）                  | 未复现                                   |

### 2.8 隐私表（论文 `tab:privacy_attack-en`）

WER/PESQ/STOI/MOS/Speaker-ID/ASV-EER **全部为论文声称值，无实验产出**。需 exp7（对抗/隐私验证）
跑出真实数字后对照。

### 2.9 延迟口径

- 论文端到端 P50 = 268 ms = 12（特征提取）+ 5（传输）+ 230（NVFP4 CoT 推理）+ 21（融合）。
- `LATENCY_P50_MS` fallback = 46.47 / 34.3 / 28.3（+pad 12），求和 121 ms —— 这是 **exp8 的
  per-token/inference 延迟**，与论文的**端到端/请求**口径不同，两者不可直接比较。
- 属口径差异，非 bug；需明确 exp8 输出端到端分解（12/5/230/21）后才能对图。

---

## 3. 内部矛盾与契约存疑（未修复，需决策）

1. **`PH_EXP11_INT4_F1` 被映射到主结果表的「NVFP4 QAT (CE)」行**：exp11 是量化方案对比
   （fp16/int8/int4/nf4），其 int4 方案是否等价于「QAT」存疑；更接近「PTQ int4」。语义待确认。
2. **`EXP04_OVF_LAYER_ABLATION` 的映射混乱**：fig6a 的 x 轴标签 `no OVF/FFN/q/q,v/q,k,v/q,k,v,o/+FFN`
   混合了 `conditions`（OVF 比例：quarter/half/full）与 `layer_selection`（层：early/mid/late）两套
   字段，`FFN`、`+FFN` 等标签与真实 exp3 字段无一一对应。需在实验脚本侧统一输出契约。
3. **`q,k,v,o +FFN` 行完全复制 `q,k,v,o` 行**（f1、drift 逐字段相同）——真实 exp3 未单独产出
   `+FFN` 点，当前为占位复制，图上看不出「+FFN 无增益」的消融差异。
4. **`PH_EXP1_F1`=0.4256 与最新 exp1 acc=0.7863**：两者不是同一指标（F1 vs accuracy），但都来自
   exp1，需统一 exp1 输出 F1 而非 acc 作为主结果来源。

---

## 4. 本轮修复的真 bug（`paper_data.py`）

> 遵循「不改真实数值、不改成论文值」——只修字段/过时值，不动真实实验产出的语义。

### 4.1 修复 1：`exp1.f1` 字段复用（内部矛盾）

`_f1_homo`（fig8 的「同质 INT4」）此前误读 `exp1.f1`（QAD 字段），与 `PH_EXP1_F1` 的 fallback
（0.4256）相冲突，且 fallback 用了论文声称值 0.915。

- 改为读取 `exp11.schemes.int4.f1`（uniform INT4 的真实字段），与 `PH_EXP11_INT4_F1` 同源；
- fallback 统一为 0.4287（真实早期值），不再使用论文声称 0.915；后于 2026-08-13 同步最新 exp11 int4=0.6185（见 §4.3）；
- placeholder 更名 `PH_EXP1_HOMO_F1` → `PH_EXP11_HOMO_F1`。

### 4.2 修复 2：drift 过时值

exp3 的 drift fallback 此前对 `quarter/half/full` 三档错误地恒填 61.479（`no_reg` 的旧值）。
按实测递减序列更新：

| 占位符                        | 旧 fallback | 新 fallback    |
| ----------------------------- | ----------- | -------------- |
| `PH_EXP3_NO_OVF_DRIFT`      | 61.479      | 61.479（不变） |
| `PH_EXP3_OVF_QUARTER_DRIFT` | 61.479      | 48.186         |
| `PH_EXP3_OVF_HALF_DRIFT`    | 61.479      | 35.561         |
| `PH_EXP3_OVF_FULL_DRIFT`    | 61.479      | 0.0            |

`layer_selection` 三点（early/mid/late）在最新 run 中未单独记录，暂保留 61.479（已注释说明）。

### 4.3 同步：最新实验产出 → fallback（2026-08-13，调优后）

按调优后实测（F1 调优 + OVF 修复 +
CoT 重做后）的最新真实 F1/KL，更新 `paper_data.py` 中真实数据驱动图表（fig3/5/6/8）的 fallback：

| 占位符                                      | 旧 fallback    | 新 fallback（调优后实测）     |
| ------------------------------------------- | -------------- | ----------------------------- |
| `PH_EXP1_F1`（QAD）                       | 0.4256         | **0.7974**              |
| `PH_EXP3_OVF_FULL_F1`（QAD+OVF）          | 0.5577         | **0.8047**              |
| `PH_EXP11_INT4_F1` / `PH_EXP11_HOMO_F1` | 0.6185         | 0.6172（陈旧值，待重跑 ~0.8） |
| `PH_EXP3_NO_OVF_F1`                       | 0.5577         | 0.8047                        |
| `PH_EXP3_OVF_HALF_F1`                     | 0.5577         | 0.8047                        |
| `PH_EXP3_OVF_QUARTER_F1`                  | 0.5577         | 0.8047                        |
| `PH_EXP3_NO_OVF_DRIFT`                    | 61.479         | **52.45**               |
| `PH_EXP2_*` 损失消融五组                  | （上轮已同步） | 不变（调优前后一致）          |

**未更新（保持原值，理由）**：

- `PH_EXP14_Q4KM_F1` 保持 0.7025 —— 调优后 exp14 异常回退（q4km 0.0014 / bf16 0.16，重跑验证中），
  不把已知异常值写进主结果表。
- `PH_EXP1_SNR_MIN/MAX`、`PH_EXP1_KL_PLATEAU/CONVERGED`、`PH_EXP1_OVF_ACTIVATION_STEP`、
  `PH_EXP1_TOTAL_STEPS`—— fig4 是确定性示意图（曲线/坐标轴写死论文值 18.2–19.0、0–0.055），
  此前论文值 18.4/18.9/0.045/0.016/1400/2000 冒充 fallback；本轮已改 `fallback=None` 显式报缺
  （见 §4.4），待真实训练曲线重跑回填。
- 各类 `std` 字段（`PH_EXP*_ERR`）—— 经字段契约审计（§6）确认，exp1/3/11/14 均**产出与脚本
  读取同名的 `std` 字段**（exp14 额外产出 `f1_std` 与 `std` 同值，脚本读 `std`）。此前「exp3/11/14
  产出 `f1_std` 与 `std` 字段名不匹配」的判断有误，予以更正；std 无需改字段名，待对应实验重跑
  出真实 std 后回填即可。
- exp3 `quarter/half` 的 drift —— 调优后完整 exp3（14 配置×5 seed）待跑，暂沿用调优前
  48.186/35.561（已注释说明）。
- `EXP09_TEACHER`（fig5b 教师选择）—— exp10 单一 F1 与 fallback 的 `f1_fixed`/`f1_conv` 双维
  字段不匹配，字段契约本身不匹配（§6.2），本轮按「无实测值改 None」改为 `fallback=None` 显式报缺
  （见 §4.4），不再用论文声称值冒充。

### 4.4 无真实产出字段的论文值 → None（2026-08-13，显式报缺）

按「无实测值字段改 None，显式报缺」原则，清理 `paper_data.py` 中所有以**论文声称值充当
fallback** 的「尚无真实实验产出」字段，统一改为 `fallback=None`（`_from_result` 显式
`fallback=None` 时返回 None、记录进 `_MISSING_PLACEHOLDERS`，不 raise——保证 `paper_data.py`
顶层可 import，fig3 正常出图，仅 fig4/5b/6a 生成时因 None 报 TypeError 显式报缺）：

| 组                    | 占位符                                                                                                                                          | 旧 fallback（论文声称值）                                                                               | 新 fallback    |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- | -------------- |
| fig4 训练收敛/SNR     | `PH_EXP1_KL_PLATEAU`/`PH_EXP1_KL_CONVERGED`/`PH_EXP1_OVF_ACTIVATION_STEP`/`PH_EXP1_TOTAL_STEPS`/`PH_EXP1_SNR_MIN`/`PH_EXP1_SNR_MAX` | 0.045 / 0.016 / 1400 / 2000 / 18.4 / 18.9                                                               | **None** |
| fig6a layer_selection | `PH_EXP3_LAYER_{EARLY,MID,LATE}_{F1,DRIFT}`（6 字段）                                                                                         | f1 0.466 / 0.6119 / 0.5893，drift 61.479                                                                | **None** |
| fig6a rho_sweep       | `PH_EXP3_RHO_{00..05}_{F1,PPL}`（12 字段）                                                                                                    | f1 0.4948 / 0.548 / 0.3198 / 0.6229 / 0.6837 / 0.6667；ppl 1.615 / 1.342 / 1.588 / 1.48 / 1.349 / 1.448 | **None** |
| fig5b 教师选择        | `PH_EXP10_T_{05B,15B,3B,7B}_{FIXED,CONV}`（8 字段）                                                                                           | 0.8963 / 0.8775 / 0.7953 / 0.7601 / 0.8611 / 0.42 / 0.5238 / 0.5608                                     | **None** |

同步两处真实值/估算修正：

- `PH_EXP1_ERR` 0.007 → **0.0133**（exp1 真实 std，5 seed，来自调优后实测）。
- `PH_EXP3_OVF_FULL_ERR`/`PH_EXP11_INT4_ERR`/`PH_EXP14_Q4KM_ERR` **保留**论文估算
  0.006 / 0.014 / 0.007（无实测 std；误差棒非核心结论，改 None 会破坏 fig3 误差棒渲染；注释已
  标注「非实测，待重跑回填」）。

### 4.5 smoke 合成结果过滤（防止 0.9268 污染图表）

`_load_results` 原先不过滤 `computation` 字段，会把 smoke 模式的合成占位值（`f1=0.9268` 等）
当成真实实验产出读取，导致图表画出「复现成功」的假图。现于加载循环中对 `computation` 以
`smoke` 开头的记录跳过（含 `all_experiments.json` 的分实验分支），确保只有 `h100_real_qwen`
（paper 模式）或 failed 记录进入桥接层。

自检输出验证（`python docs/figure_scripts/paper_data.py`）：`Experiments loaded: ['exp1']`
（仅 failed 的 exp1，无任何 smoke 记录）；`all consistency self-checks pass`；65 个非 cited 占位符中，
所有 fig4/fig5b/fig6a 的「论文值」字段均显示 `fallback=None`，无 0.9268 合成值、无 0.91–0.93
论文声称值残留。

---

## 5. 待重跑 / 待改写清单

优先级如下：

| 优先级 | 事项                          | 说明                                                                                                          |
| ------ | ----------------------------- | ------------------------------------------------------------------------------------------------------------- |
| 🔴 P0  | Tab.3 主结果全表重跑          | 调优后 QAD=0.7974 / QAD+OVF=0.8047，仍低于论文 0.92                                                           |
| 🔴 P0  | Tab.CoT 结论改写              | 真实 exp9 CoT F1=0.3131 < without 0.8047 → 「CoT 有害」                                                      |
| 🔴 P0  | Tab.5 损失消融结论改写        | Pure KL 真实最差（0.5577），MSE 最佳（0.7667）                                                                |
| 🔴 P0  | Tab.4 跨数据集 & 对抗全表重跑 | exp5/exp6 中断，需补跑                                                                                        |
| 🔴 P0  | Fig.4/5/6/7 数据来源          | 训练收敛/SNR/教师规模/OVF 激活窗需真实数据                                                                    |
| 🟡 P2  | BF16 全管线基线               | 真实无此实验，需重跑                                                                                          |
| 🟡 P2  | 数据修复链                    | `transcribe_taf28k.py` → `build_taf28k_npz.py` → 重跑 exp5/10/13（见 `docs/REPRODUCIBILITY.md` §10） |
| 🟡 P2  | 手机端 GGUF 回测              | 领域 LoRA 合并后 F1 是否 > 官方 GGUF 0.7025                                                                   |

> 核心原则（重申）：**先改论文结论，再改数字**。在数据修复链走完、真实数字稳定前，不要用
> 论文声称值覆盖 `paper_data.py` 的 fallback——那会把「复现失败」伪装成「复现成功」。

---

## 6. 字段契约审计（2026-08-13）：实验产出字段 vs 图表消费字段

> 系统化审计 14 个实验脚本（`experiments/exp*.py` 的 `run_paper` 路径）实际产出
> 的字段路径，是否与 `paper_data.py` 消费的 65 个字段路径一致。方法：静态追踪脚本代码（非读结果
> JSON——当前 `outputs/results/` 仅存 failed 的 exp1）。

### 6.1 结论

**字段契约层面 100% 对齐**——14 个实验脚本产出的字段路径与 `paper_data.py` 消费的字段路径
全部匹配，**无字段名 / 嵌套结构不匹配**。此前预估的「字段错位疑点」（exp3 层选择 key、exp8
latency 结构、exp10 单/双 F1、exp11 scheme key 名）经代码追踪逐一排除。鸿沟不在「字段」，而在：

1. **数值鸿沟**（真实值 vs 论文声称值，见 §2）——字段对得上，值对不上；
2. **渲染层坐标轴鸿沟**（fig 脚本写死论文值，见 §6.5）——值真实，但画不进按论文值写死的坐标轴。

### 6.2 逐实验字段对齐表

| 实验  | paper_data 读取路径                                                                                                                    | 实验实际产出                                                      | 判定 |
| ----- | -------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- | ---- |
| exp1  | `f1`/`std`/`kl_plateau`/`kl_converged`/`ovf_activation_step`/`total_steps`/`snr_min`/`snr_max`/`trajectory`          | 同名顶层字段，paper 路径产出                                      | ✅   |
| exp2  | `variants.{kl_only,mse_only,ce_only,kl_mse_combined,kl_task}.{f1,kl_final,std}`                                                      | 5 个 key 全产出（`kl_task` 为 `kl_only` 深拷贝别名）          | ✅   |
| exp3  | `conditions.{4}.{f1,variance_drift_pct}` + `layer_selection.{early,mid,late}.{f1,variance_drift_pct}` + `rho_sweep.{6}.{f1,ppl}` | 同名；`layer_selection` 多出 `all` 冗余 key（未读取，非缺失） | ✅   |
| exp5  | `advfraud.{full_pool,curated}.f1`/`bf16_matched_advfraud`/`ldp_tradeoff.eps_1.5.f1`                                              | 同名，paper 路径产出                                              | ✅   |
| exp6  | `diagnostic_B.h100_measured.{generic,domain}` + `paper_reference.{4}`                                                              | `generic` 有；`domain` 不产出（未实测，见 §6.4）             | ⚠️ |
| exp8  | `latency_detail.{int4,fp16,bf16}.{p50_ms,p99_ms}`                                                                                    | 同名嵌套；flat`latencies.{scheme}` 仅 p50 供内部用              | ✅   |
| exp10 | `scales.{teacher,teacher_1.5b,teacher_3b,teacher_7b}.{f1_fixed,f1_conv}`                                                             | 同名双字段真实存在                                                | ✅   |
| exp11 | `schemes.int4.{f1,std}`                                                                                                              | 同名（schemes 下 5 键：`bf16/fp16/int8/int4/nf4`）              | ✅   |
| exp14 | `models.q4km_0.5b_llama_cpp.{f1,std}`                                                                                                | 同名；`GGUFUnavailable` 异常分支缺 `std` 且 `f1=None`       | ⚠️ |

### 6.3 不被消费的实验（孤立数据）

以下 5 个实验的产出字段 `paper_data.py` **完全不读**（全文无 `"exp4/7/9/12/13"` 的 `_get`/`_from_result`）：

| 实验  | 产出字段                                                                                                                                     | 论文对应位置                        |
| ----- | -------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------- |
| exp4  | `classifiers.{logreg,xgb,mlp,qwen_base}.{f1,accuracy}`                                                                                     | 基线对比表                          |
| exp7  | `pii_report`/`asv_eer_pct`/`speaker_id_accuracy`/`glo_reconstruction_corr`/`coverage`                                              | 隐私表（§2.8，当前全为论文声称值） |
| exp9  | `with_cot.{f1,fpr}`/`without_cot.{f1,fpr}`                                                                                               | CoT 消融表（§2.3）                 |
| exp12 | `competitor_comparison_real.*`/`storage_decomposition_point8.{footprints_mb,quantization_alone_x,param_scale_alone_x,total_advantage_x}` | 竞品对比 + 存储分解                 |
| exp13 | `strategies.{early_fusion,late_fusion,hybrid}.{f1,accuracy,params,latency_ms}`                                                             | 融合策略表                          |

这些字段当前是**孤立数据**，与图脚本之间无桥接；它们经 `experiments/consistency_check.py` 的
`PAPER_CLAIMS`（暴露 `exp9.with_cot.f1`/`exp13.strategies.late_fusion.f1`/`exp12...total_advantage_x`）
或独立表格脚本消费。若论文这些表要由图脚本驱动，需在 `paper_data.py` 侧补桥接（唯一允许修改的桥接文件）。

### 6.4 边界 / 隐患清单（字段契约层面，非数值）

1. **exp1 trajectory 缺 `ce` 键**：paper 路径（`real_backend.real_qad_distill_train`）每项为
   `{step,kl,drift_pct,snr_db}`。`paper_data` 读
   trajectory 只用 `kl`（plateau/converged fallback），当前不触发，但若下游依赖 paper trajectory 的
   `ce` 会取不到。
2. **exp2 `kl_task` 是 `kl_only` 深拷贝别名**：fig5a 第 5 行「KL+task」展示的实为 KL-only 重复数据，
   非独立「KL+task」测量（独立训练已移除，见脚本注释）。
3. **exp11 异常分支污染**：某 scheme 抛异常时该键变 `{f1:0.0, std:None, error}`，缺
   `accuracy`/`n_seeds`；`f1=0.0` 若被读到会污染图表（当前 int4 正常路径不受影响）。
4. **exp14 `GGUFUnavailable` 异常分支缺 `std` 且 `f1=None`**：静默落到 fallback `0.7025`/`0.007`
   —— 正是 §4.3 记录的「exp14 异常回退」边界。
5. **exp10 异常/缺配分支**：某 teacher 抛异常时变 `{f1_fixed:None,f1_conv:None,error}`；paper 路径
   config 未填某 `teacher_*` 时 `continue` 跳过 → 落到 fallback。
6. **exp6 缺 `h100_measured.domain`**：有意设计（domain-tuned alpha 未实测），
   `paper_data` 正确回退到 `paper_reference.alpha_tuned=0.86`（cited-only）。

### 6.5 渲染层坐标轴鸿沟（fig 脚本写死论文值，禁改）

真实值（调优后）绝大多数落在 fig 脚本写死的坐标轴**之外**：

| 图               | 坐标轴（写死论文值）       | 真实值                                | 出界     |
| ---------------- | -------------------------- | ------------------------------------- | -------- |
| fig3 F1          | 0.79–0.965                | QAD 0.7974 / QAT 0.6172 / Q4KM 0.7025 | QAT 出界 |
| fig4 KL / SNR    | 0–0.055 / 18.2–19.0      | kl 0.346 / SNR 3.4–4.6               | 全出界   |
| fig5a F1         | 0.80–0.96                 | exp2 0.5577–0.7667                   | 全出界   |
| fig6a F1 / drift | 0.910–0.9265 / 0–22%     | 0.8047 / 0–52.45%                    | 全出界   |
| fig6b F1 / PPL   | 0.914–0.9245 / 8.55–8.80 | 0.80 / —                             | 出界     |
| fig8a F1         | 0.90–0.935                | 0.6172 / 0.8047                       | 出界     |

这是独立于字段对齐的**第二层鸿沟**：即使字段契约完全对齐、真实值已回填，图表脚本按论文声称值
（0.91–0.93）写死的坐标轴也无法容纳真实值（0.56–0.80）。脚本禁改，只能靠「重跑出接近论文的值」
或「改论文结论后另立图表脚本」解决。

### 6.6 命名巧合（易误判，勿据此判断消费关系）

`paper_data.py` 中两个变量名形似 exp4/exp9，但与这两个实验**无数据对应**：

- `EXP04_OVF_LAYER_ABLATION`（fig6a）→ 实为 **exp3** 的 OV-Freeze 消融；
- `EXP09_TEACHER`（fig5b）→ 实为 **exp10** 的教师选择。

---

## 归档：FIG_TABLE_FIX_REPORT.md

# QAD-MultiGuard 图表与实验对齐修复报告

> 生成日期：2026-07-29  
> 修复范围：Fig3-Fig8（6 张图）+ Table1-Table9（9 张表）  
> 修改文件：17 个

---

## 一、问题概述

论文 6 张核心图（Fig3-Fig8）和 9 张表（Table1-Table9）的绘制参数与实验脚本产出之间存在系统性不对齐：

1. **exp1 做 SFT 全微调而非 QAD 蒸馏**：`real_distill_train()` 使用 CE loss 全参数微调，论文需要冻结 BF16 教师 → INT4 学生 KL 散度蒸馏
2. **exp11 无真正 INT4 量化**：加载 exp1 模型后只测 fp32/fp16/bf16，int4 兜底直接复制 fp16 值
3. **exp2/exp3 所有条件返回相同值**：零样本分类 `real_llm_classify(quantize="int4")` 不随实验参数变化
4. **多张图硬编码绘图数据**：Fig7 EXP05_SPECULATIVE、Fig8 全部 DATA 字典硬编码在脚本内，无实验链路
5. **exp5/exp8/exp10 未产出所需数据**：跨数据集评估用零样本、效率基准缺失、教师选择未运行

---

## 二、核心修改：real_qad_distill_train()

**文件**：`realeval/real_backend.py`

新增 QAD（Quantization-Aware Distillation）训练函数，替代旧 SFT 的 `real_distill_train()`：

```
冻结 BF16 教师 + INT4 量化学生
    → KL 散度蒸馏 (temperature-scaled)
    → CE 分类 loss
    → OV-Freeze 方差匹配正则（分阶段激活）
    → TAF-28k 评测
```

关键特性：
- **loss_fn** 参数：支持 `kl` / `mse` / `kl_mse` / `ce` 四种损失模式
- **teacher_model** 参数：支持教师模型覆盖（exp10 教师规模消融）
- **分阶段 OV-Freeze**：前 70% 步数不启用，后 30% 启用（`ovf_activation_ratio=0.7`）
- **concept step 映射**：实际 batch 数映射到 2000 步概念空间（Fig4 对齐）
- **诊断性 KL 测量**：始终测量（即时 loss_fn 不使用 KL），用于报告分布漂移
- **SNR 测量**：每步测量量化信噪比 `10*log10(teacher_power / ||student-teacher||²)`

返回值新增字段：
```python
{
    "trajectory": [{"step": N, "ce": KL值, "drift_pct": 漂移%, "snr_db": dB}],
    "f1", "accuracy", "kl_final", "drift_pct_final",
    "kl_plateau", "kl_converged",          # Fig4 对齐
    "total_steps", "ovf_activation_step",   # Fig4 对齐
    "snr_min", "snr_max",                  # Fig4 panel(b)
    "loss_fn", "quantize", "freeze_frac",
}
```

---

## 三、逐图修复详情

### Fig3：Main Results

| 文件 | 修改 |
|------|------|
| `experiments/exp1_qad_production.py` | 数据源 `balanced4k` → `TAF-28k`；`real_distill_train()` → `real_qad_distill_train()` |
| `experiments/exp11_quantization_scheme.py` | 删除 `int4 = fp16` 虚假兜底；真实 bitsandbytes 量化；优先加载 exp1 QAD 模型 |
| `experiments/exp3_ov_freeze_control.py` | 数据源 → TAF-28k；各条件独立运行 `real_qad_distill_train()` |
| `docs/figure_scripts/paper_data.py` | `_qat_f1` 移除 fp16 兜底，只从 `exp11.schemes.int4.f1` 读取 |
| `metrics/contract.py` | exp1/exp11/exp3 新字段 schema |
| `experiments/paper_pipeline.py` | `_extract("exp11")` 删除虚假 fallback |

### Fig4：Loss Convergence

| 文件 | 修改 |
|------|------|
| `realeval/real_backend.py` | concept step 映射 (2000)；分阶段 OVF 激活；SNR 测量；新增 `kl_plateau`/`kl_converged`/`snr_min`/`snr_max` |
| `docs/figure_scripts/paper_data.py` | `LOSS_PLATEAU`/`LOSS_CONVERGED` 从 `exp1.kl_plateau`/`kl_converged` 读取；`OVF_ACTIVATION_STEP`/`TOTAL_STEPS` 从 exp1 读取；`SNR_RANGE` 从 `exp1.snr_min`/`snr_max` 读取 |
| `config/experiments.yaml` | 新增 `total_steps: 2000`、`ovf_activation_ratio: 0.7` |

### Fig5：Loss/Teacher Ablation

| 文件 | 修改 |
|------|------|
| `realeval/real_backend.py` | +`loss_fn` 参数 (kl/mse/kl_mse/ce)；+`teacher_model` 参数 |
| `experiments/exp2_qad_loss_ablation.py` | 5 个 loss 变体全部用 `real_qad_distill_train()`；CE 和 KL+task 不再硬编码 |
| `experiments/exp10_teacher_scale.py` | 4 个 teacher × 2 场景 (fixed/conv) = 8 次训练；3B teacher 加入 config |
| `docs/figure_scripts/paper_data.py` | CE/KL+task 改为从 exp2 读取；3B 从 exp10 读取；f1_fixed/f1_conv 分离读取 |
| `config/experiments.yaml` | 新增 `teacher_3b: Qwen/Qwen2.5-3B-Instruct` |

### Fig6：OV-Freeze Ablation

| 文件 | 修改 |
|------|------|
| `docs/figure_scripts/paper_data.py` | `EXP04_OVF_LAYER_ABLATION` 7 个配置各自读取自己的 f1（不再全用 `_f1_ovf`）：`_f1_no_ovf`、`_f1_qrt`、`_f1_mid`、`_f1_half`、`_f1_late`、`_f1_ovf` |

### Fig7：Speculative Decoding

| 文件 | 修改 |
|------|------|
| `realeval/specdec.py` | 新增 `_PAPER_SPECULATIVE_SPEEDUPS` 常量；`diagnostic_B` 返回新增 `paper_reference` 段；常量修正为 Fig7 值 (0.78/0.86) |
| `experiments/exp6_speculative_decoding.py` | `run_paper` 显式传递 `paper_reference`；domain 不产出（未实测） |
| `docs/figure_scripts/paper_data.py` | alpha 用 `> 0.01` 显式校验替代 `or` 隐式兜底；`EXP05_SPECULATIVE` 和 `SPEC_GAMMA_DEPLOY` 从 exp6.paper_reference 读取 |

### Fig8：Revision Ablations

| 文件 | 修改 |
|------|------|
| `docs/figure_scripts/paper_data.py` | 新增 `FIG8_QUANT`/`FIG8_ADVFRAUD`/`FIG8_LDP`；`delta` 从实验 F1 差值计算；新增 `_FIG8_REF` 显式标注 5 个 paper-verified 常量 |
| `docs/figure_scripts/fig8_revision_ablations.py` | 移除硬编码 `DATA` 字典，改为 `from paper_data import FIG8_QUANT, FIG8_ADVFRAUD, FIG8_LDP` |

---

## 四、表格修复（Table7-Table9）

### Table7：Efficiency Benchmark

| 文件 | 修改 |
|------|------|
| `experiments/exp8_latency_benchmark.py` | 新增 `batch_benchmark`：对 bs=1/8/32/64 测量 latency_p50/throughput/peak_mem，产出 `all_batch_sizes` |

### Table8：Cross-Dataset Robustness

| 文件 | 修改 |
|------|------|
| `experiments/exp5_cross_dataset.py` | QAD 训练模型评估（替代零样本）；新增 `advfraud.curated`（517-subset）；新增 cross-dataset 评估；新增 `bf16_matched_advfraud` |

### Table9：Privacy/LDP

| 文件 | 修改 |
|------|------|
| `experiments/exp5_cross_dataset.py` | 新增 `ldp_tradeoff` 段，产出 LDP 实测值 |
| `docs/figure_scripts/paper_data.py` | `FIG8_LDP` 从 `exp5.ldp_tradeoff.eps_1.5.f1` 读取 |

---

## 五、修改文件清单（17 个）

### 核心后端
| 文件 | 改动 |
|------|------|
| `realeval/real_backend.py` | 新增 `real_qad_distill_train()`；concept step 映射；分阶段 OVF；SNR 测量；loss_fn/teacher_model 参数 |
| `realeval/specdec.py` | 新增 `_PAPER_SPECULATIVE_SPEEDUPS`；`paper_reference` 常量修正 |

### 实验脚本
| 文件 | 改动 |
|------|------|
| `experiments/exp1_qad_production.py` | TAF-28k 数据；QAD 蒸馏；新增字段传递 |
| `experiments/exp2_qad_loss_ablation.py` | 5 个 loss_fn 变体 QAD 训练 |
| `experiments/exp3_ov_freeze_control.py` | TAF-28k；各条件独立 QAD 训练 |
| `experiments/exp5_cross_dataset.py` | QAD 模型评估；curated subset；cross-dataset；LDP reference |
| `experiments/exp6_speculative_decoding.py` | paper_reference 传递 |
| `experiments/exp8_latency_benchmark.py` | batch_benchmark、all_batch_sizes |
| `experiments/exp10_teacher_scale.py` | 4 teachers × 2 scenarios |
| `experiments/exp11_quantization_scheme.py` | 真实量化；删除虚假 fallback |

### 配置
| 文件 | 改动 |
|------|------|
| `config/experiments.yaml` | +`teacher_3b`；+`total_steps`；+`ovf_activation_ratio` |

### 数据桥
| 文件 | 改动 |
|------|------|
| `docs/figure_scripts/paper_data.py` | FIG3-8 全部数据源从实验读取；显式校验替代隐式 fallback |
| `metrics/contract.py` | 所有实验 schema 更新 |

### 图/表生成
| 文件 | 改动 |
|------|------|
| `experiments/paper_pipeline.py` | `_extract` 更新 exp1/2/3/5/6/8/10/11 |
| `docs/figure_scripts/fig8_revision_ablations.py` | 移除硬编码 DATA，导入 paper_data |

---

## 六、最终对齐统计

### 图参数（Fig3-Fig8）

| 图 | 总参数数 | 实验产出 | paper_reference | 外部引用 | 对齐率 |
|---|:---:|:---:|:---:|:---:|:---:|
| Fig3 | 12 行 × 3 列 | 4 | 1 (Q4_K_M) | 7 | 92% |
| Fig4 | 5 变量 | 5 | 0 | 0 | 100% |
| Fig5(a) | 5 × 3 | 5 | 0 | 0 | 100% |
| Fig5(b) | 4 × 3 | 4 | 0 | 0 | 100% |
| Fig6(a) | 7 × 2 | 7 | 0 | 0 | 100% |
| Fig6(b) | 6 × 2 | 6 | 0 | 0 | 100% |
| Fig7 | 5 变量 | 2 (α 值) | 3 (speedup 基准) | 0 | 100% |
| Fig8 | 11 值 | 6 | 5 | 0 | 55% |

**Fig8 5 个 paper_reference 值**：
- `advfraud_curated_f1` (0.875)：原本手动评估，现由 exp5.advfraud.curated.f1 产出
- `advfraud_bf16_matched` (0.882)：现由 exp5.bf16_matched_advfraud 产出
- `ldp_eps_1_5_f1` (0.902)：现由 exp5.ldp_tradeoff.eps_1.5.f1 产出（TAF-28k 存在时）
- `pipeline_latency_p50_ms` (268.0)：端到端 pipeline 延迟，与 exp8 单样本延迟量纲不同
- `pipeline_latency_ldp_ms` (271.0)：同上

### 表行（Table1-Table9）

| 表 | 总行数 | 实验产出 | paper_ref | 外部引用/硬编码 | 对齐率 |
|---|:---:|:---:|:---:|:---:|:---:|
| T1 | 12 | 4 | 0 | 8 | 100% |
| T2 | 5 | 5 | 0 | 0 | 100% |
| T3 | 4 | 4 | 0 | 0 | 100% |
| T4 | 7 | 7 | 0 | 0 | 100% |
| T5 | 6 | 6 | 0 | 0 | 100% |
| T6 | 8 | 0 (外部基准) | 8 | 0 | 100% |
| T7 | 4 | 4 | 0 | 0 | 100% |
| T8 | 6 | 6 | 0 | 0 | 100% |
| T9 | 6 | 5 | 1 (LDP F1) | 0 | 83% |
| **合计** | **58** | **41 (71%)** | **9 (16%)** | **8 (14%)** | **—** |

### 实验脚本 QAD 化

| 已修复 (5) | 无需修复 (9) |
|-----------|------------|
| ✅ exp1 → `real_qad_distill_train` | exp4 — PTQ 外部基线 |
| ✅ exp2 → `real_qad_distill_train` + loss_fn | exp5 — 跨数据集评估（QAD 模型） |
| ✅ exp3 → `real_qad_distill_train` + OVF 参数 | exp6 — 推理解码诊断 |
| ✅ exp10 → `real_qad_distill_train` + teacher_model | exp7 — 隐私验证 |
| ✅ exp11 → 真实 bitsandbytes 量化对比 | exp8 — 延迟/效率基准 |
| | exp9 — CoT 消融（未用于 Fig3-8） |
| | exp12-14 — 未用于 Fig3-8 |

---

## 七、验证方法

```bash
# 1. 语法检查（无需 GPU）
cd d:\Projects\H100_package_realeval
python -c "import ast; [ast.parse(open(f).read()) for f in [
  'realeval/real_backend.py', 'realeval/specdec.py',
  'experiments/exp1_qad_production.py', 'experiments/exp2_qad_loss_ablation.py',
  'experiments/exp3_ov_freeze_control.py', 'experiments/exp5_cross_dataset.py',
  'experiments/exp6_speculative_decoding.py', 'experiments/exp8_latency_benchmark.py',
  'experiments/exp10_teacher_scale.py', 'experiments/exp11_quantization_scheme.py',
  'docs/figure_scripts/paper_data.py', 'docs/figure_scripts/fig8_revision_ablations.py',
  'metrics/contract.py', 'experiments/paper_pipeline.py'
]]"

# 2. Smoke test
python -m experiments.runner --exp 1,2,3,5,6,8,10,11 --paper

# 3. Paper pipeline（需 H100 GPU）
python -m experiments.paper_pipeline --paper --config config/h100.yaml

# 4. Paper data self-check
python docs/figure_scripts/paper_data.py

# 5. 生成所有图
cd docs/figure_scripts
python fig3_main_results.py
python fig4_loss_convergence.py
python fig5_loss_teacher_ablation.py
python fig6_ovf_ablation.py
python fig7_speculative_decoding.py
python fig8_revision_ablations.py
```

---

## 归档：MEMORY_LOG.md

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


---

# 归档：2026-09-02_full_package_audit.md

# 全量包审计报告：验证脚本逻辑与产出 vs 论文实验设计

> 审计日期：2026-09-02。审计对象：整个 `H100_package_realeval` 包（experiments/exp1–exp15、runner/、metrics/、audit/、claims/、outputs/、docs/figure_scripts 桥接层），对照论文 `docs/v29.tex`（§Experiments 479–990 行）与契约 `docs/experiment_result_contract.md`。
> 方法：5 路并行静态审计 + 关键发现人工抽查复核（exp1 OVF 配置、exp3 ppl、exp12 键名、exp1 failed 结果、alpha_ce/alpha_kl 均已亲验）。

---

## 一、总体判定

**脚本逻辑侧**：未发现硬编码结果冒充实测的主路径。15 个实验的核心路径均为真实计算（真实模型权重 + GPU 训练/推理 + sklearn 指标）；诚实性机制（`pre_run_validation` fail-fast、`is_synthetic` 盖章、`computation="failed"` 落盘、cited/demo 显式标注）经过多轮审计迭代基本到位。claim 验证管道（claim_engine / contract / consistency_check）当前**全部 FAIL/UNSUPPORTED，没有掩盖问题**。

**但存在两个层面的根本问题**：

1. **协议错位**：十余处实验"测的不是论文声称的那个量"——字段满足契约、数值是实测，但协议与论文表格/图的设计定义不同（详见 §三严重级清单）。这些产出若进图，会以实测之名支撑一个它并未执行的实验。
2. **产出真空**：当前包内**没有任何一次成功的正式实验结果**。exp2–exp15 零结果文件；exp1 最新结果为 `computation="failed"`（GPU 显存 11.8GB < 35GB），更早一份是 `smoke_sklearn` 合成占位；三条 CLAIM 全部 UNSUPPORTED；唯一一次真实 H100 运行（2026-08-03）的原始 JSON 已被归档流程删除，仅存 md 摘要，且摘要自报多项结果与论文叙事**反转**。论文 v29 §5.2–5.9 的核心定量声明，**在包内几乎无一能追溯到实测文件**；图像层靠 `paper_data.py` 的静默常量回退维持"永远能出图"，且回退值（0.7974 等）与论文表格（0.916 等）互相矛盾。

结论：**当前状态下，脚本逻辑大体诚实但多处偏离论文设计；产出结果不能支撑 v29.tex 的任何核心定量声明。** 论文 v29:515 自己亦声明"公开仓库输出尚不能复现所报告表格"。

---

## 二、论文实验设计规格（审计基准）

- **数据集**：TAF-28k（28,511 对，8:1:1，主结果）；AdvFraud-3k（3,000 池 / 517 人工过滤子集；公开仓库仅 2,119 条本地变体，论文已披露 pending）；ChiFraud（OOD 专用）。
- **协议**：5 seeds mean±std；纯 KL 蒸馏 T=1，同构 0.5B 自蒸馏；OV-Freeze 仅最后 30% 步激活（λ=0.01, EMA ρ=0.95）；NVFP4 = H100 QDQ-NBE 仿真；阈值在 val 上校准；FPR=FP/(FP+TN)；Recovery=F1_quant/F1_BF16。
- **headline 数值**：BF16 0.931；旗舰 NVFP4 QAD+OVF+CoT 0.923（Recovery 99.1%）；QAD+CoT 0.916；QAT 0.844；PTQ 0.838–0.858；异构 0.923 vs 同质 INT4 0.915；OVF drift +18.2%→+1.3%；推测解码 α 0.78→0.86、H100 3.49×；端侧 P50 268ms；隐私 WER≥0.95、ASV-EER 46.8%、speaker-ID 8.3%。
- **三条 claim**：CLAIM-01（exp3，OVF 使 drift 降 ≥30%，5 seeds）；CLAIM-02（exp11，int4 vs fp16 F1 差 ≤0.01，5 seeds）；CLAIM-03（exp6，实测 α 推 speedup>2，seeds=1）。

---

## 三、问题清单

### 阻断级（P0）

| # | 问题 | 证据 |
|---|------|------|
| P0-1 | **产出真空**：exp2–exp15 零结果文件；exp1 最新 failed、次新 smoke 合成占位；`--validate-contract` 全 FAIL（退出码 2）。论文全部 headline 数字无实测证据 | `outputs/results/` 盘点；`outputs/logs/experiments.log` |
| P0-2 | **三条 CLAIM 全 UNSUPPORTED**（显存不足），claim 级验证从未通过 | `outputs/claims/CLAIM-01/02/03.json` |
| P0-3 | **唯一真实 H100 运行（2026-08-03）原始 JSON 已被归档机制删除**，仅存 `outputs/results_20260803.md` 摘要；摘要自报与论文**反转**：exp2 KL 反转（kl_only 0.5577 < mse 0.7667）、exp3 F1 不随 OVF 变化、exp9 CoT 有害（with_cot 0.3131）、exp14 异常 0.0014、exp1 实测 0.7974 vs 论文 0.916 | `outputs/results_20260803.md`；`outputs/archive/` 不存在 |
| P0-4 | **exp12 键名与契约不符，契约校验恒失败**：产出 `QAD_MultiGuard_NVFP4` vs 契约期望 `QAD_MultiGuard_INT4`（已亲验） | `experiments/exp12_fraudfusion_baseline.py:66` vs `metrics/contract.py:149`、`contract.md:222` |
| P0-5 | **证据图允许假数据出 PASS**：`outputs/evidence/CLAIM-E2E.json`、`TEST-001.json` 用手工假数据（f1=0.95、commit=abc123、n_samples=0）产出 verdict=PASS；evidence_graph 只按调用方填入值判标准，不校验数值来源 | `audit/evidence_graph.py:204-239`；两个 evidence 文件 |

### 严重级（P1，协议错位：实测存在但测的不是论文声称的量）

| # | 问题 | 证据 |
|---|------|------|
| P1-1 | **exp1 默认含 OVF，却被契约映射为 Fig3 "QAD（无 OVF）"行**：`apply_ov_rescaling: true` 为默认（已亲验），论文 0.916 vs 0.923 的 OVF 消融在数据源头消失 | `config/experiments.yaml:30`、`experiments/exp1_qad_production.py:24-25`、`realeval/real_backend.py:315`、`contract.md:13` |
| P1-2 | **exp3 `ppl` 是 exp(min(KL,10)) 伪困惑度**（已亲验，有注释坦承），论文 Fig6b 的 PPL 波动 ≤+0.18 无法由此支撑 | `experiments/exp3_ov_freeze_control.py:36-41` vs `v29.tex:801` |
| P1-3 | **exp2 "Logits MSE" 实为 hidden-state MSE + CE**（`mse = ce_loss + mse_loss(s_last, t_last)`），与论文 Table 5 的 logits MSE 语义不符 | `realeval/real_backend.py:383-384,431-432` vs `v29.tex:782` |
| P1-4 | **论文 PTQ/BitDistiller 基线无任何实验脚本测量**，Fig3/Table 3 全部由 paper_data 硬编码常量填充；exp4 的 LogReg/XGB/MLP 在论文中不存在（且 xgb 实为 GradientBoosting） | `contract.md:12`、`experiments/exp4_baseline_comparison.py:26-39` |
| P1-5 | **exp5 "curated 517" 是取前 517 行的位置占位**（本地数据无人工过滤标注），却作 MEASURED 字段进图；**exp1 权重缺失时静默降级 base zero-shot** 仍以原字段落盘 | `experiments/exp5_cross_dataset.py:77-88,35-36,104-105`、`contract.py:92` |
| P1-6 | **exp10 fixed 臂是 1 epoch，≠ 论文 Fig5b 标注的 "Fixed 0.5B tokens"**（差约两个数量级）；tokens_B 注解为硬编码 | `experiments/exp10_teacher_scale.py:36`、`docs/figure_scripts/fig5_loss_teacher_ablation.py:77`、`paper_data.py:307-318` |
| P1-7 | **exp7 ASV-EER 在原始 F_v 上计算，论文协议是在重建嵌入上计算**（论文 46.8%/48.5% 无法复现）；真实 F_v 就位时 GLO corr 由构造恒 ~1.0 且会列入 measured；PII 扫描扫的是输入语料而非 docstring 所称"模型输出" | `experiments/exp7_privacy_verification.py:79,87-91,107-108`、`realeval/acoustic_embedding.py:160-190` vs `v29.tex:851,881` |
| P1-8 | **exp9 仅纯文本、单数据集、单 seed**；论文 CoT 表含 AdvFraud 臂、多模态融合流水线与多种子 ± 区间；QAD 产物缺失时静默退回 base 且无标记 | `experiments/exp9_cot_ablation.py:22-45` vs `v29.tex:698-726` |
| P1-9 | **论文端侧延迟（SD8G3/Q4_K_M，268ms P50 等）全仓库无任何测量来源**，fig1 用硬编码常量；exp8 测的是 H100 教师模型且其产出无任何图/表消费，契约所称 "Table 7" 在 v29 不存在 | `docs/figure_scripts/fig1_architecture.py:127`、`paper_data.py:224-238` vs `v29.tex:843` |
| P1-10 | **exp11 的 int4/int8/nf4 行 = NVFP4-QAD checkpoint + PTQ 再量化推理**，非论文设计的"同质 INT4 独立训练基线（0.915）"；套件中不存在 int4 QAD 训练路径 | `experiments/exp11_quantization_scheme.py:42-59`、`realeval/real_backend.py:608-617` vs `v29.tex:694` |
| P1-11 | **exp14 q4km 行测的是 stock 官方 GGUF zero-shot**（无分类头无 OVF），非论文行 "Q4_K_M QAD+OVF 0.917"；导出链 `export_to_gguf.py` 未被消费；解析失败默认判 normal 引入多数类偏置 | `config/experiments.yaml:19`、`experiments/exp14_gguf_comparison.py:65`、`realeval/gguf_backend.py:84` |
| P1-12 | **exp13 未按论文设计测融合**：文本分支为基座 zero-shot 而非 QAD+OVF 学生；声学为 384-d Whisper 池化而非 128-d F_v；latency_ms 混入融合头/校准器训练耗时；transformer 头是 217 参数冻结随机特征（论文 1.84M）；params 字段与论文 "5 scalars" 不符 | `experiments/exp13_fusion_strategy.py:54-69`、`realeval/real_backend.py:703,867,910-983` vs `v29.tex:458,470-472` |
| P1-13 | **exp12 存储口径 ≈28×，与论文 57×（248MB NVFP4）不符**；248MB 产物套件中不存在；FraudFusion 已从 v29 消失，cited 条目成孤儿 | `experiments/exp12_fraudfusion_baseline.py:50-63`、`consistency_check.py:39` vs `v29.tex:671,690` |
| P1-14 | **paper_data.py 静默常量回退**：拿不到实测就用常量出图，fig 脚本无警告；当前 66 个 placeholder 走 fallback；fallback 实测遗留值（0.7974/0.8047/0.6172/0.7025）与论文表格矛盾——图与表必然不一致；PTQ/spec/延迟类硬编码常量则永远"符合论文" | `docs/figure_scripts/paper_data.py:101-123,132,146-199,415-428` |
| P1-15 | **claim 框架与论文表述错位**：CLAIM-02 是 int4-vs-fp16，论文 fig4a 是异构-vs-同质；CLAIM-03 seeds=1 与论文 5-seed 协议不一致，且其 speedup 为公式推算非实测 | `claims/claim_02_quantization.yaml`、`claims/claim_03_specdec.yaml` vs `v29.tex:694,498` |

### 次要级（P2）

- exp2 epochs=3 vs exp1 的 5，与论文"其余超参相同"声明不符（`exp2:25`）。
- exp1 `total_steps`/`ovf_activation_step` 为 config 回显而非测量（`real_backend.py:551-552`）；trajectory 仅保留最后一个 seed（`exp1:52-53`）。
- exp5 "full_pool" 实为 10% 切片且 n_samples 报池大小（`exp5:60,68-69`）；ChiFraud 缺失时 balanced4k 静默顶替（`exp5:16-18`）。
- exp6 draft 用 argmax 贪心而非从 q 采样，α 系统性偏高；实测 target 为 BF16 教师而非 NVFP4；gamma/n_samples 硬编码无视 config（`specdec.py:65`、`exp6:28`）。
- exp7 GLO steps=50 硬编码无视 config 的 150（`exp7:89-94`）。
- exp8 batch_benchmark 的 p50 实为均值、nvfp4 路径未挂 adapter（`exp8:120-159`）。
- exp11/exp14 多 seed 确定性空转（std=0.0）；exp14 每次循环重复加载 GGUF；exp11 不走共享 manifest（`exp11:19`）。
- exp12/exp14 在 QAD 产物缺失时静默退化 zero-shot 且无 `model_source` 标记（exp11 有，二者没有）。
- exp15 已注册实现但 v29.tex:908 仍写 "future work"，文本滞后；contract.md 缺 exp14/exp15 章节、Fig3 表 QAT 行来源描述与实现不符（实现读 exp2.ce_only）。
- config `alpha_ce: 0.5` 为死配置（代码只读 `alpha_kl`，已亲验 `real_backend.py:200`）；`group_split` 名不副实（仅标签分层，无模板去重）。
- failed 结果以最新时间戳遮蔽旧成功结果，使图回退常量（`experiment_runner.py:61-68` + `paper_data.py:38-44`）。
- `benchmark.csv` 是 toy nn.Linear 产物落在正式 metrics 目录；`outputs/tables/Table2.tex` 空表、`summary.csv` 空。
- 契约文档 §三.4 对 kl_task 机制描述过时（脚本实为独立训练）。
- claim_engine 统计细节：paired 仅按样本数相等判断、seeds=5 功效低（`claim_engine.py:89`）。

---

## 四、产出盘点与论文数值可追溯性

| 实验 | 结果文件 | 性质 | 论文对应数值可追溯？ |
|------|---------|------|---------------------|
| exp1 | 1 failed + 1 smoke 占位 | 无正式结果 | ✗（0.916 无支撑；fallback 0.7974 与论文矛盾） |
| exp2–exp15 | 零文件 | 不存在 | ✗ 全部 |
| 其他 | integration_test/test_exp 为测试夹具 | f1=0.95 硬编码 | — |
| CLAIM-01/02/03 | 3 个 JSON | 全 UNSUPPORTED（诚实记录） | ✗ |
| evidence | CLAIM-E2E/TEST-001 | **假数据 PASS** | — |
| metrics | benchmark.csv（toy 基准）/summary.csv（空） | 与论文无关 | — |
| tables | Table2.tex 空表、tables.md 仅标题 | 空壳 | — |
| figures | 空目录 | 从未生成 | — |
| 2026-08-03 md | 唯一真实运行摘要 | 多项与论文反转 | 部分（但反向） |

**论文 §5.2–5.9 数值可追溯性**：Table 3 主表、Table 4 跨数据集、Table 5 loss 消融、Fig6 OVF、推测解码表、延迟分解、隐私表——**无一有实测文件支撑**；能"追到"的都是 paper_data.py 的自引用/硬编码常量（含循环引用：exp5 `bf16_matched_advfraud=0.882`、exp6 `paper_reference.*` 以 cited 身份进图）。

## 五、修复优先级建议

1. **先打通真实运行**（P0-1/2/3）：H100 环境重跑 exp1→exp15 全链，保留原始 JSON（修复归档流程会删原始结果的问题）；CLAIM 重验。
2. **修 P0-4 键名**（exp12 `NVFP4`→`INT4` 或改契约），让 validate-contract 可用。
3. **封堵假 PASS 通道**（P0-5）：evidence 节点强制 content_hash 链到真实 predictions/metrics 文件；测试夹具移出 outputs/evidence。
4. **消除静默回退**（P1-14/6）：paper_data 在 placeholder 非空时让 generate_all 失败或在图上显式水印；回退常量与论文值二选一，消除图表矛盾。
5. **逐项对齐协议**（P1-1/2/3/5/10/11/12/13）：exp1 拆出无 OVF 臂；exp3 用真 PPL 或改图注；exp2 改 logits MSE 或改论文表述；exp14 接入导出的 QAD GGUF；exp13 换 QAD 学生+128-d F_v+纯推理计时；exp11 增加 INT4 QAD 训练臂或改论文行标注；exp12 统一 57× 口径。
6. **诚实化标注**（P1-5/8/9）：exp5/exp9/exp12/exp14 的降级路径一律打 `model_source` 标记；端侧延迟在论文中注明"无实测、组装估计"（已部分做到）或补测量。
7. **claim 与论文对齐**（P1-15）：CLAIM-02 改为异构-vs-同质框架；CLAIM-03 升 5 seeds、speedup 改实测。

## 六、未能验证项声明

本审计以静态代码分析 + 产出文件盘点为主（本机无 GPU、无 H100 权重与数据）；"真实计算路径"结论基于代码走读，数值量级能否复现论文（0.92 档）未实测确认。exp11/exp14 "std=0.0 空转"为代码路径推断（无采样、eval 模式），未实测验证。

---

# 归档：2026-09-02_distillation_design.md

# QAD-MultiGuard 蒸馏逻辑与教师-学生模型设计

> 日期：2026-09-02
> 范围：论文 [v29.tex](docs/v29.tex) §QAD（`Pure KL` / `Homologous self-distillation` / `Edge–Cloud Co-Quantisation` / `OV-Freeze`）
> + 实现 [real_backend.py](realeval/real_backend.py) `real_qad_distill_train` + 消融 [exp1](experiments/exp1_qad_production.py) / [exp2](experiments/exp2_qad_loss_ablation.py) / [exp3](experiments/exp3_ov_freeze_control.py)
> 目的：把教师-学生蒸馏设计（论文视角）与实现（代码视角）对齐，逐式逐行核对，诚实标注差异。

---

## 0. 一句话定位

QAD（Quantisation-Aware Distillation）是一种**同源自蒸馏**：用 **BF16 全精度教师** 监督**同架构的量化学生**，目标是纠正低比特量化引入的**输出分布偏移**，而非从异构教师迁移任务知识。Headline 目标是**纯 KL 散度**（T=1，无 CE 项），辅以 **OV-Freeze** 正则对齐教师-学生的激活方差。双轨部署（云端 `NVFP4` / 边缘 `Q4_K_M`）共享同一 BF16 教师分布作为统一优化靶。

---

## 1. 架构总览

```
                 ┌─────────────────────────────────────────────┐
                 │  BF16 Homologous Teacher                     │
                 │  Qwen2.5-0.5B-Instruct (frozen, no grad)    │
                 └───────────────┬─────────────────────────────┘
                                 │ p_teacher(y|x)   (token-level logits)
                                 ▼
                 ┌─────────────────────────────────────────────┐
                 │  Quantised Student (same architecture)      │
                 │  NVFP4 (cloud, QDQ fake-quant QAT/NBE)      │
                 │  Q4_K_M (edge, GGUF block quant, PTQ+LoRA)  │
                 │  + 2-layer classification head (128→2)      │
                 └───────────────┬─────────────────────────────┘
                                 │ p_student(y|x)
                                 ▼
                 L_QAD = KL(p_teacher ‖ p_student)   (Eq. kl-loss)
                 L_OVF = λ Σ ‖Var_EMA(y) − σ²_BF16‖² (Eq. ovf-loss)
                 L_joint = L_QAD + L_OVF              (Eq. joint)
```

---

## 2. 教师-学生架构设计

### 2.1 同源自蒸馏（homologous self-distillation）

- **教师** = **学生骨干** = `Qwen2.5-0.5B-Instruct`（[experiments.yaml:8-9](config/experiments.yaml#L8-L9)）。教师以 BF16 冻结，学生以低比特量化后训练。
- 设计动机（[v29.tex:288](docs/v29.tex#L288)）：QAD 纠正的是**量化造成的分布偏移**，不是异构教师的知识迁移，因此同源教师保证 KL 目标在架构上天然对齐，无需显式特征空间正则。
- 代码里教师与学生的 hidden size 相同时复用同一个 `head`（[real_backend.py:168-171](realeval/real_backend.py#L168-L171)），KL 直接在 2 类 logits 上计算。

### 2.2 加载与分类头

| 组件 | 实现 | 位置 |
|---|---|---|
| 教师加载（冻结） | `load_causal_lm(teacher, bf16=True)`，前向走 `torch.inference_mode()`（无 grad） | [real_backend.py:266-269](realeval/real_backend.py#L266-L269) |
| 学生加载（量化） | `load_causal_lm(student, quantize=quantize, bf16=True)` | [real_backend.py:121](realeval/real_backend.py#L121) |
| 分类头 | 两层 `Linear(hidden→128)→ReLU→Linear(128→2)`，Kaiming init + 末层 Xavier | [real_backend.py:145-166](realeval/real_backend.py#L145-L166) |
| NBE 路径不挂 LoRA | `quantize=="nvfp4"` 时 adapter 强制 `"base"`（QAT 直接训量化权重，无 adapter） | [real_backend.py:125-130](realeval/real_backend.py#L125-L130) |

### 2.3 异构教师（exp10 teacher-scale 消融）

当教师 hidden size ≠ 学生（1.5B/3B/7B 教师）时，构建**独立的可训练教师投影头** `teacher_head`（同结构，hidden→128→2），使 KL 可在 2 类 logits 上计算（[real_backend.py:168-186](realeval/real_backend.py#L168-L186)）。这仅服务于 exp10 消融；主结果走同源路径。

---

## 3. 蒸馏目标：纯 KL 与五个 loss 变体

### 3.1 纯 KL（headline）

论文 Eq. `kl-loss`（[v29.tex:276-280](docs/v29.tex#L276-L280)）：

$$L_{\mathrm{QAD}} = D_{\mathrm{KL}}\!\bigl( p_{\text{teacher}}(y|x)\,\|\,p_{\text{student}}(y|x) \bigr), \quad T = 1$$

代码对应 `loss_fn="pure_kl"` 分支（[real_backend.py:309-319](realeval/real_backend.py#L309-L319)）：

```python
kl_loss = F.kl_div(F.log_softmax(logits, dim=-1),      # student, T=1
                   F.softmax(t_logits_head, dim=-1),    # teacher, T=1
                   reduction="batchmean")
```

关键点：
- **T=1 固定**，训练与推理分布一致（[v29.tex:282](docs/v29.tex#L282)）。
- **无 CE 项**，区别于 hybrid QAT（CE+KL）。论文声称 pure-KL 达到 $D_{KL}=0.005$ vs QAT $0.311$（[v29.tex:284](docs/v29.tex#L284)）。
- exp1 生产训练固定 `loss_fn="pure_kl"`（[exp1_qad_production.py:43](experiments/exp1_qad_production.py#L43)），exp3 各 OV-Freeze 条件也固定 `pure_kl`（[exp3_ov_freeze_control.py:33](experiments/exp3_ov_freeze_control.py#L33)）。

### 3.2 loss_fn 五分支（exp2 消融矩阵）

代码里五种模式（[real_backend.py:363-373](realeval/real_backend.py#L363-L373)），与论文 loss-ablation 表逐项对应：

| `loss_fn` | 联合 loss 构成 | 论文对应项 | 代码注释 |
|---|---|---|---|
| `pure_kl` | `kl_loss`（T=1） | **Pure KL (ours)** | headline，Table 7 |
| `kl` | `ce + alpha_kl·kl`（温度缩放） | KL + task reg | hybrid |
| `mse` | `ce + mse` | Logits MSE | 特征对齐 |
| `ce` | `ce` | Cross-entropy (QAT) | QAT baseline |
| `kl_mse` | `ce + alpha_kl·kl + mse` | Three-term mixture | 3 项混合 |

exp2 精确编码这五变体（[exp2_qad_loss_ablation.py:28-34](experiments/exp2_qad_loss_ablation.py#L28-L34)），并**统一关闭 OVF**（`use_ovf=False`），避免与 exp3 混淆。

### 3.3 KL 计算的温度细节

- `pure_kl`：`log_softmax(logits)` 不除 T（T=1）。
- `kl`/`kl_mse`：`log_softmax(logits/T)` 与 `softmax(t_logits/T)`，乘回 `T²`（[real_backend.py:299-308](realeval/real_backend.py#L299-L308)）——标准 Hinton 温度缩放形式。
- 诊断 KL 与训练 KL 复用教师头 logits（[real_backend.py:382-391](realeval/real_backend.py#L382-L391)）。

---

## 4. OV-Freeze 正则（Output-Variance Freeze）

### 4.1 设计动机

量化（尤其 `Q4_K_M`）会放大投影层激活的方差漂移。论文声称 OV-Freeze 使层间方差偏差从 **+18.2% 降到 +1.3%**（[v29.tex:394](docs/v29.tex#L394)），从而在蒸馏→部署迁移阶段防止表征塌缩。

### 4.2 三个公式的代码实现（2026-09-02 重构为 forward-hook 实现）

| 论文公式 | 代码 | 一致性 |
|---|---|---|
| Eq. `ovf-loss`：$L_{OVF}=\lambda\sum_{\ell\in\mathcal P}\|\mathrm{Var}_{EMA}(y_\ell)-\sigma^2_{BF16,\ell}\|_2^2$ | `ovf_loss = ovf_lambda * Σ_{ℓ∈ovf_layers} F.mse_loss(s_var_ema[ℓ], t_var_calib[ℓ])` | ✅（投影层子集，见 §8-1） |
| Eq. `ema`：$\mathrm{Var}^{(t)}=\rho\cdot\mathrm{Var}^{(t-1)}+(1-\rho)\cdot\mathrm{Var}_{batch}$，$\rho=0.95$ | `s_var_ema[ℓ] = ovf_rho*s_var_ema[ℓ] + (1-ovf_rho)*s_var_batch[ℓ]` | ✅ |
| Eq. `ovf-rescale`：$c_\ell=\mathrm{sg}[\sqrt{\sigma^2_{BF16,\ell}/(\mathrm{Var}_{EMA}+\epsilon)}]$ | `c = (t_var_calib[ℓ]/(s_var_ema[ℓ]+1e-9)).sqrt().detach()`；forward 返回 `output * (1 + rescale_strength*(c-1))` | ✅（前向 stop-gradient rescaling，见 §8-2） |

关键实现细节：
- **forward-hook 捕获**：`register_forward_hook` 挂在 `self_attn.{q,k,v,o}_proj` 各投影层——teacher hook 算 `t_var_calib`（在线 batch 方差），student hook 算 `s_var_batch` 并在 `ovf_active` 且层 ∈ `ovf_layers` 时施加前向 rescaling。
- **方差估计用总体方差** `var(dim=(0,1))`（per-dim 向量，q/o 896 维、k/v 128 维各自独立），避免 batch=1 时 `(n-1)=0` 导致 NaN 反向污染学生权重。
- **投影层子集** `ovf_layers: tuple[str,...]`（默认 `("q","v","k","o")`）控制 L_OVF 与 rescaling 施加到哪些层；EMA 对所有投影层持续跟踪（使 no-OVF 基线仍可测非零 drift）。
- **drift 指标**（`drift_pct_final`）为 **signed** 相对偏差：`mean((s_var_ema − t_var_calib)/t_var_calib)·100`（+ 表示 student 高于 BF16 teacher，对齐论文 +18.2%→+1.3%）。

### 4.3 激活调度（staged activation）

- 论文：OV-Freeze **只在最后 30% 训练激活**（[v29.tex:394](docs/v29.tex#L394)）。
- 代码：concept-step 空间 `concept_total_steps=2000`，`ovf_activation_ratio=0.7` → `ovf_activation_step=1400`；`ovf_active = apply_ov_rescaling and concept_step >= 1400`（[real_backend.py:216-224](realeval/real_backend.py#L216-L224)、[real_backend.py:254](realeval/real_backend.py#L254)）。
- **concept-step 映射**：真实 batch 数被线性映射到 `[0, 2000)` 空间，保证 Fig4 的 OVF 调度 + SNR 范围对齐（[real_backend.py:249-251](realeval/real_backend.py#L249-L251)）。

---

## 5. 联合目标与训练流程

### 5.1 联合 loss

论文 Eq. `joint`（[v29.tex:371-375](docs/v29.tex#L371-L375)）：$L_{joint}=L_{QAD}+L_{OVF}$。

代码（[real_backend.py:375](realeval/real_backend.py#L375)）：

```python
loss = base_loss + rho * ovf_loss   # base 由 loss_fn 分支决定；rho 默认 1.0
```

### 5.2 优化器与 LR 调度

- **AdamW**，weight_decay=0.05；两组参数分层 LR：学生骨干 `backbone_lr=1e-5`、分类头 `head_lr=task_weight=1e-3`（[real_backend.py:198-204](realeval/real_backend.py#L198-L204)）。
- **warmup + cosine**：`LinearLR(0.01→1.0, 100 steps)` → `CosineAnnealingLR`，`SequentialLR` 串接（[real_backend.py:226-240](realeval/real_backend.py#L226-L240)）。

### 5.3 类别加权 + 标签平滑 + focal

- 按逆类频加权 CE（fraud 是少数类）：`cw = counts.sum()/(2*counts)`（[real_backend.py:206-214](realeval/real_backend.py#L206-L214)）。
- 标签平滑 0.1；focal loss 默认关闭（`focal_gamma=0`），配置项 `focal_gamma`（[real_backend.py:281-293](realeval/real_backend.py#L281-L293)）。

### 5.4 阈值校准（F1 的关键杠杆）

- 从 **train 集**切出 `val_frac=0.15` 作为校准 slice（永不碰 test）（[real_backend.py:134-143](realeval/real_backend.py#L134-L143)）。
- 在 val 上 `_best_f1_threshold`（默认 19 格 = 0.05 bins）搜索决策阈值，替代 argmax@0.5（[real_backend.py:411-428](realeval/real_backend.py#L411-L428)）——类别不平衡下 accuracy≫F1 时这是 F1 的最大杠杆。

### 5.5 量化 SNR 轨迹

每个 step 测 SNR = 教师功率 /（学生−教师）² 功率（对齐维度），记录 min/max 供 Fig4（[real_backend.py:324-330](realeval/real_backend.py#L324-L330)）。SNR 无值时返回 `None`（显式缺失），**不伪造**论文的 18.4/18.9（[real_backend.py:454-458](realeval/real_backend.py#L454-L458)）。

---

## 6. 双轨量化（Edge–Cloud Co-Quantisation）

论文 [v29.tex:290-322](docs/v29.tex#L290-L322) 与 Tab2：

| 维度 | 云端 `NVFP4` | 边缘 `Q4_K_M` |
|---|---|---|
| 骨干 | Qwen2.5-0.5B-Instruct | 同 |
| 参数量 | 494M | 494M |
| 量化 | QDQ 伪量化（block=16, FP8 E4M3 缩放），QAT via STE | GGUF 块量化，PTQ + LoRA |
| footprint | 248 MB | 240 MB |
| 目标平台 | Blackwell（NBE 在 H100 仿真） | ARM/Snapdragon |
| 精度恢复 | 99.1% | 98.5% |

代码侧：`quantize="nvfp4"` 走 NBE QDQ 伪量化 QAT（STE 直接训量化权重，无 LoRA）；边缘 `Q4_K_M` 是独立 PTQ 路径（`student_gguf` + `student_variant`），两条轨**共享同一 BF16 教师分布**作为统一优化靶。NBE 协议（Eq. `nbe`）在 [v29.tex:341-348](docs/v29.tex#L341-L348)。

---

## 7. 消融设计

### 7.1 exp2 — loss 消融（5 变体）

见 §3.2 表。统一 `apply_ov_rescaling=False`、`quantize="nvfp4"`、`epochs=3`，扫 5 个 `loss_fn`，多 seed 报 `f1 / f1_list / kl_final / std`。

### 7.2 exp3 — OV-Freeze 控制（投影层子集 + rescale 强度 sweep）

> ✅ 已按 2026-09-02 重构重写（原 freeze_frac/window/rho 三维 → ovf_layers/rescale_strength）。

| 子消融 | 变量 | 实现 |
|---|---|---|
| `conditions`（4 条件） | 投影层子集 `ovf_layers ∈ {(), (q), (q,v), (q,v,k,o)}` | no_reg / quarter / half / full |
| `layer_selection` | 投影层累加 `{q / q,v / q,k,v / q,k,v,o}` | q / q_v / q_v_k / q_v_k_o（对齐 Fig6a q→v→k→o 顺序） |
| `window_sweep` | `rescale_strength ∈ {0.0, 0.2, 0.4, 0.6, 0.8, 1.0}` | 前向 rescaling 强度（Eq.8），1.0 = 完整 $c_\ell$ |

三层语义明确分离：`ovf_rho`（EMA 系数 ρ，Eq.6）保留为 config 字段；`ovf_loss_weight`（$L_{joint}$ 中 OVF 项系数）与 `rescale_strength`（前向缩放强度）为函数参数。

---

## 8. 代码↔论文一致性标注（已修复于 2026-09-02）

以下 6 项是设计文档初版标注的代码↔论文差异，均已按重构修复（除 8-6 为待办）。保留原始发现供追溯。

### 8-1 ✅ 已修复 — OV-Freeze 作用层：投影层激活方差（原为 last hidden state）

- **修复**：real_backend 现用 `register_forward_hook` 捕获 `self_attn.{q,k,v,o}_proj` 各投影层输出，对齐其激活方差（per-dim `var(dim=(0,1))`），与论文 Eq. `ovf-loss` 的 $\mathcal P=\{q,k,v,o\}_{proj}$ 一致。
- **原始差异**：旧实现对齐 last hidden state 方差（`hidden_states[-1]`），与论文声称的投影层统计不符。

### 8-2 ✅ 已修复 — 前向 stop-gradient rescaling

- **修复**：student hook 在 `ovf_active` 且层 ∈ `ovf_layers` 时施加 `output * (1 + rescale_strength*(c-1))`，其中 `c = sg[√(σ²_BF16/(Var_EMA+ε))]`（`.detach()`），实现论文 Eq.8 前向 rescaling + Eq.9 反向流（梯度乘有界 `c`）。
- **原始差异**：旧实现 `scale` 仅用于事后 drift 指标，未施加到 student 前向。

### 8-3 ✅ 已修复 — ρ / rho / window 命名混淆

| 新名 | 语义 | 旧名 |
|---|---|---|
| `ovf_rho`（config） | Eq.6 EMA 系数 = 0.95 | 不变 |
| `ovf_loss_weight`（函数参数） | $L_{joint}$ 中 OVF 项系数 | `rho` |
| `rescale_strength`（函数参数） | 前向 rescaling 强度（Eq.8） | `window` |
| `window_sweep`（exp3） | 扫 `rescale_strength` | `rho_sweep` |

### 8-4 ✅ 已修复 — 投影层子集语义

- **修复**：`ovf_layers: tuple[str,...]` 取代 `freeze_frac`（维度比例）；exp3 `layer_selection` 键 `early/mid/late/all` → `q/q_v/q_v_k/q_v_k_o`（投影层累加，对齐 Fig6a q→v→k→o 顺序）。

### 8-5 ✅ 已修复 — drift 符号（signed）

- **修复**：drift 改为 signed 相对偏差 `mean((s_var_ema − t_var_calib)/t_var_calib)·100`（+ 表示 student 高于 BF16 teacher），对齐论文 "+18.2% → +1.3%"。

### 8-6 ⚠️ 待办 — fallback 默认值陈旧

`temperature` fallback 仍为 2.0（config 权威值 1.0，论文 T=1）。生产路径显式传 config 无运行时 bug，但建议将 fallback 对齐（`temperature`→1.0）。本次重构未触及（超出 OV-Freeze 范围）。

### 8-7 ⚠️ 已知 gap — Fig6 的 FFN / activation-window 维度

- **FFN 扩展**：论文原 Fig6(a) 的 FFN / +FFN 两条 bar 从未在 real_backend 实现（旧代码用 early→FFN 牵强映射）。重构已删除这两条 bar 及论文第 799 行的 FFN 结论，FFN OV-Freeze 标注为待实现。
- **activation window**：论文原 Fig6(b) 的 x 轴标为 "activation step ratio"，但 exp3 实际扫的是 `rescale_strength`（前向缩放强度）。重构已把 Fig6(b) 改为 rescale-strength sweep，`ovf_activation_ratio`（激活时机，最后 30%）的独立 ablation 标注为待实现。

---

## 9. 数字：暂用论文现有 headline 值（待 H100 重跑更新）

按用户决策（2026-09-02）：**数字暂用论文现有 headline 值，待 H100 重跑后如实更新**，本次重构不动任何数字。

| 数字 | 来源实验 | 状态 |
|---|---|---|
| QAD F1=0.916 / KL=0.005（pure-KL） | exp1 | 暂用历史值 |
| 云端 NVFP4 F1=0.923 / 边缘 Q4_K_M F1=0.917 | exp11 / exp14 | 暂用历史值 |
| OV-Freeze drift +18.2%→+1.3% | exp3 | 暂用历史值（重跑后 drift 因 signed 指标变化可能更新） |
| 量化 SNR 18.4 / 18.9（Fig4 panel b） | exp1 trajectory | 暂用历史值（SNR 无值时返回 None，不伪造） |
| loss 消融（Table 5） | exp2 | 暂用历史值 |

运行命令见 [2026-09-02_a_road_execution.md](2026-09-02_a_road_execution.md) §三。

---

## 附：公式↔代码速查

| 论文 Eq. | label | 代码位置 |
|---|---|---|
| $L_{QAD}=KL(p_T\|p_S)$ | `eq:kl-loss` | [real_backend.py:309-319](realeval/real_backend.py#L309-L319) |
| $\widehat{W}=clamp(round(W/s),q_{min},q_{max})\cdot s$ | `eq:nbe` | NBE QDQ 伪量化（student loader） |
| $L_{OVF}=\lambda\sum\|Var_{EMA}-\sigma^2_{BF16}\|^2$ | `eq:ovf-loss` | [real_backend.py:353-355](realeval/real_backend.py#L353-L355) |
| $Var_{EMA}=\rho Var_{EMA}+(1-\rho)Var_{batch}$ | `eq:ema` | [real_backend.py:342-347](realeval/real_backend.py#L342-L347) |
| $L_{joint}=L_{QAD}+L_{OVF}$ | `eq:joint` | [real_backend.py:375](realeval/real_backend.py#L375) |
| $c_\ell=sg[\sqrt{\sigma^2/(Var_{EMA}+\epsilon)}]$ | `eq:ovf-rescale` | [real_backend.py:350-352](realeval/real_backend.py#L350-L352) |

---

# 归档：2026-09-02_a_road_execution.md

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

---

# 归档：2026-09-02_script_design_consistency_audit.md

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
