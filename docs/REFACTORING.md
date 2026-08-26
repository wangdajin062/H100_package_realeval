# 重构说明 —— H100_package_realeval

> 记录 2026-08-05 对实验侧代码的模块化重构。重构目标：在不修改 `docs/figure_scripts/` 的前提下，让实验脚本输出字段与图像脚本输入完全对齐，并建立可复现实验管线。

---

## 1. 重构目标

1. 消除重复代码（去重与复用）
2. 模块化设计（按职责拆分）
3. 统一配置管理（集中、可覆盖、可追踪）
4. 日志系统（分级、可落盘、可追踪实验）
5. 参数解析（CLI + 配置协同）
6. 错误处理（明确异常边界与可读报错）
7. 类型注解（关键模块完善 typing）
8. 文档补充（使用说明、复现路径、参数字典）

---

## 2. 新模块职责

```
H100_package_realeval/
├── config/                    # 统一配置管理
│   ├── __init__.py            # 暴露 load_config / validate_config / get_default_config
│   ├── loader.py              # YAML 加载、合并、环境变量覆盖、数值字符串强制转换
│   └── schema.py              # 配置 schema 与校验
├── runner/                    # 实验编排
│   ├── registry.py            # 14 个实验注册表
│   ├── experiment_runner.py   # 单实验运行封装（日志、异常、GPU 清理）
│   └── orchestrator.py        # 多实验调度、归档、结果归并
├── metrics/                   # 指标计算与聚合
│   ├── contract.py            # 字段合约（从 experiments/alignment.py / contract.py 迁移）
│   ├── extraction.py          # headline 指标提取
│   └── aggregation.py         # 多 seed 聚合
├── realeval/io/               # IO 子包（替代原 realeval/io.py，避免与标准库 io 冲突）
│   ├── __init__.py            # 向后兼容：from realeval.io import ... 仍然有效
│   ├── paths.py               # 路径管理
│   ├── serialization.py       # JSON/CSV/NPY 序列化
│   └── archive.py             # 自动归档 + 清理
├── cli/
│   └── parser.py              # 统一 argparse
├── utils/
│   ├── logging.py             # 统一日志工厂
│   ├── exceptions.py          # 结构化异常
│   └── typing.py              # 公共类型别名
└── experiments/               # 14 个实验脚本 + 兼容层
    ├── runner.py              # CLI 包装器（委托 runner.orchestrator）
    ├── paper_pipeline.py      # 一键流水线（委托 runner + metrics）
    ├── framework.py           # 模式分发 / 数据回退 / 通用 helper
    ├── common.py              # 公共训练/评估 helper
    ├── consistency_check.py   # 论文数字 vs 实测一致性守门员
    └── exp*_*.py              # 各实验实现
```

---

## 3. 核心数据流

```
CLI (experiments.runner)
    │
    ▼
runner.orchestrator.run_experiments()
    │
    ├── config.loader.load_config()          # 加载 + 合并 + 校验
    ├── realeval.io.archive.archive_and_clear_outputs()  # 自动归档旧结果
    │
    ├── 对每个实验：
    │   runner.registry.get_experiment(name)
    │   runner.experiment_runner.run_single_experiment()
    │       ├── 实验 run(config) → dict
    │       └── metrics.extraction.extract_headline(result)
    │
    ├── realeval.io.serialization.save_all_experiments()  # 写入 all_experiments.json
    ├── metrics.contract.validate_contract() # 字段合约校验
    └── experiments.consistency_check.main() # 论文数字 vs 实测漂移检查
```

---

## 4. 复现路径

### 4.1 本地验证（无需 GPU）

```bash
cd Projects/H100_package_realeval

# 测试基线（smoke 路径已移除；本地验证走 pytest + 对齐/合约检查）
python -m pytest tests/ -q

# 字段对齐检查：65 处 _from_result 字段全部可解析
python docs/figure_scripts/check_alignment.py

# 合约校验（smoke 模式下会标出 NON_H100_COMPUTATION，属预期行为）
python -m experiments.runner --validate-contract

# 一致性检查（smoke / CITED / DRIFT 标注意义见第 9 节）
python -m experiments.consistency_check
```

### 4.2 H100 / RunPod 论文级复现

```bash
# 一键运行全部 14 个实验（自动归档旧结果）
bash run_h100.sh

# 或等价命令
python -m experiments.paper_pipeline --paper --config config/runpod_h100.yaml

# 生成论文表格与图像
python -m experiments.runner --report
cd docs/figure_scripts && python generate_all.py
```

### 4.3 自动归档工作流

每次运行（不带 `--no-archive`）时：

1. 若 `outputs/results/` 存在旧结果，自动构建 Markdown 归档快照
2. 写入 `outputs/archive/{YYYY-MM-DD_HHMMSS}_experiment_results.md`
3. 清理 `outputs/results/` / `outputs/metrics/` / `outputs/predictions/` 等
4. 运行新实验

---

## 5. 向后兼容

- `from realeval.io import ...` 仍然有效（`realeval/io/__init__.py` 转发到新子包）。
- 旧版 `experiments/alignment.py` / `experiments/contract.py` 已删除，字段合约逻辑统一迁移到 `metrics/contract.py`。
- `experiments/claim_engine.py` 的 `_SHORT_TO_FULL` 改为从 `runner.registry.SHORT_TO_FULL` 导入。
- 实验脚本 `exp1_qad_production.py` 等输出字段保持原命名，未做不兼容改动。

---

## 6. 验证状态（2026-08-05）

| 检查项 | 状态 | 说明 |
|--------|------|------|
| `py_compile` 全文件通过 | ✓ | 新/改模块无语法错误 |
| `pytest tests/ -q` | ✓ | **71 passed, 1 warning** |
| smoke 全部 14 个实验 | ✓ | exp1–exp14 全部完成 |
| `check_alignment.py` | ✓ | 65 处字段路径全部可用 |
| `validate-contract` | ✓ | 严格模式按预期标出 smoke 非 H100 计算 |
| `consistency_check` | ✓ | 仅预期内的 SMOKE/CITED/DRIFT，无 MISSING |
| 自动归档 | ✓ | 生成带时间戳 Markdown 并清理输出目录 |
| 大文件从历史移除 | ✓ | 已移除 `docs/figure/`、`data/`、`cluster/cloudflared` |
| 远程分支清理 | ✓ | 仅保留 `refs/heads/main`，`master`/`main_11` 已删除 |
| 本地引用清理 | ✓ | 已清理 `refs/original/`、`refs/agents/`、`refs/cline/`、stash、reflog |
| `.git` 目录大小 | ✓ | 从约 931M 降至 888K |
| LFS 缓存清理 | ✓ | `git lfs prune --force` 删除 83 个本地对象 |

---

## 7. Git 历史清理记录

为降低仓库体积并移除过期二进制/数据历史，对 `main` 分支执行了重写式清理。所有论文图像脚本（`docs/figure_scripts/`）未受影响。

### 7.1 移除内容

- `docs/figure/`：所有 `.tiff`/`.png`/`.pdf` 生成图像
- `data/`：TAF-28k、ChiFraud 等数据集
- `cluster/cloudflared`：集群部署二进制

### 7.2 关键命令

```bash
# 重写 main，移除 docs/figure
git filter-branch --force --index-filter 'git rm --cached --ignore-unmatch -r docs/figure' --prune-empty --tag-name-filter cat -- main

# 清理本地过期引用
git remote set-head origin -d
git update-ref -d refs/remotes/origin/main
git stash clear
git reflog expire --expire=now --all

# 强制推送与垃圾回收
git push origin main --force
git gc --aggressive --prune=now
git lfs prune --force
```

### 7.3 清理后状态

- 远程仅剩 `main` 分支
- 本地 `.git` 从约 **931M** 降至 **888K**
- `git rev-list --objects --all` 中无 ≥1MB blob
- `git lfs ls-files` 为空

### 7.4 协作注意

这是一次强制推送，所有提交哈希已改变。其他机器请直接删除旧 clone 后重新拉取：

```bash
git clone ssh://git@ssh.github.com:443/wangdajin062/H100_package_realeval.git
```

---

## 8. 已知限制

- **exp5 / exp7 / exp10 / exp12 / exp13 / exp14** 在本地无网络环境时会尝试从 HuggingFace 下载 `wangdajin062/TeleAntiFraud-bucket`，导致长时间重试。请在 H100/RunPod 环境或预先下载 `data/TAF28k` 后运行。
- smoke 路径数值为合成近似，仅用于验证代码路径与字段结构；论文图表真实数值需 `--paper` 路径。
- H100 实测后需更新 `experiments/consistency_check.py` 中的 `PAPER_CLAIMS` 表，才能长期作为“论文数字 vs 实测”的守门员。

---

## 9. 一致性检查说明（`experiments/consistency_check.py`）

该工具补齐了 `metrics/contract.py` 只检查“字段存在”的不足，额外做三层判定：

| 判定 | 含义 | 示例 |
|------|------|------|
| **SMOKE** | `computation` 不以 `h100` 开头，不是真实 H100 测量 | 本地 smoke 运行全部被标红 |
| **CITED** | 字段为硬编码论文值/自引用，不可当证据 | exp5 `bf16_matched_advfraud`、exp6 `paper_reference.*` |
| **DRIFT** | 实测头条指标与 `PAPER_CLAIMS` 声称值差距过大 | smoke 数值与论文值偏离时会标红 |
| **MATCH** | 实测值在容忍范围内 | exp13 late fusion 0.8975 vs 声称 0.923 |

用法：

```bash
python -m experiments.consistency_check          # 人读格式，有 P0 则 exit=1
python -m experiments.consistency_check --json   # 机读格式，供 CI 解析
```

> 注：`PAPER_CLAIMS` 中的阈值/期望值按当前论文声称填写；完成 H100 `--paper` 复测后请同步更新，再把它接进 `paper_pipeline` 末尾即可实现自动守门。
