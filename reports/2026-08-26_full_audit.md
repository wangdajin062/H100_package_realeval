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
