#!/usr/bin/env python
"""
check_alignment.py — 核对绘图脚本与列表所需变量/字段是否与实验产出对齐。

设计原则（对齐项目既定约束）：
  · 图像脚本（fig*.py）与列表数据桥（paper_data.py）的变量/字段必须能从实验产出
    outputs/results/*.json 解析；无法解析时 paper_data 会回退 fallback 并在
    _MISSING_PLACEHOLDERS 中追踪 —— 本工具把“哪些字段缺失/错位”显式列出。
  · 本工具只读不改，不修改任何图像脚本。

用途：每次跑完实验后运行一次，验证字段对齐状态。

    python docs/figure_scripts/check_alignment.py

退出码：0 = 全部对齐；1 = 存在缺失/错位字段或 fig 引用了未定义变量。
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_RESULTS_DIR = _HERE.parent.parent / "outputs" / "results"
_PAPER_DATA = _HERE / "paper_data.py"

# 需要核对 import 的图像/列表脚本
_FIG_SCRIPTS = [
    "fig3_main_results.py",
    "fig5_revision_ablations.py",
    "fig6_loss_teacher_ablation.py",
    "fig7_ovf_ablation.py",
    "fig8_speculative_decoding.py",
]


def load_results() -> dict:
    """与 paper_data._load_results 相同的加载逻辑（同名实验后者覆盖前者）。"""
    by_exp: dict = {}
    if not _RESULTS_DIR.is_dir():
        return by_exp
    for f in sorted(_RESULTS_DIR.glob("exp*_*.json")):
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
            if str(r.get("computation", "")).startswith("smoke"):
                continue  # 与 paper_data._load_results 一致：过滤 smoke 合成结果
            name = r.get("experiment", f.stem.split("_")[0])
            by_exp[name] = r
        except (json.JSONDecodeError, OSError):
            pass
    all_file = _RESULTS_DIR / "all_experiments.json"
    if all_file.exists():
        try:
            for k, v in json.loads(all_file.read_text(encoding="utf-8")).items():
                if str(v.get("computation", "")).startswith("smoke"):
                    continue
                by_exp.setdefault(k, v)
        except Exception:
            pass
    return by_exp


def _get(results: dict, exp_name: str, keys: tuple):
    """按整段 key 遍历（不做点分割——key 可含 '.'，如 teacher_1.5b / rho_0.0）。

    返回 (value, ok)。ok=False 表示：
      · key 不存在；或
      · 路径中途已是标量（如 exp8 扁平 `latencies.int4`=46.47 被当作嵌套路径读取）——
        这是“能解析但错位”的结构中断，必须报出来。
    """
    r = results.get(exp_name, {})
    for i, k in enumerate(keys):
        if isinstance(r, dict) and k in r:
            r = r[k]
        else:
            return None, False
        if not isinstance(r, dict) and i < len(keys) - 1:
            return None, False  # 结构中断：还有剩余 key，但当前已是标量
    return r, True


def extract_from_result_calls(src: str):
    """AST 提取 paper_data.py 中所有 _from_result(...) 调用。"""
    tree = ast.parse(src)
    calls = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "_from_result"):
            try:
                args = [ast.literal_eval(a) for a in node.args]
            except (ValueError, SyntaxError):
                continue
            kw = {}
            for k in node.keywords:
                try:
                    kw[k.arg] = ast.literal_eval(k.value)
                except (ValueError, SyntaxError):
                    kw[k.arg] = "<expr>"
            if args and isinstance(args[0], str):
                calls.append({
                    "exp": args[0],
                    "keys": tuple(args[1:]),
                    "placeholder": kw.get("placeholder"),
                    "fallback": kw.get("fallback"),
                    "line": node.lineno,
                    "cited": kw.get("cited", False),
                })
    return calls


def extract_defined_names(src: str) -> set:
    """paper_data.py 顶层定义的变量名（赋值目标 / import 名）。"""
    tree = ast.parse(src)
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
                elif isinstance(t, (ast.Tuple, ast.List)):
                    for el in t.elts:
                        if isinstance(el, ast.Name):
                            names.add(el.id)
        elif isinstance(node, ast.FunctionDef):
            names.add(node.name)
        elif isinstance(node, ast.ImportFrom):
            names.update(a.asname or a.name for a in node.names)
        elif isinstance(node, ast.Import):
            for a in node.names:
                names.add((a.asname or a.name).split(".")[0])
    return names


def extract_fig_imports(fig_path: Path):
    """某 fig 脚本 from paper_data import (...) 的名字。"""
    try:
        tree = ast.parse(fig_path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return []
    names = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.ImportFrom) and node.module == "paper_data"):
            names.extend(a.asname or a.name for a in node.names)
    return names


def main() -> int:
    if not _PAPER_DATA.is_file():
        print(f"[FATAL] 找不到 {_PAPER_DATA}")
        return 2
    src = _PAPER_DATA.read_text(encoding="utf-8")
    results = load_results()
    calls = extract_from_result_calls(src)
    defined = extract_defined_names(src)

    print(f"实验产出目录 : {_RESULTS_DIR}")
    print(f"已加载实验   : {sorted(results.keys()) if results else '(无)'}")
    print(f"_from_result 调用: {len(calls)} 处\n")

    problems = []
    # ── 1) 字段路径可用性（含结构错位检测） ────────────────────────────
    for c in calls:
        hit, ok = _get(results, c["exp"], c["keys"])
        if not ok:
            key_path = ".".join(c["keys"])
            if hit is not None:
                # 能解析但中途遇到标量/结构中断 → 字段错位（读取到错误值）
                problems.append(f"  - [MISALIGN] {c['placeholder']}: {c['exp']}.{key_path} "
                                f"路径中断（当前值={hit!r}，期望嵌套结构）(line {c['line']})")
            else:
                tag = "cited" if c["cited"] else "MISSING"
                problems.append(f"  - [{tag}] {c['placeholder']}: {c['exp']}.{key_path} 无法解析"
                                f" (line {c['line']}, fallback={c['fallback']})")
    # ── 2) fig 脚本 import 是否在 paper_data 中定义 ───────────────────
    print("── 图像脚本 import 检查 ──")
    for fn in _FIG_SCRIPTS:
        fp = _HERE / fn
        if not fp.is_file():
            continue
        names = extract_fig_imports(fp)
        if not names:
            print(f"  {fn}: (无 paper_data import)")
            continue
        missing = [n for n in names if n not in defined]
        if missing:
            problems.append(f"  - [MISSING] {fn} import 未在 paper_data 定义: {missing}")
        print(f"  {fn}: import {len(names)} 项"
              + (f"  [OK] 全部已定义" if not missing else f"  [X] 缺失 {missing}"))
    # ── 3) 汇总 ───────────────────────────────────────────────────────
    if problems:
        print(f"\n[FAIL] {len(problems)} 处字段对齐问题:")
        print("\n".join(problems))
        return 1
    print(f"\n[PASS] 全部 {len(calls)} 处字段路径可用，图像脚本 import 均已在 paper_data 定义。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
