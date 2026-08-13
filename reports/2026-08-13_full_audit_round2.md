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
