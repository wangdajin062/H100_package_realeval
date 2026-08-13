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

> 注：本报告为只读审计结论，未做任何修改。修复需另行确认范围后执行。
