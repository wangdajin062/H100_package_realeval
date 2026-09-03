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
