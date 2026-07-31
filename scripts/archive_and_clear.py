"""scripts/archive_and_clear.py — 归档实验结果并清理输出目录

用法：
    python scripts/archive_and_clear.py              # 归档 + 清理
    python scripts/archive_and_clear.py --dry-run    # 仅预览，不写文件
    python scripts/archive_and_clear.py --archive-only  # 仅写 Markdown，不清理

工作流（设计为每次流水线运行前的标准预处理步骤）：
    1. 从 outputs/results/ 读取最新的各实验结果 JSON（含 all_experiments.json）
    2. 读取 figures 列表与 metrics/benchmark CSV
    3. 将完整快照写入 outputs/archive/<DATE>_<TIME>_results.md
    4. 删除 outputs/results/exp*_*.json、all_experiments.json、predictions/、
       figures/、metrics/，以及 outputs/results/{metrics,paper_table,latency,
       throughput,memory}.*
       保留：outputs/results/paper_tables/（LaTeX）、outputs/models/、
             outputs/audit/、outputs/logs/

可通过 archive_if_needed() 在流水线代码中按需调用。
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("archive_and_clear")

ROOT   = Path(__file__).resolve().parent.parent
OUTDIR = ROOT / "outputs"

RESULTS     = OUTDIR / "results"
PREDICTIONS = OUTDIR / "predictions"
FIGURES     = OUTDIR / "figures"
METRICS_DIR = OUTDIR / "metrics"
TABLES_DIR  = OUTDIR / "tables"
ARCHIVE     = OUTDIR / "archive"


# ── helpers ──────────────────────────────────────────────────────────────────

def _r(v, nd=4):
    return round(v, nd) if isinstance(v, float) else v


def _latest_results() -> dict[str, dict]:
    """Load the latest timestamped result for each experiment."""
    by_exp: dict[str, dict] = {}
    for f in sorted(RESULTS.glob("exp*_*.json")):
        key = f.stem.rsplit("_", 2)[0]
        try:
            by_exp[key] = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return by_exp


def _all_result_files() -> list[Path]:
    """All timestamped experiment result files (sorted)."""
    return sorted(RESULTS.glob("exp*_*.json"))


def _csv_rows(path: Path) -> tuple[list[str], list[list[str]]]:
    """Read CSV and return (headers, rows). Returns ([], []) if missing."""
    if not path.exists():
        return [], []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)
    return (rows[0] if rows else []), rows[1:]


def _figure_files() -> list[Path]:
    return sorted(FIGURES.glob("**/*.*")) if FIGURES.exists() else []


# ── markdown builder ─────────────────────────────────────────────────────────

def build_archive_markdown(date_str: str) -> str:
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

    # ── 1. 摘要（面向论文）─────────────────────────────────────────────────────
    lines += ["## 各实验最新结果摘要", ""]

    summary_rows: list[tuple[str, str, str]] = []
    for exp in sorted(results):
        r = results[exp]
        comp = r.get("computation", "?")
        f1   = r.get("f1") or r.get("F1")
        if f1 is None:
            # 尝试从嵌套字段提取
            for sub in ("conditions", "classifiers", "schemes", "scales", "strategies"):
                inner = r.get(sub, {})
                if isinstance(inner, dict):
                    for v in inner.values():
                        if isinstance(v, dict) and "f1" in v:
                            f1 = v["f1"]; break
                if f1 is not None:
                    break
        f1_str = f"{f1:.4f}" if isinstance(f1, float) else str(f1) if f1 is not None else "—"
        summary_rows.append((exp, comp, f1_str))

    lines.append("| 实验 | 计算路径 | F1（headline） |")
    lines.append("|------|----------|----------------|")
    for exp, comp, f1s in summary_rows:
        lines.append(f"| {exp} | {comp} | {f1s} |")
    lines += ["", "---", ""]

    # ── 2. 各实验完整 JSON 数据 ──────────────────────────────────────────────
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

    # ── 3. 结果文件索引 ───────────────────────────────────────────────────────
    lines += ["## 结果文件索引", ""]
    lines.append("| 文件名 | 大小 (KB) | 修改时间 |")
    lines.append("|--------|-----------|----------|")
    for f in all_files:
        stat = f.stat()
        lines.append(
            f"| {f.name} | {stat.st_size / 1024:.1f} |"
            f" {datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')} |"
        )
    # 也将 all_experiments.json 纳入索引
    all_exp_file = RESULTS / "all_experiments.json"
    if all_exp_file.exists():
        stat = all_exp_file.stat()
        lines.append(
            f"| {all_exp_file.name} | {stat.st_size / 1024:.1f} |"
            f" {datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')} |"
        )
    lines += ["", "---", ""]

    # ── 4. all_experiments.json 内容（paper_data.py 主要候补来源）─────────────
    if all_exp_file.exists():
        try:
            ae = json.loads(all_exp_file.read_text(encoding="utf-8"))
            lines += ["## all_experiments.json（paper_data.py 候补来源）", "", "```json",
                       json.dumps(ae, ensure_ascii=False, indent=2, default=str),
                       "```", ""]
        except Exception:
            pass

    # ── 5. Aggregated metrics.json ────────────────────────────────────────────
    metrics_file = RESULTS / "metrics.json"
    if metrics_file.exists():
        try:
            m = json.loads(metrics_file.read_text(encoding="utf-8"))
            lines += ["## 聚合指标 metrics.json", "", "```json",
                       json.dumps(m, ensure_ascii=False, indent=2, default=str),
                       "```", ""]
        except Exception:
            pass

    # ── 6. CSV 表格 ──────────────────────────────────────────────────────────
    for csv_path, title in [
        (METRICS_DIR / "summary.csv",    "汇总 CSV（outputs/metrics/summary.csv）"),
        (RESULTS / "latency.csv",        "延迟 CSV"),
        (RESULTS / "throughput.csv",     "吞吐量 CSV"),
        (RESULTS / "memory.csv",         "内存 CSV"),
        (METRICS_DIR / "benchmark.csv",  "基准测试 CSV"),
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

    # ── 7. 图像文件索引 ───────────────────────────────────────────────────────
    if figures:
        lines += ["## 图像文件", ""]
        for f in figures:
            stat = f.stat()
            rel  = f.relative_to(OUTDIR)
            lines.append(f"- `{rel}` ({stat.st_size / 1024:.1f} KB, "
                          f"{datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')})")
        lines += [""]

    return "\n".join(lines)


# ── 清理逻辑 ─────────────────────────────────────────────────────────────────

_CLEAR_GLOBS = [
    # 带时间戳的实验结果文件
    (RESULTS,     "exp*_*.json",         False),
    # predictions 镜像
    (PREDICTIONS, "*.json",              False),
    # 全量归并文件（paper_data.py 候补来源）
    (RESULTS,     "all_experiments.json", False),
    # 生成的聚合输出
    (RESULTS,     "metrics.json",        False),
    (RESULTS,     "paper_table.md",      False),
    (RESULTS,     "latency.csv",         False),
    (RESULTS,     "throughput.csv",      False),
    (RESULTS,     "memory.csv",          False),
]

_CLEAR_DIRS = [
    FIGURES,
    METRICS_DIR,
    TABLES_DIR,
]


def clear_outputs(dry_run: bool = False) -> list[str]:
    """Delete experiment outputs. Returns list of deleted paths."""
    deleted: list[str] = []

def clear_outputs(dry_run: bool = False) -> list[str]:
    """删除实验输出文件。返回已删除路径列表。"""
    deleted: list[str] = []

    for dirpath, pattern, _recursive in _CLEAR_GLOBS:
        for f in dirpath.glob(pattern):
            if f.is_file():
                if not dry_run:
                    f.unlink()
                deleted.append(str(f.relative_to(ROOT)))

    for d in _CLEAR_DIRS:
        if d.exists():
            # 删除目录内容，保留目录本身
            for child in list(d.iterdir()):
                if not dry_run:
                    if child.is_dir():
                        shutil.rmtree(child)
                    else:
                        child.unlink()
                deleted.append(str(child.relative_to(ROOT)))

    return deleted


def _has_results() -> bool:
    """检查 outputs/results/ 中是否存在实验结果文件。"""
    return bool(list(RESULTS.glob("exp*_*.json"))) or (RESULTS / "all_experiments.json").exists()


def archive_if_needed(force: bool = False) -> str | None:
    """若存在旧实验结果则自动归档并清理，返回归档文件路径（无结果时返回 None）。

    该函数供 paper_pipeline.py / runner.py 在每次运行前调用，
    实现"每次重跑前将旧结果保存为带时间戳的 Markdown 文件并清理输出目录"。

    参数：
        force：True 表示即使目录为空也强制执行（用于测试）。

    返回：归档文件路径字符串，若无结果可归档则返回 None。
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

    # 重建空占位目录，避免后续流水线报错
    for d in [RESULTS, PREDICTIONS, FIGURES, METRICS_DIR, TABLES_DIR]:
        d.mkdir(parents=True, exist_ok=True)
    log.info("输出目录已重置，准备接受新一轮实验结果。")

    return str(archive_path)


# ── main ────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="归档实验结果 → Markdown，然后清理输出目录。")
    ap.add_argument("--dry-run",      action="store_true", help="仅预览，不写入文件")
    ap.add_argument("--archive-only", action="store_true", help="仅写 Markdown，跳过清理")
    ap.add_argument("--force",        action="store_true", help="即使无结果也强制执行")
    args = ap.parse_args()

    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date_tag = datetime.now().strftime("%Y-%m-%d_%H%M%S")

    # ── 步骤 1：构建并保存归档 Markdown ─────────────────────────────────────
    log.info("正在构建归档 Markdown …")
    md = build_archive_markdown(date_str)

    archive_path = ARCHIVE / f"{date_tag}_experiment_results.md"
    if not args.dry_run:
        ARCHIVE.mkdir(parents=True, exist_ok=True)
        archive_path.write_text(md, encoding="utf-8")
        log.info("归档已写入 → %s  (%d KB)", archive_path, len(md) // 1024)
    else:
        log.info("[dry-run] 将写入 → %s  (%d KB)", archive_path, len(md) // 1024)

    if args.archive_only:
        log.info("--archive-only：跳过清理步骤")
        return 0

    # ── 步骤 2：清理 ─────────────────────────────────────────────────────────
    log.info("正在清理实验输出目录 …")
    deleted = clear_outputs(dry_run=args.dry_run)

    for p in deleted:
        mode = "[dry-run] 将删除" if args.dry_run else "已删除"
        log.info("  %s %s", mode, p)

    log.info("%s %d 个输出文件。",
             "[dry-run] 将删除" if args.dry_run else "已清理", len(deleted))

    if not args.dry_run:
        # 重建空占位目录
        for d in [RESULTS, PREDICTIONS, FIGURES, METRICS_DIR, TABLES_DIR]:
            d.mkdir(parents=True, exist_ok=True)
        log.info("输出目录已重置，可进行下一轮流水线运行。")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
