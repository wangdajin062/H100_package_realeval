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
│   ├── defaults.py            # 默认配置字典
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
    ├── alignment.py           # 兼容 re-export（原字段对齐逻辑已迁移到 metrics/contract.py）
    ├── contract.py            # 兼容 re-export
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
    └── metrics.contract.validate_contract() # 字段合约校验
```

---

## 4. 复现路径

### 4.1 本地 smoke 验证（无需 GPU / 无需网络）

```bash
cd Projects/H100_package_realeval

# 运行不需要 HuggingFace 下载的子集
python -m experiments.runner --smoke --no-archive --exp 1,2,3,4,6,8,9,11

# 字段对齐检查（预期仅剩 exp5 / exp14 因需 TAF-28k 网络下载而缺失）
python docs/figure_scripts/check_alignment.py

# 合约校验
python -m experiments.runner --validate-contract
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
- 旧版 `experiments/alignment.py` / `experiments/contract.py` 保留兼容 re-export。
- 实验脚本 `exp1_qad_production.py` 等输出字段保持原命名，未做不兼容改动。

---

## 6. 验证状态（2026-08-05）

| 检查项 | 状态 | 说明 |
|--------|------|------|
| `py_compile` 全文件通过 | ✓ | 新/改模块无语法错误 |
| `pytest tests/test_integration.py` | ✓ | 4/4 通过 |
| smoke 子集运行 | ✓ | exp1/2/3/4/6/8/9/11 成功 |
| `check_alignment.py` | 部分通过 | 仅 exp5 / exp14 缺失（需 TAF-28k 网络下载） |
| `validate-contract` | 部分通过 | 同上 |
| 自动归档 | ✓ | 生成带时间戳 Markdown 并清理输出目录 |

---

## 7. 已知限制

- **exp5 / exp7 / exp10 / exp12 / exp13 / exp14** 在本地无网络环境时会尝试从 HuggingFace 下载 `wangdajin062/TeleAntiFraud-bucket`，导致长时间重试。请在 H100/RunPod 环境或预先下载 `data/TAF28k` 后运行。
- smoke 路径数值为合成近似，仅用于验证代码路径与字段结构；论文图表真实数值需 paper 路径。
