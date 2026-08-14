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
