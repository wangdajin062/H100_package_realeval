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
