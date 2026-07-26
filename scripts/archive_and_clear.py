"""scripts/archive_and_clear.py — Archive experiment results then clear outputs.

Usage:
    python scripts/archive_and_clear.py              # archive + clear
    python scripts/archive_and_clear.py --dry-run    # preview only, no delete
    python scripts/archive_and_clear.py --archive-only  # write markdown, skip clear

Workflow (designed for pre-pipeline cleanup):
    1. Read all latest experiment result JSONs from outputs/results/
    2. Read figures list and metrics/benchmark CSVs
    3. Write a comprehensive Markdown snapshot to outputs/archive/<DATE>_results.md
    4. Delete outputs/results/exp*_*.json, predictions/, figures/, metrics/,
       and outputs/results/{metrics,paper_table,latency,throughput,memory}.*
       Keeps: outputs/results/paper_tables/ (LaTeX), outputs/models/, outputs/audit/,
              outputs/logs/
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
        f"# Experiment Results Archive",
        f"",
        f"**Generated:** {date_str}  ",
        f"**Experiments archived:** {sorted(results.keys())}  ",
        f"**Total result files:** {len(all_files)}  ",
        f"",
        "---",
        "",
    ]

    # ── 1. Summary banner (paper-facing) ─────────────────────────────────────
    lines += ["## Summary (latest result per experiment)", ""]

    summary_rows: list[tuple[str, str, str]] = []
    for exp in sorted(results):
        r = results[exp]
        comp = r.get("computation", "?")
        f1   = r.get("f1") or r.get("F1")
        if f1 is None:
            # try nested
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

    lines.append("| Experiment | Computation | F1 (headline) |")
    lines.append("|------------|-------------|---------------|")
    for exp, comp, f1s in summary_rows:
        lines.append(f"| {exp} | {comp} | {f1s} |")
    lines += ["", "---", ""]

    # ── 2. Per-experiment full JSON dump ──────────────────────────────────────
    lines += ["## Full Experiment Data", ""]

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

    # ── 3. All result files index ─────────────────────────────────────────────
    lines += ["## Result File Index", ""]
    lines.append("| File | Size (KB) | Modified |")
    lines.append("|------|-----------|----------|")
    for f in all_files:
        stat = f.stat()
        lines.append(
            f"| {f.name} | {stat.st_size / 1024:.1f} |"
            f" {datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')} |"
        )
    lines += ["", "---", ""]

    # ── 4. Aggregated metrics.json ────────────────────────────────────────────
    metrics_file = RESULTS / "metrics.json"
    if metrics_file.exists():
        try:
            m = json.loads(metrics_file.read_text(encoding="utf-8"))
            lines += ["## Aggregated metrics.json", "", "```json",
                       json.dumps(m, ensure_ascii=False, indent=2, default=str),
                       "```", ""]
        except Exception:
            pass

    # ── 5. CSV tables ─────────────────────────────────────────────────────────
    for csv_path, title in [
        (METRICS_DIR / "summary.csv",    "Summary CSV (outputs/metrics/summary.csv)"),
        (RESULTS / "latency.csv",        "Latency CSV"),
        (RESULTS / "throughput.csv",     "Throughput CSV"),
        (RESULTS / "memory.csv",         "Memory CSV"),
        (METRICS_DIR / "benchmark.csv",  "Benchmark CSV"),
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

    # ── 6. Figures index ──────────────────────────────────────────────────────
    if figures:
        lines += ["## Figures", ""]
        for f in figures:
            stat = f.stat()
            rel  = f.relative_to(OUTDIR)
            lines.append(f"- `{rel}` ({stat.st_size / 1024:.1f} KB, "
                          f"{datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')})")
        lines += [""]

    return "\n".join(lines)


# ── clear logic ───────────────────────────────────────────────────────────────

_CLEAR_GLOBS = [
    # timestamped experiment result files
    (RESULTS,     "exp*_*.json",      False),
    # predictions mirror
    (PREDICTIONS, "*.json",           False),
    # generated aggregate outputs
    (RESULTS,     "metrics.json",     False),
    (RESULTS,     "paper_table.md",   False),
    (RESULTS,     "latency.csv",      False),
    (RESULTS,     "throughput.csv",   False),
    (RESULTS,     "memory.csv",       False),
]

_CLEAR_DIRS = [
    FIGURES,
    METRICS_DIR,
    TABLES_DIR,
]


def clear_outputs(dry_run: bool = False) -> list[str]:
    """Delete experiment outputs. Returns list of deleted paths."""
    deleted: list[str] = []

    for dirpath, pattern, _recursive in _CLEAR_GLOBS:
        for f in dirpath.glob(pattern):
            if f.is_file():
                if not dry_run:
                    f.unlink()
                deleted.append(str(f.relative_to(ROOT)))

    for d in _CLEAR_DIRS:
        if d.exists():
            # Remove contents, keep the directory itself
            for child in list(d.iterdir()):
                if not dry_run:
                    if child.is_dir():
                        shutil.rmtree(child)
                    else:
                        child.unlink()
                deleted.append(str(child.relative_to(ROOT)))

    return deleted


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Archive results → Markdown, then clear outputs.")
    ap.add_argument("--dry-run",      action="store_true", help="Preview changes, write no files")
    ap.add_argument("--archive-only", action="store_true", help="Write archive markdown, skip clear")
    args = ap.parse_args()

    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date_tag = datetime.now().strftime("%Y-%m-%d")

    # ── Step 1: build and save archive markdown ───────────────────────────────
    log.info("Building archive markdown …")
    md = build_archive_markdown(date_str)

    archive_path = ARCHIVE / f"{date_tag}_experiment_results.md"
    if not args.dry_run:
        ARCHIVE.mkdir(parents=True, exist_ok=True)
        archive_path.write_text(md, encoding="utf-8")
        log.info("Archive written → %s  (%d KB)", archive_path, len(md) // 1024)
    else:
        log.info("[dry-run] Would write → %s  (%d KB)", archive_path, len(md) // 1024)

    if args.archive_only:
        log.info("--archive-only: skipping clear step")
        return 0

    # ── Step 2: clear ─────────────────────────────────────────────────────────
    log.info("Clearing experiment outputs …")
    deleted = clear_outputs(dry_run=args.dry_run)

    for p in deleted:
        mode = "[dry-run] would delete" if args.dry_run else "deleted"
        log.info("  %s %s", mode, p)

    log.info("%s %d output file(s).", "[dry-run] Would delete" if args.dry_run else "Cleared", len(deleted))

    if not args.dry_run:
        # Re-create empty placeholder dirs so subsequent pipelines don't error.
        for d in [RESULTS, PREDICTIONS, FIGURES, METRICS_DIR, TABLES_DIR]:
            d.mkdir(parents=True, exist_ok=True)
        log.info("Output directories reset and ready for next pipeline run.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
