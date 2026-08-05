"""realeval/io/archive.py — 实验结果归档与输出目录清理。

每次重跑前将旧实验结果保存为带时间戳的 Markdown 文件，然后清理结果目录，
保证下一轮实验从干净状态开始。
"""
from __future__ import annotations

import csv
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from realeval.io.paths import (
    ARCHIVE,
    FIGURES,
    METRICS_DIR,
    PREDICTIONS,
    RESULTS,
    ROOT,
    TABLES_DIR,
)

log = logging.getLogger("realeval.io.archive")


def _r(v: Any, nd: int = 4) -> Any:
    return round(v, nd) if isinstance(v, float) else v


def _latest_results() -> dict[str, dict[str, Any]]:
    """加载每个实验最新的带时间戳结果。"""
    by_exp: dict[str, dict[str, Any]] = {}
    for f in sorted(RESULTS.glob("exp*_*.json")):
        key = f.stem.rsplit("_", 2)[0]
        try:
            by_exp[key] = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return by_exp


def _all_result_files() -> list[Path]:
    """所有带时间戳的实验结果文件（按文件名排序）。"""
    return sorted(RESULTS.glob("exp*_*.json"))


def _csv_rows(path: Path) -> tuple[list[str], list[list[str]]]:
    """读取 CSV 并返回 (headers, rows)。"""
    if not path.exists():
        return [], []
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    return (rows[0] if rows else []), rows[1:]


def _figure_files() -> list[Path]:
    return sorted(FIGURES.glob("**/*.*")) if FIGURES.exists() else []


def _extract_headline_f1(r: dict[str, Any]) -> Any:
    """从结果字典中提取一个可用的 headline F1（用于归档摘要）。"""
    f1 = r.get("f1") or r.get("F1")
    if f1 is None:
        for sub in ("conditions", "classifiers", "schemes", "scales", "strategies"):
            inner = r.get(sub, {})
            if isinstance(inner, dict):
                for v in inner.values():
                    if isinstance(v, dict) and "f1" in v:
                        f1 = v["f1"]
                        break
            if f1 is not None:
                break
    return f1


def build_archive_markdown(date_str: str) -> str:
    """构建归档 Markdown 快照。"""
    results = _latest_results()
    all_files = _all_result_files()
    figures = _figure_files()

    lines: list[str] = [
        "# 实验结果归档快照",
        "",
        f"**生成时间：** {date_str}  ",
        f"**已归档实验：** {sorted(results.keys())}  ",
        f"**结果文件总数：** {len(all_files)}  ",
        "",
        "---",
        "",
    ]

    # 摘要
    lines += ["## 各实验最新结果摘要", ""]
    lines.append("| 实验 | 计算路径 | F1（headline） |")
    lines.append("|------|----------|----------------|")
    for exp in sorted(results):
        r = results[exp]
        comp = r.get("computation", "?")
        f1 = _extract_headline_f1(r)
        f1_str = f"{_r(f1):.4f}" if isinstance(f1, float) else str(f1) if f1 is not None else "—"
        lines.append(f"| {exp} | {comp} | {f1_str} |")
    lines += ["", "---", ""]

    # 完整 JSON
    lines += ["## 各实验完整数据", ""]
    for exp in sorted(results):
        r = results[exp]
        ts_file = max(RESULTS.glob(f"{exp}_*.json"), default=None)
        ts = ts_file.name if ts_file else "?"
        lines.append(f"### {exp} — `{ts}`")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(r, ensure_ascii=False, indent=2, default=str))
        lines.append("```")
        lines.append("")

    # 文件索引
    lines += ["## 结果文件索引", ""]
    lines.append("| 文件名 | 大小 (KB) | 修改时间 |")
    lines.append("|--------|-----------|----------|")
    for f in all_files:
        stat = f.stat()
        lines.append(
            f"| {f.name} | {stat.st_size / 1024:.1f} |"
            f" {datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')} |"
        )
    all_exp_file = RESULTS / "all_experiments.json"
    if all_exp_file.exists():
        stat = all_exp_file.stat()
        lines.append(
            f"| {all_exp_file.name} | {stat.st_size / 1024:.1f} |"
            f" {datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')} |"
        )
    lines += ["", "---", ""]

    # all_experiments.json
    if all_exp_file.exists():
        try:
            ae = json.loads(all_exp_file.read_text(encoding="utf-8"))
            lines += ["## all_experiments.json（paper_data.py 候补来源）", "", "```json",
                       json.dumps(ae, ensure_ascii=False, indent=2, default=str),
                       "```", ""]
        except Exception:
            pass

    # metrics.json
    metrics_file = RESULTS / "metrics.json"
    if metrics_file.exists():
        try:
            m = json.loads(metrics_file.read_text(encoding="utf-8"))
            lines += ["## 聚合指标 metrics.json", "", "```json",
                       json.dumps(m, ensure_ascii=False, indent=2, default=str),
                       "```", ""]
        except Exception:
            pass

    # CSV 表格
    for csv_path, title in [
        (METRICS_DIR / "summary.csv", "汇总 CSV（outputs/metrics/summary.csv）"),
        (RESULTS / "latency.csv", "延迟 CSV"),
        (RESULTS / "throughput.csv", "吞吐量 CSV"),
        (RESULTS / "memory.csv", "内存 CSV"),
        (METRICS_DIR / "benchmark.csv", "基准测试 CSV"),
    ]:
        headers, rows = _csv_rows(csv_path)
        if not headers:
            continue
        lines += [f"## {title}", ""]
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("|" + "|".join(["---"] * len(headers)) + "|")
        for row in rows:
            lines.append("| " + " | ".join(str(c) for c in row) + " |")
        lines += [""]

    # 图像索引
    if figures:
        lines += ["## 图像文件", ""]
        for f in figures:
            stat = f.stat()
            rel = f.relative_to(ROOT)
            lines.append(f"- `{rel}` ({stat.st_size / 1024:.1f} KB, "
                          f"{datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')})")
        lines += [""]

    return "\n".join(lines)


_CLEAR_GLOBS: list[tuple[Path, str, bool]] = [
    (RESULTS, "exp*_*.json", False),
    (PREDICTIONS, "*.json", False),
    (RESULTS, "all_experiments.json", False),
    (RESULTS, "metrics.json", False),
    (RESULTS, "paper_table.md", False),
    (RESULTS, "latency.csv", False),
    (RESULTS, "throughput.csv", False),
    (RESULTS, "memory.csv", False),
]

_CLEAR_DIRS: list[Path] = [FIGURES, METRICS_DIR, TABLES_DIR]


def clear_outputs(dry_run: bool = False) -> list[str]:
    """删除实验输出文件并返回已删除路径列表。"""
    deleted: list[str] = []

    for dirpath, pattern, _recursive in _CLEAR_GLOBS:
        for f in dirpath.glob(pattern):
            if f.is_file():
                if not dry_run:
                    f.unlink()
                deleted.append(str(f.relative_to(ROOT)))

    for d in _CLEAR_DIRS:
        if d.exists():
            for child in list(d.iterdir()):
                if not dry_run:
                    if child.is_dir():
                        shutil.rmtree(child)
                    else:
                        child.unlink()
                deleted.append(str(child.relative_to(ROOT)))

    return deleted


def _has_results() -> bool:
    """检查 ``outputs/results/`` 中是否存在可归档的实验结果。"""
    return bool(list(RESULTS.glob("exp*_*.json"))) or (RESULTS / "all_experiments.json").exists()


def archive_if_needed(force: bool = False) -> str | None:
    """若存在旧实验结果则自动归档并清理，返回归档文件路径（无结果时返回 None）。

    Args:
        force: True 表示即使目录为空也强制执行（用于测试）。

    Returns:
        归档 Markdown 文件路径字符串；无结果可归档时返回 None。
    """
    if not force and not _has_results():
        log.info("outputs/results/ 中无实验结果，跳过归档步骤。")
        return None

    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d %H:%M:%S")
    date_tag = now.strftime("%Y-%m-%d_%H%M%S")

    log.info("检测到旧实验结果，开始自动归档…")
    md = build_archive_markdown(date_str)

    ARCHIVE.mkdir(parents=True, exist_ok=True)
    archive_path = ARCHIVE / f"{date_tag}_experiment_results.md"
    archive_path.write_text(md, encoding="utf-8")
    log.info("归档完成 → %s  (%d KB)", archive_path, len(md) // 1024)

    log.info("清理旧实验输出…")
    deleted = clear_outputs(dry_run=False)
    log.info("已清理 %d 个文件。", len(deleted))

    # 重建空占位目录
    for d in [RESULTS, PREDICTIONS, FIGURES, METRICS_DIR, TABLES_DIR]:
        d.mkdir(parents=True, exist_ok=True)
    log.info("输出目录已重置，准备接受新一轮实验结果。")

    return str(archive_path)
