# 实验脚本系统化重构 — 设计文档

> 日期: 2026-08-03
> 目标: 在**不修改论文图像脚本**的前提下，使实验侧参数与字段完全对齐图像脚本所需输入

## 1. 背景与约束

### 硬性约束
- 不修改 `docs/figure_scripts/fig{1..8}_*.py`（图像脚本）
- 不修改 `realeval/` 核心库
- 论文所有图表结果必须来自重构后的实验脚本真实运行流程

### 当前问题
- 14 个实验脚本中 7 种重复代码模式，共计 ~60 处复制粘贴
- `paper_data.py` 中存在硬编码 fallback 值，实验失败时静默回退到论文数字
- `generate_all.py` / `sync_paper_data.py` 路径解析 bug（3 层 parent vs 2 层）
- 9 个实验脚本无任何错误处理
- 配置键命名不一致（`exp1_seeds` / `exp2_seeds` ...）
- exp8 字段命名与 `paper_data.py` 不匹配（`latencies` vs `latency_detail`）

### 核心目标
实验脚本重构后，`paper_data.py` 中每一个 `_from_result()` 调用都能从实验 JSON 中找到正确的实测值。
**这是衡量重构成功与否的唯一标准。**

## 2. 参数与字段对齐映射

### 2.1 图像脚本 → 实验产出映射表

```
paper_data 变量              来源实验     期望字段路径                        当前状态
══════════════════════════════════════════════════════════════════════════════════
BF16_F1                      硬编码       0.931                             ← 保留硬编码(无BF16实测)
EXP01_QUANT_QUALITY          硬编码       6条PTQ baseline                   ← 保留硬编码(外部引用)
QAT_QAD_OVF[0] (QAT)        exp11        schemes.int4.f1, std              ✅
QAT_QAD_OVF[1] (QAD)        exp1         f1, std                           ✅
QAT_QAD_OVF[2] (QAD+OVF)    exp3         conditions.ov_freeze_full.f1      ✅
QAT_QAD_OVF[3] (Q4_K_M)     exp14        models.q4km_0.5b_llama_cpp.f1     ✅
LOSS_PLATEAU                 exp1         trajectory[*].kl → plateau       ✅
LOSS_CONVERGED               exp1         trajectory[-1].kl                ✅
OVF_ACTIVATION_STEP          exp1         ovf_activation_step               ✅
TOTAL_STEPS                  exp1         total_steps                       ✅
SNR_RANGE                    exp1         (snr_min, snr_max)                ✅
EXP03_LOSS_ABLATION          exp2         variants.{kl_only,mse_only,ce_only,kl_mse_combined,kl_task}.{f1,kl_final,std} ✅
EXP09_TEACHER                exp10        scales.{teacher,teacher_1.5b,teacher_3b,teacher_7b}.{f1_fixed,f1_conv} ✅
EXP04_OVF_LAYER_ABLATION     exp3         layer_selection.{early,mid,late}.{f1,drift_pct}  ✅
                                        + conditions.*  + rho_sweep       ⚠️ rho_sweep缺少ratio_pct扫描
EXP10_OVF_STEP_RATIO         exp3         rho_sweep (需映射到ratio_pct)     ⚠️ 当前rho_sweep用ρ值,非%
EXP05_SPECULATIVE            exp6         diagnostic_B.h100_measured        ⚠️ 缺domain实测
                                        + paper_reference.*               ✅
SPEC_ALPHA_GENERIC           exp6         diagnostic_B.h100_measured.generic ✅
SPEC_ALPHA_TUNED             exp6         paper_reference.alpha_tuned       ⚠️ 缺实测,来源引用
SPEC_GAMMA_DEPLOY            exp6         paper_reference.gamma_deploy       ✅
FIG8_QUANT                   exp11        schemes.{int4,hetero}.f1          ⚠️ 缺异构vs同构对比
FIG8_ADVFRAUD                exp5         advfraud.{curated,full_pool}.f1   ✅
FIG8_LDP                     exp5         paper_reference.ldp_eps_1_5_f1    ⚠️ 缺实测
```

### 2.2 字段兼容策略
- `experiments/alignment.py` 中定义 `EXPECTED_FIELDS` 字典
- 每个实验返回结果时由 `contract.py` 校验必填字段存在性
- `paper_data.py` 中 `_MISSING` 哨兵替代静默 fallback（实验值缺失时 raise 而非回退到论文数字）
- 旧字段通过 `paper_data.py` 中的 fallback 路径兼容（先查新字段名，再查旧字段名）

## 3. 架构变更

### 3.1 新增文件

| 文件 | 职责 | 大小预估 |
|------|------|---------|
| `experiments/common.py` | 共享工具集 | ~80 行 |
| `experiments/smoke.py` | Smoke test 共享逻辑 | ~50 行 |
| `experiments/alignment.py` | 实验→图像脚本字段对齐校验 | ~60 行 |

### 3.2 修改文件

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `experiments/framework.py` | 小幅修改 | 修复 `setdefault("experiment")` 与手动设置冲突 |
| `experiments/runner.py` | 小幅修改 | 添加 `--align` 标志, 运行后自动校验 |
| `experiments/contract.py` | 扩展 | 补充全量字段路径 |
| `config/experiments.yaml` | 小幅修改 | 新增 `multi_seed_counts` section |
| `docs/figure_scripts/paper_data.py` | 修复 | 硬编码→_MISSING哨兵模式 |
| `docs/figure_scripts/generate_all.py` | 修复 | 路径bug修复 |
| `docs/figure_scripts/sync_paper_data.py` | 修复 | 路径bug修复 |
| `experiments/exp{1..14}_*.py` | 重构 | 去重 + 错误处理 + 类型注解 |

### 3.3 不改的文件
- `realeval/*`（核心库）
- `docs/figure_scripts/fig{1..8}_*.py`（图像脚本）
- `cluster/*`（训练脚本）
- `config/experiments.yaml` 顶层结构

## 4. 各组件详细设计

### 4.1 `experiments/common.py`

```python
"""共享工具集: 消除14个实验脚本间的重复代码."""

def set_seed(seed: int) -> None:
    """torch + numpy + cuda 三合一 seed 设置."""
    ...

def load_dataset(config: dict, default_name: str = "taf28k",
                 max_samples: int | None = None) -> DatasetSplit:
    """统一的数据加载 + 防泄漏分割."""
    ...

def n_seeds_from_config(config: dict, exp_id: str) -> int:
    """从 unified multi_seed_counts 读取."""
    ...

def multi_seed_std(values: list[float]) -> float | None:
    """多 seed 的标准差计算."""
    ...

def smoke_baseline_f1(labels: list[int]) -> float:
    """GradientBoosting baseline F1."""
    ...

def config_override(config: dict, **overrides: dict) -> dict:
    """deepcopy config + 递归 merge overrides."""
    ...

def resolve_qad_path() -> Path | None:
    """解析 exp1 产出的 QAD 模型路径."""
    ...
```

### 4.2 `experiments/smoke.py`

```python
"""Smoke test 共享逻辑."""

def toy_kl_distill(X: np.ndarray, y: np.ndarray, n_classes: int = 4) -> dict:
    """玩具 KL 蒸馏 (LogisticRegression teacher + Linear student)."""
    ...

def quantize_proxy(arr: np.ndarray, bits: int) -> np.ndarray:
    """均匀量化代理 (用于 INT4/NF4 smoke)."""
    ...
```

### 4.3 `experiments/alignment.py`

```python
"""实验→图像脚本 字段对齐校验器.

在每次 runner 运行后自动执行，确保 paper_data.py 的
_from_result() 调用都能在实验产出 JSON 中找到对应字段.
"""

EXPECTED_FIELDS: dict[str, list[tuple[str, ...]]] = {
    "exp1": [
        ("f1",), ("std",), ("trajectory",),
        ("kl_plateau",), ("kl_converged",),
        ("ovf_activation_step",), ("total_steps",),
        ("snr_min",), ("snr_max",),
    ],
    "exp2": [
        ("variants", "kl_only", "f1"),
        ("variants", "mse_only", "f1"),
        ("variants", "ce_only", "f1"),
        ("variants", "kl_mse_combined", "f1"),
        ("variants", "kl_task", "f1"),
    ],
    # ... exp3–exp14 同理
}

def check_alignment(all_results: dict) -> list[str]:
    """返回未对齐字段列表."""
    ...
```

### 4.4 `paper_data.py` 修复

关键变更：`_from_result` 在实验值缺失时 **raise MissingExperimentData** 而非静默回退到硬编码值。

```python
class MissingExperimentData(Exception):
    """实验数据缺失 — 不能静默回退到论文硬编码值."""

_SENTINEL = object()

def _from_result(exp: str, *keys: str, default=_SENTINEL):
    """从实验结果 JSON 中抽取字段。default 仅用于可选字段."""
    try:
        val = _nested_get(by_exp[exp], keys)
        if val is not None:
            return val
    except (KeyError, TypeError):
        pass
    if default is not _SENTINEL:
        return default
    raise MissingExperimentData(f"{exp}: {'→'.join(keys)} not found")
```

### 4.5 路径 bug 修复

`generate_all.py` 和 `sync_paper_data.py`:
```python
# 修复前 (错误)
_ROOT = Path(__file__).resolve().parent.parent.parent  # → C:\Users\wang\Projects

# 修复后 (正确)
_ROOT = Path(__file__).resolve().parent.parent  # → C:\Users\wang\Projects\H100_package_realeval
```

`generate_all.py` 清除目录:
```python
# 修复前
_FIGURE_DIR = _HERE.parent / "figure"  # → <repo>/figure (但图写入 docs/figure)

# 修复后
_FIGURE_DIR = _HERE.parent / "figure"  # 保持 docs/figure (与 fig*.py 写入一致)
```

## 5. 验证标准

重构完成后，以下检查全部通过即视为成功：

1. `python -m experiments.runner --validate-contract` 全部 14 个实验字段通过
2. `python -m docs.figure_scripts.check_alignment` 退出码 0
3. `python -m docs.figure_scripts.generate_all` 不报错，所有图片可生成
4. `python -m experiments.runner --smoke --exp all` 全部通过
5. `paper_data.py` 中不再有静默 fallback 到论文硬编码值的路径

## 6. 不在范围内

- 不修复评测管线本身的 bug（fp16<int4、int8 时延异常、FPR≈0.96 等）— 这些属于 rerun_checklist.md 的先决条件
- 不优化模型训速/推理性能
- 不新增实验
- 不修改论文文本
- 不引入新的 Python 依赖
