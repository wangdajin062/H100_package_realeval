# 2026-08-11 重构后脚本产出 vs 实际实验结果 比对审计

> 比对双方：
> **脚本产出** = 当前重构后脚本（本地 smoke 全量跑 14/14 通过 + paper 路径静态核查）；
> **实际结果** = `outputs/results/` 最新文件（2026-08-02/03 RunPod H100 产出，已回拉）。
> 校验工具：`--validate-contract`（metrics/contract.py）、`docs/figure_scripts/check_alignment.py`、结构递归 diff。

## 一、结论速览

| 类别 | 条目数 | 状态 |
|---|---|---|
| A. 契约破坏（校验 FAIL） | 2 | 1 已校正（exp2），1 待 H100 重跑（exp11） |
| B. 数值层失效/异常（字段在、值不对） | 4 | 待 H100 重跑/排查 |
| C. 脚本 smoke/paper 结构分歧 | 11 | 2 已修正（exp5/exp6），9 记录在案 |
| D. 旧结果遗留字段 | 1 | 无害，记录在案 |
| E. 工具问题 | 1 | 记录在案（有约束未改） |

校正后校验状态：`check_alignment.py` 65 处字段路径全 PASS；`--validate-contract` 仅余 exp11.schemes.bf16 一项 FAIL。

> **2026-08-11 数据事件（见第九节）**：比对完成后，测试套件的隔离缺陷清空了 `outputs/results/` 真实结果。exp2/exp6/exp11 已逐字恢复，其余需从 Pod 重新同步。下表"状态"以删除前状态为准。

## 二、A 类：契约破坏与校正

| 实验 | 差异 | 根因 | 处置 | 状态 |
|---|---|---|---|---|
| exp2 | 最新结果（`exp2_20260803_092151.json`）缺 `variants.kl_task.{f1,kl_final,std}`；paper_data 回退硬编码 0.4048/0.372 | 该结果 09:21 UTC 落盘，早于 Pod 10:45 拉取重构代码；当前脚本 paper/smoke 均自动产出 `kl_task = kl_only` 别名 | 按脚本自身别名规则回填最新结果文件及 `all_experiments.json`（kl_task = kl_only：f1 0.5577 / kl 0.34629 / std 0.1361，含 f1_list） | ✅ 已校正，双校验 PASS |
| exp11 | 最新结果（`exp11_20260803_084323.json`）缺 `schemes.bf16.{f1,std}` | bf16 参考基线在 680a90d 才加入脚本，exp11 08:43 UTC 已跑完 | 无真实测量可回填，禁止编造 → **需 H100 重跑 exp11** | ⏳ 待重跑；paper_data 目前硬编码 BF16_F1=0.931，图像脚本不受影响 |

## 三、B 类：数值层失效/异常（契约 PASS 但值不可信）

| 实验 | 实际结果现状 | 说明 | 处置 |
|---|---|---|---|
| exp3 | 4 条件 drift 全 0.0、f1 全 0.5121（`exp3_20260803_131209.json`） | OVF 消融失效轮（freeze_frac/window 未传入的回归，cec086a 已修复）；快速验证已恢复响应（no_reg 52.45 / full 0.00） | 完整 exp3（14 配置×5 seed，3–4h）待重跑 |
| exp14 | bf16 **0.0269** / q4km **0.0014**（`exp14_20260803_154344.json`） | 15:45 重跑后仍严重异常（8/2 曾 0.59/0.70）；疑似 F1 调优后评估路径/阈值未对齐 | 待排查评估路径后重跑 |
| exp5 | taf 0.6647 / chi 0.6298 / ldp_eps1.5 0.5359 | 跑于 F1 调优（15:01）前，基于旧 exp1_qad 权重，与 exp1 现值 0.7974 不同源 | 随新 exp1_qad 复测 |
| exp10 | teacher 0.9044 / 1.5B 0.8373 / 3B 0.7411 / 7B 0.7161 | 同上（调优前）；且教师-学生评估路径一致性待确认 | 随新 exp1_qad 复测 |
| exp12 | QAD_MultiGuard_INT4 **0.0603** | 同上，异常低 | 随新 exp1_qad 复测 |

## 四、C 类：脚本 smoke/paper 结构分歧（契约文档 §3.3 要求两路径结构一致）

| 实验 | 分歧内容 | 性质 | 处置 |
|---|---|---|---|
| exp6 | smoke 把引用值 α_domain=0.86 放入 `h100_measured`（误标为实测），缺嵌套 `paper_reference` 与顶层 `note` | 违反"引用值不得标为实测"原则 | ✅ 已修正：smoke 对齐真实 `diagnostic_B()` 返回结构，domain 仅存于 paper_reference |
| exp5 | smoke 仍产出 paper 路径已删除的 `paper_reference` 自引块（66c63a7 改用 ldp_tradeoff 实测） | 重构遗留，自引值可能回流 | ✅ 已移除（连带清理闲置变量） |
| exp1 | smoke 多 `path`；缺 `kl_final_list`/`drift_pct_list`/`n_seeds`/`quantize`/`*_note` | 元数据不对称，无消费方 | 记录在案 |
| exp2 | smoke 缺 `variants.*.f1_list` | 同上 | 记录在案 |
| exp4 | smoke 缺 `dataset` | 同上 | 记录在案 |
| exp7 | smoke 缺 `coverage` 覆盖清单 | 同上 | 记录在案 |
| exp8 | smoke 缺 `latencies.int8_fallback_flagged`/`fp16_slower_than_int4`；`peak_mem_mb=None` 为设计内（无 GPU） | 同上 | 记录在案 |
| exp9 | smoke 缺 `with_cot.note`/`without_cot.note` | 同上 | 记录在案 |
| exp11 | smoke 多 `schemes.*.quant_note` | 同上 | 记录在案 |
| exp12 | smoke 多 `storage_decomposition_point8.note` | 同上 | 记录在案 |
| exp14 | smoke 多 `is_synthetic`；bf16/q4km 缺 `std`/`f1_std`/`n_seeds`/`latency_ms_p50` | 同上 | 记录在案 |

> 说明：所有 `std` 字段 smoke=None vs 实际=float 属设计内差异（契约文档 §3.6：单 seed 无标准差），未计入分歧。

## 五、D 类：旧结果遗留字段（当前脚本不再产出，无消费方）

| 实验 | 字段 | 说明 |
|---|---|---|
| exp11 | `schemes.*.f1_std` | 旧脚本双写 f1_std+std；当前脚本只写 `std`。遗留无害，下次重跑自然消失 |

## 六、E 类：工具问题

| 项 | 问题 | 处置 |
|---|---|---|
| `docs/figure_scripts/check_alignment.py` | Windows GBK 控制台打印 ✓/✗ 触发 UnicodeEncodeError 崩溃 | 该目录有"不可修改"硬约束，未改动；workaround：`PYTHONIOENCODING=utf-8 python docs/figure_scripts/check_alignment.py` |

## 七、一致性确认（无差异项）

- **exp13**：smoke/paper/实际结果三方结构完全一致。
- **exp1**：实际结果 f1 0.7974 / acc 0.9456 / std 0.0133，与 RUNLOG 记录吻合；字段全 PASS。
- **exp9**：with_cot 0.3131(fpr 0.2608) / without_cot 0.8047(fpr 0.0165)，与 RUNLOG 吻合；字段全 PASS。
- **exp4/exp7/exp8**：契约字段全部满足；数值与 RUNLOG 汇总一致（exp4 qwen_base 0.9061、exp8 bf16 27ms 等）。

## 九、数据丢失事件与处置（2026-08-11）

### 经过
本次比对收尾时运行测试套件，`tests/test_archive_cleanup.py::test_archive_if_needed_force`
对 `realeval.io.archive` 的标量路径常量打了 monkeypatch，但**未补丁 import 期构建的
`_CLEAR_GLOBS`/`_CLEAR_DIRS` 列表**；`archive_if_needed(force=True)` 末尾的
`clear_outputs()` 按真实路径执行删除，`outputs/results/` 下全部真实 H100 结果
（14 个实验的 exp\*\_\*.json、all_experiments.json、metrics/latency 等派生文件）被清空。
同文件 `test_clear_outputs_removes_result_jsons` 未补丁 `_CLEAR_DIRS`，连带清空了
figures/metrics/tables 子目录内容。

### 根因（双重隔离失效）
1. 上述两个测试补丁不全（已修复，见下）。
2. `realeval/io/paths.py` 不读 `REALEVAL_OUTPUT_ROOT` 环境变量（仅 envreport 读），
   导致 conftest 的隔离对 runner 子进程无效（smoke exp1 结果曾写入真实目录）。

### 恢复结果
| 文件 | 恢复方式 | 状态 |
|---|---|---|
| exp2_20260803_092151.json（含本次 kl_task 回填） | 本会话完整读取记录逐字重建 | ✅ |
| exp2_20260802_130638.json | 同上 | ✅ |
| exp11_20260803_084323.json | 同上 | ✅ |
| exp6_20260803_131248.json | 同上 | ✅ |
| exp1_20260803_151832（0.7974 调优版）、exp3/4/5/7/8/9/10/12/13/14 最新结果、all_experiments.json | 本地无完整副本（归档 md 仅含 08-02 前的旧版全量 JSON） | ❌ **需从 Pod 重新同步**（`scripts/sync_from_runpod.py`）；Pod 不可用时需按第八节待办重跑 |
| 测试产生的 smoke/集成测试垃圾文件 | 已删除 | ✅ |

### 已实施的隔离修复
- `realeval/io/paths.py`：`OUTDIR` 改为读取 `REALEVAL_OUTPUT_ROOT`（未设置时行为不变；子进程隔离生效）。
- `tests/test_archive_cleanup.py`：两个测试均补齐 `_CLEAR_GLOBS`/`_CLEAR_DIRS` 补丁。
- `tests/conftest.py`：`isolate_outputs` 升级为逐模块重绑定 import 期固化的路径常量
  （io.paths / serialization / archive，含 `_CLEAR_GLOBS`/`_CLEAR_DIRS`），in-process 写入同样隔离。
- `tests/test_runner_integration.py`：断言目录跟随 `REALEVAL_OUTPUT_ROOT`；
  3 处 `subprocess.run` 加 `errors="replace"`（顺带修复 Windows GBK 下
  `test_runner_requires_explicit_mode` 的既有解码失败——该失败与本次改动无关，已单独验证）。

## 十、待办清单（按优先级）

1. **从 Pod 重新同步 outputs/results/**（或重跑）；同步后重跑 `--validate-contract` 与 `check_alignment.py` 复核。
2. **H100 重跑 exp11**（补 schemes.bf16）→ 契约全 PASS。
3. **H100 重跑完整 exp3**（cec086a 修复后的 14 配置×5 seed）。
4. **排查并重跑 exp14**（bf16 0.0269 异常，疑 F1 调优后评估路径未对齐）。
5. 随新 exp1_qad 复测 exp5/exp10/exp12（消除跨图权重不同源）。
6. （可选）若解除 docs/figure_scripts/ 只读约束，修复 check_alignment.py 的 GBK 打印。
