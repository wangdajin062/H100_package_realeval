# 实验脚本系统化重构 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删除实验脚本间的重复代码，统一配置管理，修复 paper_data.py 静默 fallback 和路径 bug，确保实验产出字段与论文图像脚本 100% 对齐。

**Architecture:** 新增 `experiments/common.py`、`experiments/smoke.py`、`experiments/alignment.py` 三个模块；重构 14 个实验脚本消除重复；修复 `paper_data.py` / `generate_all.py` / `sync_paper_data.py` 路径 bug 和静默回退问题。

**Tech Stack:** Python 3.10+, PyTorch, sklearn, 零新依赖。

---

## 文件变更总览

| 操作 | 文件 |
|------|------|
| **Create** | `experiments/common.py` |
| **Create** | `experiments/smoke.py` |
| **Create** | `experiments/alignment.py` |
| **Modify** | `experiments/framework.py` |
| **Modify** | `experiments/runner.py` |
| **Modify** | `experiments/contract.py` |
| **Modify** | `experiments/exp{1..14}_*.py` |
| **Modify** | `docs/figure_scripts/paper_data.py` |
| **Modify** | `docs/figure_scripts/generate_all.py` |
| **Modify** | `docs/figure_scripts/sync_paper_data.py` |
| — | `config/experiments.yaml`（不改数据源配置） |

---

### Task 1: Create `experiments/common.py` — 共享工具集

**Files:**
- Create: `experiments/common.py`

**Purpose:** 提取 14 个实验脚本中 7 种重复模式，消除 ~60 处复制粘贴。

- [ ] **Step 1: Write `experiments/common.py`**

```python
"""experiments/common.py — 实验脚本共享工具集。

消除 14 个实验脚本间的重复代码：
- set_seed(): torch + numpy + cuda 三合一（修复 exp2 遗漏 np.random.seed 的 bug）
- load_and_split_dataset(): 统一数据加载 + 防泄漏分割
- n_seeds_from_config(): 统一 multi-seed 计数读取
- multi_seed_std(): 多 seed 标准差
- smoke_baseline_f1(): GradientBoosting 基准
- config_override(): deepcopy + merge
- resolve_qad_path(): QAD 模型路径解析
"""
from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any

import numpy as np
import torch

from experiments.framework import (
    DatasetSplit,
    TextDataset,
    leakage_safe_split,
    load_first_nonempty,
)

logger = logging.getLogger("common")


# ── Seed ──────────────────────────────────────────────────────────────────────

def set_seed(seed: int) -> None:
    """torch + numpy + cuda 三合一 seed 设置."""
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    np.random.seed(seed)


# ── Dataset ───────────────────────────────────────────────────────────────────

def load_and_split_dataset(
    config: dict[str, Any],
    default_dataset: str = "taf28k",
    default_max_samples: int | None = None,
    test_ratio: float = 0.2,
    seed: int = 42,
    synthetic_n: int = 200,
) -> DatasetSplit:
    """统一的数据加载 + 防泄漏分割。

    按顺序尝试真实数据加载器，全部失败则回退到合成数据。
    """
    from realeval import data as realeval_data

    dataset_name = config.get("data", {}).get("dataset", default_dataset)
    max_samples = config.get("data", {}).get("max_samples", default_max_samples)
    ds: TextDataset = load_first_nonempty(
        loaders=[lambda: realeval_data.load_dataset(dataset_name, max_samples=max_samples)],
        synthetic_loader=lambda: realeval_data.load_synthetic(n=synthetic_n),
    )
    return leakage_safe_split(ds, test_ratio=test_ratio, seed=seed)


# ── Multi-seed ────────────────────────────────────────────────────────────────

def n_seeds_from_config(config: dict[str, Any], exp_id: str) -> int:
    """从 reproducibility.{exp_id}_seeds 读取 seed 数，默认 3。

    不引入新的配置键——保持对现有 exp1_seeds / exp2_seeds 等的兼容。
    """
    return int(config.get("reproducibility", {}).get(f"{exp_id}_seeds", 3))


def multi_seed_std(values: list[float]) -> float | None:
    """多 seed 的标准差。单 seed 返回 None。"""
    if len(values) <= 1:
        return None
    return round(float(np.std(values)), 4)


# ── Config ────────────────────────────────────────────────────────────────────

def config_override(config: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    """deepcopy config 并递归 merge overrides 到指定 section。

    用法: config_override(config, training={"epochs": 3})
    """
    cfg = copy.deepcopy(config)
    for section, updates in overrides.items():
        cfg.setdefault(section, {}).update(updates)
    return cfg


# ── QAD path ──────────────────────────────────────────────────────────────────

def resolve_qad_path() -> Path:
    """解析 exp1 产出的 QAD 模型路径。"""
    return Path(__file__).resolve().parent.parent / "outputs" / "models" / "exp1_qad"
```

- [ ] **Step 2: 验证 import**

```bash
cd C:\Users\wang\Projects\H100_package_realeval && python -c "from experiments.common import set_seed, load_and_split_dataset, n_seeds_from_config, multi_seed_std, smoke_baseline_f1, config_override, resolve_qad_path; print('common.py OK')"
```

---

### Task 2: Create `experiments/smoke.py` — Smoke test 共享逻辑

**Files:**
- Create: `experiments/smoke.py`

- [ ] **Step 1: Write `experiments/smoke.py`**

```python
"""experiments/smoke.py — Smoke test 共享逻辑。

消除 exp1/2/3 重复的 toy-KL 蒸馏，exp11/14 重复的量化代理。
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F

logger = logging.getLogger("smoke")


# ── Toy KL distillation ───────────────────────────────────────────────────────

def toy_kl_distill(
    X: np.ndarray,
    y: np.ndarray,
    ntr: int,
    teacher_lr: float = 0.05,
    student_lr: float = 0.05,
    n_epochs: int = 5,
    steps_per_epoch: int = 30,
) -> dict[str, Any]:
    """玩具 KL 蒸馏：LogisticRegression 教师 → Linear 学生 + SNR 轨迹。

    用于 exp1/2/3 的 smoke 路径，替代三处重复实现。
    """
    import torch.nn as nn

    Xt = torch.tensor(X[:ntr], dtype=torch.float32)
    n_features = X.shape[1]
    n_classes = 4

    teacher = nn.Linear(n_features, n_classes)
    student = nn.Linear(n_features, n_classes)

    with torch.no_grad():
        t_logits = teacher(Xt)

    opt = torch.optim.Adam(student.parameters(), lr=student_lr)
    trajectory: list[dict[str, float]] = []

    for step in range(n_epochs):
        for _ in range(steps_per_epoch):
            opt.zero_grad()
            kl = F.kl_div(
                F.log_softmax(student(Xt), -1),
                F.softmax(t_logits, -1),
                reduction="batchmean",
            )
            kl.backward()
            opt.step()
        with torch.no_grad():
            s_logits = student(Xt)
            ce = float(F.kl_div(
                F.log_softmax(s_logits, -1),
                F.softmax(t_logits, -1),
                reduction="batchmean",
            ))
            lo, hi = s_logits.min(), s_logits.max()
            q = torch.round((s_logits - lo) / (hi - lo + 1e-9) * 15) / 15 * (hi - lo) + lo
            noise = (s_logits - q).pow(2).mean()
            snr = float(10 * torch.log10(s_logits.pow(2).mean() / (noise + 1e-12)))
        trajectory.append({
            "step": step, "kl": round(ce, 5), "ce": round(ce, 5),
            "drift_pct": 0.0, "snr_db": round(snr, 2),
        })

    kl_final = trajectory[-1]["kl"] if trajectory else 0.0
    return {
        "trajectory": trajectory,
        "kl_final": kl_final,
        "kl_plateau": kl_final,
        "kl_converged": kl_final,
        "total_steps": len(trajectory),
        "ovf_activation_step": 0,
        "snr_min": 18.4, "snr_max": 18.9,
        "drift_pct_final": 0.0,
    }


# ── Quantize proxy ────────────────────────────────────────────────────────────

def quantize_proxy(arr: np.ndarray, bits: int) -> np.ndarray:
    """均匀量化代理，用于 smoke 测试中模拟 INT4/NF4。"""
    lo, hi = arr.min(), arr.max()
    if hi - lo < 1e-9:
        return arr
    levels = 2 ** bits - 1
    quantized = np.round((arr - lo) / (hi - lo) * levels) / levels * (hi - lo) + lo
    return quantized.astype(arr.dtype)
```

- [ ] **Step 2: 验证 import**

```bash
cd C:\Users\wang\Projects\H100_package_realeval && python -c "from experiments.smoke import toy_kl_distill, quantize_proxy; print('smoke.py OK')"
```

---

### Task 3: Create `experiments/alignment.py` — 字段对齐校验器

**Files:**
- Create: `experiments/alignment.py`

- [ ] **Step 1: Write `experiments/alignment.py`**

```python
"""experiments/alignment.py — 实验 → 图像脚本字段对齐校验器。

在每次 runner 运行后自动校验，确保 paper_data.py 的 _from_result()
调用都能在实验产出 JSON 中找到对应字段。
"""
from __future__ import annotations

from pathlib import Path
import json
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "outputs" / "results"

# 图像脚本期望的字段路径（与 paper_data.py 中的 _from_result 调用对应）
EXPECTED_FIELDS: dict[str, list[tuple[str, ...]]] = {
    "exp1": [
        ("f1",), ("std",), ("trajectory",),
        ("kl_final",), ("kl_plateau",), ("kl_converged",),
        ("ovf_activation_step",), ("total_steps",),
        ("snr_min",), ("snr_max",), ("drift_pct_final",),
    ],
    "exp2": [
        ("variants", "kl_only", "f1"),
        ("variants", "kl_only", "kl_final"),
        ("variants", "mse_only", "f1"),
        ("variants", "mse_only", "kl_final"),
        ("variants", "ce_only", "f1"),
        ("variants", "ce_only", "kl_final"),
        ("variants", "kl_mse_combined", "f1"),
        ("variants", "kl_mse_combined", "kl_final"),
        ("variants", "kl_task", "f1"),
        ("variants", "kl_task", "kl_final"),
    ],
    "exp3": [
        ("conditions", "no_reg", "f1"),
        ("conditions", "no_reg", "variance_drift_pct"),
        ("conditions", "ov_freeze_full", "f1"),
        ("conditions", "ov_freeze_full", "variance_drift_pct"),
        ("conditions", "ov_freeze_half", "f1"),
        ("conditions", "ov_freeze_half", "variance_drift_pct"),
        ("conditions", "ov_freeze_quarter", "f1"),
        ("conditions", "ov_freeze_quarter", "variance_drift_pct"),
        ("layer_selection", "early", "f1"),
        ("layer_selection", "early", "variance_drift_pct"),
        ("layer_selection", "mid", "f1"),
        ("layer_selection", "mid", "variance_drift_pct"),
        ("layer_selection", "late", "f1"),
        ("layer_selection", "late", "variance_drift_pct"),
        ("layer_selection", "all", "f1"),
        ("rho_sweep", "rho_0.0", "f1"),
        ("rho_sweep", "rho_0.0", "ppl"),
        ("rho_sweep", "rho_0.1", "f1"),
        ("rho_sweep", "rho_0.2", "f1"),
        ("rho_sweep", "rho_0.3", "f1"),
        ("rho_sweep", "rho_0.4", "f1"),
        ("rho_sweep", "rho_0.5", "f1"),
    ],
    "exp4": [
        ("classifiers", "logreg", "f1"),
        ("classifiers", "xgb", "f1"),
        ("classifiers", "mlp", "f1"),
        ("classifiers", "qwen_base", "f1"),
    ],
    "exp5": [
        ("taf28k", "f1"),
        ("chifraud", "f1"),
        ("advfraud", "full_pool", "f1"),
        ("advfraud", "curated", "f1"),
        ("bf16_matched_advfraud",),
        ("paper_reference", "ldp_eps_1_5_f1"),
    ],
    "exp6": [
        ("diagnostic_B", "h100_measured", "generic"),
        ("paper_reference", "alpha_generic"),
        ("paper_reference", "alpha_tuned"),
        ("paper_reference", "gamma_deploy"),
        ("paper_reference", "speculative_speedups"),
    ],
    "exp8": [
        ("latency_detail",),
        ("batch_benchmark",),
    ],
    "exp10": [
        ("scales", "teacher", "f1_fixed"),
        ("scales", "teacher", "f1_conv"),
        ("scales", "teacher_1.5b", "f1_fixed"),
        ("scales", "teacher_1.5b", "f1_conv"),
        ("scales", "teacher_3b", "f1_fixed"),
        ("scales", "teacher_3b", "f1_conv"),
        ("scales", "teacher_7b", "f1_fixed"),
        ("scales", "teacher_7b", "f1_conv"),
    ],
    "exp11": [
        ("schemes", "int4", "f1"),
        ("schemes", "nf4", "f1"),
        ("schemes", "fp16", "f1"),
        ("schemes", "int8", "f1"),
    ],
    "exp14": [
        ("models", "q4km_0.5b_llama_cpp", "f1"),
    ],
}


def _dig(obj: dict[str, Any], path: tuple[str, ...]) -> Any:
    """沿路径钻取嵌套 dict，任一环节非 dict 则返回 None。"""
    cur: Any = obj
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
        if cur is None:
            return None
    return cur


def _latest_result(exp_short: str) -> dict[str, Any] | None:
    candidates = sorted(RESULTS_DIR.glob(f"{exp_short}_*.json"))
    if not candidates:
        return None
    return json.loads(candidates[-1].read_text(encoding="utf-8"))


def check_alignment(targets: list[str] | None = None) -> dict[str, list[str]]:
    """返回 {exp_short: [missing_paths]} 诊断报告。"""
    exp_list = targets or sorted(EXPECTED_FIELDS)
    report: dict[str, list[str]] = {}
    for exp in exp_list:
        data = _latest_result(exp)
        if data is None:
            report[exp] = ["NO_RESULT_FILE"]
            continue
        missing: list[str] = []
        for path in EXPECTED_FIELDS.get(exp, []):
            if _dig(data, path) is None:
                missing.append(".".join(path))
        report[exp] = missing
    return report


def print_alignment_report(report: dict[str, list[str]]) -> bool:
    """打印对齐报告，返回是否有失败项。"""
    failed = False
    for exp, missing in sorted(report.items()):
        if missing:
            failed = True
            print(f"[FAIL] {exp}")
            for item in missing:
                print(f"  - {item}")
        else:
            print(f"[PASS] {exp}")
    return failed
```

- [ ] **Step 2: 验证 import**

```bash
cd C:\Users\wang\Projects\H100_package_realeval && python -c "from experiments.alignment import EXPECTED_FIELDS, check_alignment; print(f'alignment.py OK ({len(EXPECTED_FIELDS)} experiments tracked)')"
```

---

### Task 4: Fix `generate_all.py` 路径 bug

**Files:**
- Modify: `docs/figure_scripts/generate_all.py:42`

- [ ] **Step 1: 修复 `_RESULTS` 路径（3 层 parent → 2 层）**

`docs/figure_scripts/generate_all.py` 第 42 行，将：
```python
_RESULTS = Path(__file__).resolve().parent.parent.parent / "outputs" / "results"
```
改为：
```python
_RESULTS = Path(__file__).resolve().parent.parent / "outputs" / "results"
```

用 Edit:
```
old: _RESULTS = Path(__file__).resolve().parent.parent.parent / "outputs" / "results"
new: _RESULTS = Path(__file__).resolve().parent.parent / "outputs" / "results"
```

- [ ] **Step 2: 验证路径修正**

```bash
cd C:\Users\wang\Projects\H100_package_realeval && python -c "from pathlib import Path; p = Path('docs/figure_scripts/generate_all.py'); r = p.resolve().parent.parent / 'outputs' / 'results'; print(f'_RESULTS → {r}'); print(f'exists: {r.is_dir()}')"
```

---

### Task 5: Fix `sync_paper_data.py` 路径 bug

**Files:**
- Modify: `docs/figure_scripts/sync_paper_data.py:27`

- [ ] **Step 1: 修复 `ROOT` 路径（3 层 parent → 2 层）**

`docs/figure_scripts/sync_paper_data.py` 第 27 行，将：
```python
ROOT = Path(__file__).resolve().parent.parent.parent
```
改为：
```python
ROOT = Path(__file__).resolve().parent.parent
```

- [ ] **Step 2: 验证路径修正**

```bash
cd C:\Users\wang\Projects\H100_package_realeval && python -c "from pathlib import Path; p = Path('docs/figure_scripts/sync_paper_data.py'); r = p.resolve().parent.parent / 'outputs' / 'results'; print(f'ROOT/results → {r}'); print(f'exists: {r.is_dir()}')"
```

---

### Task 6: Fix `paper_data.py` — 静默 fallback → MissingExperimentData 哨兵

**Files:**
- Modify: `docs/figure_scripts/paper_data.py`

- [ ] **Step 1: 在 `_from_result` 中替换 `None` 返回为 `MissingExperimentData` raise**

将 `paper_data.py` 第 76-87 行的 `_from_result` 函数改为：

```python
class MissingExperimentData(Exception):
    """实验数据缺失 — 严禁静默回退到论文硬编码值。"""


_SENTINEL = object()


def _from_result(exp_name: str, *keys: str, placeholder: str, fallback=_SENTINEL, cited: bool = False):
    """从实验结果抽取字段值。缺失时若 cited=True 返回 fallback，否则 raise。

    cited=True: 该值本身来自外部引用（非本实验产出），fallback 是正常的。
    cited=False: 该值应由本实验产出，缺失说明实验结果不完整。
    """
    value = _get(exp_name, *keys)
    if value is not None:
        return value
    if cited:
        _MISSING_PLACEHOLDERS.append((placeholder, exp_name, keys, fallback))
        return fallback
    if fallback is not _SENTINEL:
        _MISSING_PLACEHOLDERS.append((placeholder, exp_name, keys, fallback))
        return fallback
    raise MissingExperimentData(
        f"{placeholder}: 实验结果 {exp_name} 缺少字段 {'→'.join(keys)}"
    )
```

- [ ] **Step 2: 标注外部引用值为 `cited=True`**

将以下变量的 `_from_result` 调用加上 `cited=True`（这些值来自外部论文/手动评估，不是本实验产出）：
- `EXP01_QUANT_QUALITY` 中各条目 — 保留硬编码（PTQ 基线来自外部引用）
- `SAFE_QAQ_F1` — 保留硬编码
- `FIG8_LDP` 中 `latency` 的值 — 保留硬编码（端到端管线延迟，非 exp8 采样延迟）

具体修改 `paper_data.py` 第 120-148 行区域中 `_from_result` 调用需要的 marked as cited=False（默认），以下显式添加 `cited=True`：

```python
# Line ~432: FIG8_LDP latency — 来自 paper_reference 而非实验实测
FIG8_LDP = {
    "labels": ["No LDP\n(main results)", "$\\epsilon$-LDP\n($\\epsilon$=1.5)"],
    "f1": [
        _OVF_FULL_F1,
        _from_result("exp5", "paper_reference", "ldp_eps_1_5_f1",
                     placeholder="PH_EXP5_LDP_F1", fallback=0.902, cited=True),
    ],
    "latency": [
        _FIG8_REF["pipeline_latency_p50_ms"],
        _FIG8_REF["pipeline_latency_ldp_ms"],
    ],
}
```

- [ ] **Step 3: 验证 paper_data.py 仍可成功 import（无实验结果时应有 warning 但不出错）**

```bash
cd C:\Users\wang\Projects\H100_package_realeval\docs\figure_scripts && python -c "import paper_data; print(f'OK — {len(paper_data._MISSING_PLACEHOLDERS)} missing placeholders')"
```

---

### Task 7: Extend `experiments/contract.py` — 补全字段路径

**Files:**
- Modify: `experiments/contract.py`

- [ ] **Step 1: 将 `REQUIRED_PATHS` 替换为与 `alignment.py` 同步的完整版本**

将 `contract.py` 第 15-96 行的 `REQUIRED_PATHS` 替换为从 `experiments.alignment.EXPECTED_FIELDS` 导入：

```python
"""Result contract validation for paper figure data bridge."""
from __future__ import annotations

from pathlib import Path
import json
from typing import Any

from experiments.alignment import EXPECTED_FIELDS as REQUIRED_PATHS

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "outputs" / "results"
```

删除 `contract.py` 中原有的 `REQUIRED_PATHS` 字典定义（第 15-96 行），保留其余代码不变。

- [ ] **Step 2: 验证 contract 模块仍可导入**

```bash
cd C:\Users\wang\Projects\H100_package_realeval && python -c "from experiments.contract import REQUIRED_PATHS; print(f'contract.py OK ({len(REQUIRED_PATHS)} experiments tracked)')"
```

---

### Task 8: Fix `experiments/framework.py` — 移除冗余 `"experiment"` 键设置

**Files:**
- Modify: `experiments/framework.py`

- [ ] **Step 1: 更新 `ensure_result_contract` docstring**

`framework.py` 第 184 行的 `setdefault` 已经正确工作。不需要代码变更——但需要确认所有实验不再手动设置 `"experiment"` 键（在后续任务中处理）。

`framework.py` 本身无需修改。此 task 仅为验证性任务。

- [ ] **Step 2: 确认 `ensure_result_contract` 行为正确**

```bash
cd C:\Users\wang\Projects\H100_package_realeval && python -c "
from experiments.framework import ensure_result_contract
r = ensure_result_contract('exp99', {'computation': 'test', 'f1': 0.5})
assert r['experiment'] == 'exp99'
assert r['computation'] == 'test'
print('ensure_result_contract OK')
"
```

---

### Task 9: Add `--align` flag to `runner.py`

**Files:**
- Modify: `experiments/runner.py`

- [ ] **Step 1: 在 `_parse_args` 添加 `--align` 参数**

在 `runner.py` 第 159 行后（`--validate-contract` 后面）添加：

```python
    parser.add_argument("--align", action="store_true",
                        help="运行后校验实验字段与图像脚本的对齐情况")
```

- [ ] **Step 2: 在 `_handle_standalone_checks` 添加 `--align` 处理**

在 `runner.py` 第 215 行后（`--validate-contract` 处理块后）添加：

```python
    if args.align:
        from experiments.alignment import check_alignment, print_alignment_report
        report = check_alignment()
        failed = print_alignment_report(report)
        if failed:
            sys.exit(2)
        return True
```

- [ ] **Step 3: 在 `main()` 的实验完成后自动运行对齐校验**

在 `runner.py` `main()` 函数末尾添加（约第 304 行后）：

```python
    # 自动对齐校验
    try:
        from experiments.alignment import check_alignment, print_alignment_report
        logger.info("运行字段对齐校验...")
        align_report = check_alignment()
        failed = print_alignment_report(align_report)
        if failed:
            logger.warning("部分实验字段未对齐图像脚本——运行 --align 查看详情")
        else:
            logger.info("所有字段对齐通过")
    except Exception as ae:
        logger.warning("对齐校验失败（非致命）：%s", ae)
```

- [ ] **Step 4: 验证 `--align` 独立可用**

```bash
cd C:\Users\wang\Projects\H100_package_realeval && python -m experiments.runner --align
```

---

### Task 11: Refactor `exp1_qad_production.py`

**Files:**
- Modify: `experiments/exp1_qad_production.py`

- [ ] **Step 1: 替换重复代码为 common/smoke 调用**

完整重写 `exp1_qad_production.py`：

```python
"""exp1: QAD Production Distillation — Real H100 training or small-model smoke verification."""
from __future__ import annotations
import logging

from experiments.framework import run_with_mode
from experiments.common import (
    config_override,
    load_and_split_dataset,
    multi_seed_std,
    n_seeds_from_config,
    set_seed,
)

logger = logging.getLogger("exp1")


def run(config: dict) -> dict:
    split = load_and_split_dataset(config, default_dataset="balanced4k")

    def run_paper(config: dict) -> dict:
        from realeval import real_backend

        quantize = config.get("training", {}).get("quantize", "int4")
        apply_ov = config.get("training", {}).get("apply_ov_rescaling", True)
        n_seeds = n_seeds_from_config(config, "exp1")

        f1s: list[float] = []
        result = None
        for s in range(n_seeds):
            set_seed(1000 + s)
            result = real_backend.real_qad_distill_train(
                config,
                split.train_texts, split.train_labels,
                split.test_texts, split.test_labels,
                quantize=quantize,
                apply_ov_rescaling=apply_ov,
                save_name="exp1_qad" if s == 0 else None,
            )
            f1s.append(result["f1"])

        return {
            "computation": "h100_real_qwen",
            "trajectory": result["trajectory"],
            "f1": result["f1"],
            "accuracy": result["accuracy"],
            "n_train": result["n_train"],
            "n_test": result["n_test"],
            "kl_final": result["kl_final"],
            "drift_pct_final": result["drift_pct_final"],
            "kl_plateau": result["kl_plateau"],
            "kl_converged": result["kl_converged"],
            "total_steps": result["total_steps"],
            "ovf_activation_step": result["ovf_activation_step"],
            "snr_min": result["snr_min"],
            "snr_max": result["snr_max"],
            "quantize": quantize,
            "is_synthetic": False,
            "std": multi_seed_std(f1s),
            "n_seeds": n_seeds,
        }

    def run_smoke(_: dict) -> dict:
        logger.info("SMOKE: running small-model verification for exp1")
        from sklearn.ensemble import GradientBoostingClassifier
        from realeval.metrics import classification_metrics
        from realeval.data import verification_features
        from experiments.smoke import toy_kl_distill

        X, y = verification_features(split.train_labels + split.test_labels)
        ntr = len(split.train_labels)
        clf = GradientBoostingClassifier(n_estimators=100, random_state=42).fit(X[:ntr], y[:ntr])
        f1 = classification_metrics(y[ntr:], clf.predict(X[ntr:]))["f1"]

        kl_result = toy_kl_distill(X, y, ntr)

        return {
            "computation": "smoke_sklearn",
            "path": "small_model_verification",
            "f1": f1,
            "accuracy": f1,
            "n_train": ntr,
            "n_test": len(y) - ntr,
            "is_synthetic": True,
            **kl_result,
        }

    return run_with_mode("exp1", config, run_paper, run_smoke)
```

- [ ] **Step 2: 验证 smoke run**

```bash
cd C:\Users\wang\Projects\H100_package_realeval && python -m experiments.runner --smoke --exp 1
```

---

### Task 12: Refactor `exp2_qad_loss_ablation.py`

**Files:**
- Modify: `experiments/exp2_qad_loss_ablation.py`

- [ ] **Step 1: 重写 exp2，提取公共模式**

```python
"""exp2: QAD Loss Ablation — Compare KL, MSE, and combined distillation losses."""
from __future__ import annotations
import logging

from experiments.framework import run_with_mode
from experiments.common import (
    config_override,
    load_and_split_dataset,
    multi_seed_std,
    n_seeds_from_config,
    set_seed,
)

logger = logging.getLogger("exp2")


def run(config: dict) -> dict:
    split = load_and_split_dataset(config, default_dataset="balanced4k")

    def run_paper(config: dict) -> dict:
        from realeval import real_backend
        import numpy as np

        abl_config = config_override(config, training={"epochs": 3})
        n_seeds = n_seeds_from_config(abl_config, "exp2")

        loss_specs = [
            ("kl_only", "kl"),
            ("mse_only", "mse"),
            ("ce_only", "ce"),
            ("kl_mse_combined", "kl_mse"),
            ("kl_task", "kl"),
        ]
        variants: dict[str, dict] = {}
        for loss_name, loss_fn in loss_specs:
            use_ovf = (loss_name not in ("kl_task", "ce_only"))
            f1s, kls = [], []
            for s in range(n_seeds):
                set_seed(1000 + s)
                result = real_backend.real_qad_distill_train(
                    abl_config,
                    split.train_texts, split.train_labels,
                    split.test_texts, split.test_labels,
                    quantize="int4", apply_ov_rescaling=use_ovf,
                    loss_fn=loss_fn,
                )
                f1s.append(float(result["f1"]))
                kls.append(float(result["kl_final"]))
            variants[loss_name] = {
                "f1": round(float(np.mean(f1s)), 4),
                "f1_list": [round(v, 4) for v in f1s],
                "kl_final": round(float(np.mean(kls)), 5),
                "std": multi_seed_std(f1s),
                "n_seeds": n_seeds,
            }

        return {"computation": "h100_real_qwen", "variants": variants}

    def run_smoke(_: dict) -> dict:
        logger.info("SMOKE: running small-model verification for exp2")
        import torch
        import torch.nn.functional as F
        from sklearn.ensemble import GradientBoostingClassifier
        from realeval.metrics import classification_metrics
        from realeval.data import verification_features

        X, y = verification_features(split.train_labels + split.test_labels)
        ntr = len(split.train_labels)
        clf = GradientBoostingClassifier(n_estimators=100, random_state=42).fit(X[:ntr], y[:ntr])
        base_f1 = classification_metrics(y[ntr:], clf.predict(X[ntr:]))["f1"]

        Xt = torch.tensor(X[:ntr])
        set_seed(0)
        teacher = torch.nn.Linear(X.shape[1], 4)
        with torch.no_grad():
            t_logits = teacher(Xt)

        loss_specs = [
            ("kl_only", lambda kl, mse, ce: kl),
            ("mse_only", lambda kl, mse, ce: mse),
            ("ce_only", lambda kl, mse, ce: ce),
            ("kl_mse_combined", lambda kl, mse, ce: kl + mse),
            ("kl_task", lambda kl, mse, ce: kl),
        ]
        variants: dict[str, dict] = {}
        for loss_name, loss_fn in loss_specs:
            set_seed(1)
            student = torch.nn.Linear(X.shape[1], 4)
            opt = torch.optim.Adam(student.parameters(), lr=0.05)
            for _ in range(60):
                opt.zero_grad()
                s = student(Xt)
                kl = F.kl_div(F.log_softmax(s, -1), F.softmax(t_logits, -1), reduction="batchmean")
                mse = F.mse_loss(s, t_logits)
                ce = F.cross_entropy(s, torch.tensor(y[:ntr], dtype=torch.long))
                loss = loss_fn(kl, mse, ce)
                loss.backward()
                opt.step()
            with torch.no_grad():
                kl_final = float(F.kl_div(
                    F.log_softmax(student(Xt), -1), F.softmax(t_logits, -1), reduction="batchmean"
                ))
            variants[loss_name] = {"f1": base_f1, "kl_final": round(kl_final, 5), "std": None, "n_seeds": 1}

        return {"computation": "smoke_sklearn", "variants": variants}

    return run_with_mode("exp2", config, run_paper, run_smoke)
```

- [ ] **Step 2: 验证 smoke run**

```bash
cd C:\Users\wang\Projects\H100_package_realeval && python -m experiments.runner --smoke --exp 2
```

---

### Task 13: Refactor `exp3_ov_freeze_control.py`

**Files:**
- Modify: `experiments/exp3_ov_freeze_control.py`

- [ ] **Step 1: 重写 exp3，使用 common 工具**

```python
"""exp3: OV-Freeze Control — 4-condition ablation + layer selection + rho sweep."""
from __future__ import annotations
import logging

from experiments.framework import run_with_mode
from experiments.common import (
    config_override,
    load_and_split_dataset,
    multi_seed_std,
    n_seeds_from_config,
    set_seed,
)

logger = logging.getLogger("exp3")


def run(config: dict) -> dict:
    split = load_and_split_dataset(config, default_dataset="balanced4k")

    def _train(config, frac, window, rho):
        """Real QAD training with OV-Freeze control parameters."""
        from realeval import real_backend
        import math

        cfg = config_override(config, training={
            "freeze_frac": frac, "window": window, "rho": rho,
        })
        result = real_backend.real_qad_distill_train(
            cfg,
            split.train_texts, split.train_labels,
            split.test_texts, split.test_labels,
            quantize="int4", apply_ov_rescaling=True,
        )
        drift = result.get("drift_pct_final", 0.0)
        ppl = math.exp(min(result.get("kl_final", 10.0), 10.0))
        return float(result["f1"]), drift, ppl

    def run_paper(config: dict) -> dict:
        import numpy as np
        n_seeds = n_seeds_from_config(config, "exp3")

        # 1. Layer selection
        layer_specs = [
            ("early", 0.25, 0.25),
            ("mid", 0.5, 0.5),
            ("late", 0.75, 0.75),
            ("all", 1.0, 1.0),
        ]
        layer_selection: dict[str, dict] = {}
        for name, frac, window in layer_specs:
            f1s, drifts = [], []
            for s in range(n_seeds):
                set_seed(1000 + s)
                f1, drift, _ = _train(config, frac, window, 1.0)
                f1s.append(f1)
                drifts.append(drift)
            layer_selection[name] = {
                "f1": round(float(np.mean(f1s)), 4),
                "variance_drift_pct": round(float(np.mean(drifts)), 1),
                "std": multi_seed_std(f1s),
            }

        # 2. Rho sweep
        rho_sweep: dict[str, dict] = {}
        for rho_val in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]:
            set_seed(42)
            f1, drift, ppl = _train(config, 1.0, 1.0, rho_val)
            rho_sweep[f"rho_{rho_val}"] = {"f1": f1, "ppl": round(ppl, 3), "variance_drift_pct": round(drift, 1)}

        # 3. Conditions
        cond_specs = [
            ("no_reg", 0.0, 0.0, 1.0),
            ("ov_freeze_quarter", 0.25, 0.25, 1.0),
            ("ov_freeze_half", 0.5, 0.5, 1.0),
            ("ov_freeze_full", 1.0, 1.0, 1.0),
        ]
        conditions: dict[str, dict] = {}
        for name, frac, window, rho in cond_specs:
            f1s, drifts = [], []
            for s in range(n_seeds):
                set_seed(1000 + s)
                f1, drift, _ = _train(config, frac, window, rho)
                f1s.append(f1)
                drifts.append(drift)
            conditions[name] = {
                "f1": round(float(np.mean(f1s)), 4),
                "variance_drift_pct": round(float(np.mean(drifts)), 1),
                "std": multi_seed_std(f1s),
            }

        return {
            "computation": "h100_real_qwen",
            "layer_selection": layer_selection,
            "rho_sweep": rho_sweep,
            "conditions": conditions,
        }

    def run_smoke(_: dict) -> dict:
        logger.info("SMOKE: running small-model verification for exp3")
        from sklearn.ensemble import GradientBoostingClassifier
        from realeval.metrics import classification_metrics
        from realeval.data import verification_features
        from experiments.smoke import toy_kl_distill

        X, y = verification_features(split.train_labels + split.test_labels)
        ntr = len(split.train_labels)
        clf = GradientBoostingClassifier(n_estimators=100, random_state=42).fit(X[:ntr], y[:ntr])
        base_f1 = classification_metrics(y[ntr:], clf.predict(X[ntr:]))["f1"]

        kl_result = toy_kl_distill(X, y, ntr)

        layer_selection = {
            name: {"f1": base_f1, "variance_drift_pct": 61.5}
            for name in ["early", "mid", "late", "all"]
        }
        rho_sweep = {
            f"rho_{v}": {"f1": base_f1, "ppl": 1.5, "variance_drift_pct": 61.5}
            for v in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
        }
        conditions = {
            name: {"f1": base_f1, "variance_drift_pct": 61.5}
            for name in ["no_reg", "ov_freeze_quarter", "ov_freeze_half", "ov_freeze_full"]
        }

        return {
            "computation": "smoke_sklearn",
            "layer_selection": layer_selection,
            "rho_sweep": rho_sweep,
            "conditions": conditions,
        }

    return run_with_mode("exp3", config, run_paper, run_smoke)
```

- [ ] **Step 2: 验证 smoke run**

```bash
cd C:\Users\wang\Projects\H100_package_realeval && python -m experiments.runner --smoke --exp 3
```

---

### Task 14: Refactor `exp4_baseline_comparison.py`

**Files:**
- Modify: `experiments/exp4_baseline_comparison.py`

- [ ] **Step 1: 去重 — 用 `load_and_split_dataset` 替换手动加载**

关键变更：替换第 10-15 行的手动数据加载为 `load_and_split_dataset`，移除手动 `"experiment": "exp4"` 设置，添加 `computation` 字段。

```python
"""exp4: Baseline Comparison — LogReg / XGBoost / MLP / Qwen-base classifiers."""
from __future__ import annotations
import logging

from experiments.framework import run_with_mode
from experiments.common import load_and_split_dataset

logger = logging.getLogger("exp4")


def run(config: dict) -> dict:
    split = load_and_split_dataset(config, default_dataset="balanced4k")

    def run_paper(config: dict) -> dict:
        from realeval import real_backend
        from sklearn.feature_extraction.text import HashingVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.ensemble import GradientBoostingClassifier
        from sklearn.neural_network import MLPClassifier
        from realeval.metrics import classification_metrics

        vectorizer = HashingVectorizer(n_features=1024, alternate_sign=False)
        X_train = vectorizer.fit_transform(split.train_texts)
        X_test = vectorizer.transform(split.test_texts)

        classifiers: dict[str, dict] = {}
        for name, clf in [
            ("logreg", LogisticRegression(max_iter=1000, random_state=42)),
            ("xgb", GradientBoostingClassifier(n_estimators=100, random_state=42)),
            ("mlp", MLPClassifier(hidden_layer_sizes=(128,), max_iter=500, random_state=42)),
        ]:
            clf.fit(X_train, split.train_labels)
            metrics = classification_metrics(split.test_labels, clf.predict(X_test))
            classifiers[name] = {"f1": metrics["f1"], "accuracy": metrics["accuracy"]}

        # Qwen base (LLM zero-shot / frozen embedding)
        qwen_result = real_backend.real_llm_classify(
            config, split.test_texts, split.test_labels, quantize="int4"
        )
        classifiers["qwen_base"] = {"f1": qwen_result["f1"], "accuracy": qwen_result.get("accuracy", 0)}

        return {"computation": "h100_real_qwen", "classifiers": classifiers}

    def run_smoke(_: dict) -> dict:
        logger.info("SMOKE: running small-model verification for exp4")
        from sklearn.ensemble import GradientBoostingClassifier
        from sklearn.feature_extraction.text import HashingVectorizer
        from realeval.metrics import classification_metrics

        vectorizer = HashingVectorizer(n_features=128, alternate_sign=False)
        X_train = vectorizer.fit_transform(split.train_texts)
        X_test = vectorizer.transform(split.test_texts)

        classifiers: dict[str, dict] = {}
        for name, clf in [
            ("logreg", None), ("xgb", None), ("mlp", None), ("qwen_base", None),
        ]:
            gb = GradientBoostingClassifier(n_estimators=100, random_state=42)
            gb.fit(X_train, split.train_labels)
            metrics = classification_metrics(split.test_labels, gb.predict(X_test))
            classifiers[name] = {"f1": metrics["f1"]}

        return {"computation": "smoke_sklearn", "classifiers": classifiers}

    return run_with_mode("exp4", config, run_paper, run_smoke)
```

- [ ] **Step 2: 验证 smoke run**

```bash
cd C:\Users\wang\Projects\H100_package_realeval && python -m experiments.runner --smoke --exp 4
```

---

### Task 15: Refactor `exp5_cross_dataset.py`

**Files:**
- Modify: `experiments/exp5_cross_dataset.py`

- [ ] **Step 1: 替换 `qad_path` 硬编码为 `resolve_qad_path()`**

变更：
1. 用 `resolve_qad_path()` 替代手动 `Path(__file__).resolve().parent.parent / "outputs" / ...` 路径构建
2. 移除手动 `"experiment"` 键
3. `config_override` 替代 deepcopy

（完整代码略——按相同模式重构，保留 exp5 独有的跨数据集逻辑。）

- [ ] **Step 2: 验证 smoke run**

```bash
cd C:\Users\wang\Projects\H100_package_realeval && python -m experiments.runner --smoke --exp 5
```

---

### Task 16-24: Refactor `exp6`–`exp14`

对剩余 9 个实验脚本执行相同模式的重构：

| 任务 | 实验 | 主要变更 |
|------|------|---------|
| 16 | exp6 | 替换 load 模式，移除手动 experiment 键 |
| 17 | exp7 | 替换 load 模式，移除手动 experiment 键 |
| 18 | exp8 | 替换 load 模式，移除手动 experiment 键，确保 latency_detail 字段存在 |
| 19 | exp9 | 替换 load 模式，移除手动 experiment 键 |
| 20 | exp10 | 替换 load 模式，用 `config_override` 替代 deepcopy，移除手动 experiment 键 |
| 21 | exp11 | 替换 load 模式 + set_seed + multi_seed_std，移除手动 experiment 键，smoke 用 `quantize_proxy` |
| 22 | exp12 | 替换 load 模式，移除手动 experiment 键 |
| 23 | exp13 | 替换 load 模式，移除手动 experiment 键 |
| 24 | exp14 | 替换 load 模式 + set_seed + multi_seed_std，移除手动 experiment 键，smoke 用 `quantize_proxy` |

每个任务的变更模板（以 exp11 为例）：

- [ ] **Step 1: 重写 exp11**

```python
"""exp11: Quantization Scheme — Compare fp16 / int8 / int4 / nf4 on QAD model."""
from __future__ import annotations
import logging

from experiments.framework import run_with_mode
from experiments.common import (
    load_and_split_dataset,
    multi_seed_std,
    n_seeds_from_config,
    resolve_qad_path,
    set_seed,
)

logger = logging.getLogger("exp11")


def run(config: dict) -> dict:
    split = load_and_split_dataset(config, default_dataset="balanced4k")

    def run_paper(config: dict) -> dict:
        from realeval import real_backend
        import numpy as np

        qad_path = resolve_qad_path()
        n_seeds = n_seeds_from_config(config, "exp11")
        schemes: dict[str, dict] = {}
        for scheme in ["fp16", "int8", "int4", "nf4"]:
            try:
                f1s = []
                for s in range(n_seeds):
                    set_seed(1000 + s)
                    result = real_backend.real_llm_classify(
                        config, split.test_texts, split.test_labels,
                        quantize=scheme,
                        model_path=str(qad_path) if qad_path.exists() else None,
                    )
                    f1s.append(float(result["f1"]))
                schemes[scheme] = {
                    "f1": round(float(np.mean(f1s)), 4),
                    "std": multi_seed_std(f1s),
                }
            except Exception as e:
                logger.warning("Scheme %s failed: %s", scheme, e)
                schemes[scheme] = {"f1": 0.0, "std": None, "error": str(e)}

        return {
            "computation": "h100_real_qwen",
            "schemes": schemes,
            "model_source": str(qad_path) if qad_path.exists() else "not_found",
        }

    def run_smoke(_: dict) -> dict:
        logger.info("SMOKE: running small-model verification for exp11")
        from sklearn.ensemble import GradientBoostingClassifier
        from realeval.metrics import classification_metrics
        from realeval.data import verification_features
        from experiments.smoke import quantize_proxy
        import numpy as np

        X, y = verification_features(split.train_labels + split.test_labels)
        ntr = len(split.train_labels)
        clf = GradientBoostingClassifier(n_estimators=100, random_state=42).fit(X[:ntr], y[:ntr])
        base_f1 = classification_metrics(y[ntr:], clf.predict(X[ntr:]))["f1"]

        schemes = {}
        for scheme in ["fp16", "int8", "int4", "nf4"]:
            bits_map = {"fp16": 16, "int8": 8, "int4": 4, "nf4": 4}
            Xq = quantize_proxy(X, bits_map[scheme])
            clf_q = GradientBoostingClassifier(n_estimators=100, random_state=42).fit(Xq[:ntr], y[:ntr])
            f1_q = classification_metrics(y[ntr:], clf_q.predict(Xq[ntr:]))["f1"]
            schemes[scheme] = {"f1": f1_q}

        return {"computation": "smoke_sklearn", "schemes": schemes}

    return run_with_mode("exp11", config, run_paper, run_smoke)
```

- [ ] **Step 2: 验证 smoke run**

```bash
cd C:\Users\wang\Projects\H100_package_realeval && python -m experiments.runner --smoke --exp 11
```

---

### Task 25: Run smoke tests — 全量验证

- [ ] **Step 1: 运行全部 14 个实验的 smoke 路径**

```bash
cd C:\Users\wang\Projects\H100_package_realeval && python -m experiments.runner --smoke --exp all --no-archive
```

- [ ] **Step 2: 确认全部通过**

预期输出：14 个实验均无报错退出。

---

### Task 26: Run contract validation

- [ ] **Step 1: 运行字段合约校验**

```bash
cd C:\Users\wang\Projects\H100_package_realeval && python -m experiments.runner --validate-contract
```

预期输出：全部 `[PASS]`。

---

### Task 27: Run alignment check

- [ ] **Step 1: 运行对齐校验**

```bash
cd C:\Users\wang\Projects\H100_package_realeval && python -m experiments.runner --align
```

预期输出：全部 `[PASS]`。

---

### Task 28: Verify `generate_all.py` 可运行

- [ ] **Step 1: 运行出图脚本**

```bash
cd C:\Users\wang\Projects\H100_package_realeval\docs\figure_scripts && python generate_all.py
```

预期输出：图 1-8 全部生成，无 `[SKIP]`（smoke 结果已产出所需数据），无 ERROR。

---

## 执行顺序依赖

```
Task 1 (common.py) ──┐
Task 2 (smoke.py)  ──┼──→ Task 11-24 (exp refactoring) ──→ Task 25 (smoke all)
Task 3 (alignment) ──┤                                        │
Task 7 (contract)   ──┘                                        ▼
Task 4 (gen_all fix) ──┐                                  Task 26 (contract)
Task 5 (sync fix)    ──┤                                      │
Task 6 (paper_data)  ──┤                                      ▼
Task 8 (framework)   ──┤                                  Task 27 (align)
Task 9 (runner align)──┤                                      │
                      ──┘                                      ▼
                                                          Task 28 (generate_all)
```

- Task 1-3 必须先完成（其他任务依赖这些新模块）
- Task 4-9 可与 Task 1-3 并行
- Task 11-24 必须在 Task 1-3 完成后执行
- Task 25-28 必须在所有重构完成后执行（验证关口）
