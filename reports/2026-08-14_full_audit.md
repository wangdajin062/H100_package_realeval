# H100_package_realeval 全量审计报告（第三轮：复核 round1/round2 修复 + 残留发现 + 诚实标注修复）

> 日期：2026-08-14
> 基线：HEAD `6cbc498`（该 commit 已将第二轮 `reports/2026-08-13_full_audit_round2.md` 第八节所列的工作树修复全部落盘提交），审计开始时工作树干净
> 方法：全包字节编译 + 轻量模块导入 + 安装 CPU torch/transformers 后跑通 pytest 全量 + consistency_check / paper_data / check_alignment / runner CLI 逐一实测 + 三类深度静态审计（seed 统计链 / 契约字段↔实验产出逐字段对照 / 数据来源与硬编码常量溯源），关键发现逐条人工复核
> 与前两轮关系：本报告复核 round1/round2 所有已声明修复是否真正生效并落盘，列出仍残留或新发现的问题，并就其中的诚实标注缺陷做了低风险修复

---

## 一、总体结论

**round1 + round2 的全部关键修复均已提交（`6cbc498`）并经实测生效**：seed 传递、exp11 异常路径 `None`、consistency_check ASCII 化、契约补全 exp7/9/12/13、CITED_FIELDS 两处统一、exp8 batch_benchmark 补 p90/p99、`run_h100.sh --clean` opt-in、runpod overlay `data.dataset: taf28k`、schema 枚举补 `chifraud`、孤儿数据集清理——本轮逐条抽查全部真实生效，无回退。

**pytest 65 passed**（本轮在安装 CPU torch/transformers 后实测）；全包字节编译无错；所有诊断工具（consistency_check 人类/JSON 模式、paper_data 自检、check_alignment、runner `--validate-contract` / `--align`）均跑通且行为诚实。`outputs/results/` 为空，故所有实验一律报 MISSING_RESULT——**任何对外图表仍必须先完成 H100 重跑回填**（与前两轮结论一致）。

本轮新发现集中在**一条诚实标注缺陷**（exp5 `bf16_matched_advfraud` 硬编码常量在代码注释中被误称"measured value"，且在 paper_data 中绕过了其余所有数值都在走的显式报缺机制）与若干**注释/死代码漂移**。诚实标注缺陷及两处注释漂移已在本轮低风险修复（见第五节）。

---

## 二、round1 / round2 修复复核（本轮逐条实测确认）

| 项目 | 复核方式 | 结果 |
|---|---|---|
| seed 传递（消除虚假重复统计） | grep 全实验 | ✅ exp1/2/3/10/11/14 均用 `set_seed(seed_base_from_config(config) + s)`；`common.seed_base_from_config` 默认 1000、claim_engine 注入 `cfg["seed"]=42+s` 时真正生效 |
| exp11 异常路径 `f1: 0.0 → None` | 读源码 | ✅ `exp11_quantization_scheme.py:57` 现为 `{"f1": None, "std": None, "error": ...}` |
| consistency_check ASCII 化 | `PYTHONIOENCODING=gbk` 实跑 | ✅ 图标 `[OK]/[X]/[!]/[i]`，GBK 控制台完整打印、退出码 0，无 `UnicodeEncodeError` |
| 契约补 exp7/9/12/13 | 逐字段对照实验产出 | ✅ 4 个实验的 EXPECTED_FIELDS 键与实验真实产出键**逐一匹配**（exp7 pii_report/asv_eer_pct/…、exp9 with_cot/without_cot.f1/fpr、exp12 competitor_comparison_real.QAD_MultiGuard_INT4.f1 + storage_decomposition_point8.*、exp13 strategies.*.{f1,accuracy,latency_ms}） |
| 两处 CITED_FIELDS 统一 | 对照 | ✅ `metrics/contract.py:169-179` 与 `experiments/consistency_check.py:62-68` 一致（exp5 bf16_matched + exp6 paper_reference 四键含 gamma_deploy） |
| exp8 batch_benchmark 补 p90/p99 | 读源码 + aggregation 消费 | ✅ `exp8:155-156` 产出 `latency_p90_ms/p99_ms`（逐次迭代 + `torch.cuda.synchronize`），`aggregation.py:73` 正确读取——round2 P2「p90/p99 列恒空」已闭合 |
| `run_h100.sh --clean` opt-in | 读脚本 | ✅ `:17/:33/:36` 清理需 `--clean` / `CLEAN=1` 显式开启 |
| runpod overlay 真正强制主语料 | 读 yaml | ✅ `runpod_h100.yaml:31` `dataset: taf28k`（实验读取的正是 `data.dataset`）；`:30` `source` 注释已如实改为「仅 provenance 记录与白名单校验消费」 |
| schema 枚举补 chifraud | grep | ✅ `config/schema.py:24,162` 均含 `chifraud`，与 experiments.yaml / validation 白名单一致 |
| 孤儿数据集清理 | 树 + grep | ✅ `data/balanced600/`、`data/balanced10c/` 已从仓库移除（`data/` 现仅 `scripts/`）；`chifraud.npz` 现为 exp7 的**受 try/except 保护的合法回退依赖**（`exp7:30`），不再是孤儿 |
| eps_1.5 键一致性 | grep 三处 | ✅ exp5 产出 `f"eps_{1.5}"`=`eps_1.5`（点号），paper_data / contract / 契约文档三处均用点号，一致（round2 报告中的 `eps_1_5` 仅为报告笔误，代码无此问题） |

---

## 三、本轮验证记录（当前环境实测）

> 本审计环境无 GPU，初始仅有 PyYAML。经安装 numpy/scikit-learn/scipy + CPU torch/transformers 后可跑通全部非-GPU 路径。

- `python -m compileall`（realeval/experiments/metrics/audit/statlib/runner/config/cli/utils/docs/cluster/scripts/data）→ **exit 0，无错**
- 轻量模块导入（contract/aggregation/extraction/stats/evidence_graph/tracker/schema/loader/registry/parser/io.paths/privacy）→ **全部 OK**
- `pytest tests/ -q` → **65 passed, 1 warning**（5.1s；warning 为 scipy paired-ttest 在近似相同数据上的精度提示，属测试数据特性，非代码缺陷）
- `python -m experiments.consistency_check --json` → 10 实验全部 `MISSING_RESULT`（outputs 为空，预期）
- `PYTHONIOENCODING=gbk python -m experiments.consistency_check` → 人类模式完整打印、退出码 0，无 Unicode 崩溃
- `python docs/figure_scripts/paper_data.py` → 自检通过，缺失字段逐条显式列出（结果为空属预期）
- `python docs/figure_scripts/check_alignment.py` → 跑通，正确报 MISSING
- `python -m experiments.runner --validate-contract` → exit 2（结果文件缺失，预期）；`--align` → 同
- `git status`：审计开始时干净；`git ls-files` 无 `outputs/` 跟踪文件

---

## 四、本轮发现

### P2 — 诚实标注缺陷（本轮已修，见第五节）

**F-1. exp5 `bf16_matched_advfraud = 0.882` 硬编码常量被注释误称"measured value"，且在 paper_data 中绕过显式报缺机制。**
- `experiments/exp5_cross_dataset.py:98` 直接写死 `out["bf16_matched_advfraud"] = 0.882`；原 `:124-125` 注释称其"kept as-is (measured value)"——但它是论文自引用常量（AdvFraud curated 子集上的 BF16 基线，本套件并无对应真实 BF16 跑批），与 `metrics/contract.py:171` 将其归为 **CITED**（非独立测量）直接矛盾。
- `docs/figure_scripts/paper_data.py`（原 `:474`）以 `_get("exp5", "bf16_matched_advfraud") or _FIG8_REF[...]` 读取，**绕过了其余所有图表数值都在走的 `_from_result` 显式报缺机制**：无论 exp5 是否跑过、值是否真实测得，恒返回 0.882 并静默进入 Fig8 面板(b) 的 `bf16_matched` 参照棒，且不进入 `_MISSING_PLACEHOLDERS` 追踪。CITED 审计器（consistency_check）确实会对该键报 WARN，故 tooling 层能捕获；但代码注释的"measured value"表述在事实层面是错的，是本审计系列专门针对的"硬编码常量伪装成实测"一类。

### P3 — 注释 / 死代码 / 语义漂移（低优先级）

**F-2.（本轮已修）`paper_data.py` exp10 注释过时。** 原注释称 exp10"调优后真实产出为单一 F1"，但当前 `experiments/exp10_teacher_scale.py:66-68` 明确产出 `f1_fixed` 与 `f1_conv` 双维，fig5b 读取的正是这两维；契约与 PAPER_CLAIMS 的键均正确。注释误导后续适配者。

**F-3.（本轮已修）`metrics/aggregation.py:63` docstring 过时。** 只列 `{latency_p50_ms, throughput_sps, peak_mem_mb}`，未含函数与 exp8 现已产出/消费的 `latency_p90_ms/p99_ms`。

**F-4. `paper_data.py` 延迟常量为死代码。** `LATENCY_COMPONENTS`（`:209`，管线阶段标签 Feat./Fast/CoT spec./Fus.+UI）、`LATENCY_P50_MS`（`:215`）、`LATENCY_P99_MS`（`:220`）在全仓**零消费**（无任何 figure 脚本或模块引用）。附带两重隐患：(a) 自检输出中 6 条 `PH_EXP8_*_P50/P99` fallback 告警全部由这些死常量产生，纯噪音；(b) 标签（管线阶段）与数据（`int4/fp16/bf16` 三方案 p50/p99）语义不匹配，且以 `12/16` 魔数补齐到 4 项——一旦将来被接线即会错标。建议删除或接线并对齐语义。保守起见本轮仅记录、未删（避免误伤未入库的 figure 脚本）。

**F-5. runner `--paper` 标志为装饰性。** `run_with_mode`（`experiments/framework.py:129`）恒走 paper 真实路径，不存在 smoke/非-paper 分支；`experiments/runner.py:153-154` 的 `args.paper` 仅打印一行日志，从不路由。无害，但"存在非-paper 模式"的暗示可能误导。仅记录，不改行为（改 CLI 有连带风险）。

---

## 五、本轮修复（低风险，已在工作树落盘）

| 编号 | 修复 | 文件 |
|---|---|---|
| F-1 | exp5：将 `bf16_matched_advfraud` 的注释改写为「CITED（非实测）论文自引用常量，镜像 paper_data `_FIG8_REF`、在 contract 归 CITED，仅为让 consistency_check 标注为 cited 而产出，绝不可当独立测量」；删去误导性的"measured value"表述（保留该键产出以维持 CITED 审计信号）。paper_data 侧改为 `_from_result("exp5","bf16_matched_advfraud", placeholder="PH_EXP5_BF16_MATCHED", fallback=_FIG8_REF["advfraud_bf16_matched"], cited=True)`——与其余全部图表数值统一走显式报缺机制，Fig8 该值现进入 `_MISSING_PLACEHOLDERS` 作为**显式标注的 cited 回退**。 | `experiments/exp5_cross_dataset.py`、`docs/figure_scripts/paper_data.py` |
| F-2 | 重写 paper_data exp10 注释，如实描述当前双维（f1_fixed/f1_conv）产出与 fallback=None 报缺策略。 | `docs/figure_scripts/paper_data.py` |
| F-3 | 补 aggregation docstring 的 p90/p99 键说明。 | `metrics/aggregation.py` |
| 附带 | paper_data 自检 banner "non-cited placeholder(s)" → "placeholder(s) using fallback (cited ones are legitimate)"，因引入了一条 cited 占位符，原措辞不再准确。 | `docs/figure_scripts/paper_data.py` |

**修复后验证**：三文件 `py_compile` 通过；`paper_data.py` 自检通过，`PH_EXP5_BF16_MATCHED` 现作为 cited 占位符被正确追踪（fallback=0.882）；`pytest tests/ -q` → **65 passed**。

---

## 六、有意保留（沿用前两轮结论，本轮复核同意）

- `claims/legacy/` + `runner/claim_runner.py` + `runner/interface.py` ABC：自我一致但生产无调用的归档岛；acceptance 扁平键与任何实验产出不匹配，未来复活需先写适配层。
- 3 个新格式 claim（claim_01/02/03）的 `evidence_path` 本轮已逐条对照实验产出确认存在（exp3.conditions.*.variance_drift_pct / exp11.schemes.{int4,fp16}.f1 / exp6.diagnostic_B.h100_measured.generic）；但 claim 评估仍不在任何 pipeline 内（手动 `python -m experiments.claim_engine` 入口）——建议至少在 CI 加一次干跑，防止再次漂移。
- `h100.yaml` 的 `output.*`、`runpod` 声明性字段等死配置键——低风险，保留。
- exp8 逐次计时的 `torch.cuda.synchronize()` 使重跑后 `latency_p50_ms` 可能与旧结果有微小偏移（为测得真实 p90/p99 的必要代价）。

---

## 七、后续建议（按优先级）

1. **H100 重跑回填**：`outputs/results/` 为空，所有图表当前只能由 paper_data 内置常量/None 报缺生成；任何对外图表必须先完成真实重跑（与前两轮一致，是当前唯一的 P0 级前置条件）。
2. F-4 死延迟常量：删除或接线并对齐 label↔data 语义（消除 6 条噪音告警）。
3. claim 引擎接入 CI 干跑，锁定 claim↔实验的字段契约。
4. F-5 若确认永不需要非-paper 模式，可将 `--paper` 标志标注为「兼容保留、恒为真」以消除歧义。
