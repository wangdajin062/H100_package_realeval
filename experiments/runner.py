"""experiments/runner.py — Unified Experiment Orchestrator (thin wrapper).

Delegates to the refactored ``runner/`` package, ``config/``, ``metrics/``,
``realeval/io/``, and ``cli/`` modules. This file exists solely to preserve the
historical CLI entry point:

    python -m experiments.runner --paper --config config/h100.yaml
    python -m experiments.runner --exp 1,3,6
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

# Ensure project root is importable when running as ``python -m experiments.runner``
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cli.parser import build_runner_parser
from config import load_config
from config.schema import ensure_valid_config
from metrics.contract import check_alignment, print_alignment_report, validate_latest_results
from runner.orchestrator import run_all, run_selected
from runner.registry import EXPERIMENTS, SHORT_TO_FULL
from realeval.io.archive import archive_if_needed
from utils.logging import configure_logging, get_logger

configure_logging()
logger = get_logger("experiments.runner")


def _handle_standalone_checks(args) -> bool:
    """Handle CLI flags that do not run experiments. Returns True if main() should exit."""
    if args.check:
        from realeval.hwenv import check
        ok, issues = check(strict=True)
        if ok:
            print("Hardware check PASSED (paper-grade ready)")
        else:
            print("Hardware check ISSUES:")
            for i in issues:
                print(f"  - {i}")
        return True

    if args.storage_check:
        from realeval.paths import storage_report, list_local_models
        rep = storage_report()
        print("Storage Report:")
        for k, v in rep.items():
            print(f"  {k}: {v}")
        lm = list_local_models()
        print(f"Local models ({lm['count']}):")
        for m in lm["found"]:
            print(f"  - {m}")
        return True

    if args.report:
        from realeval.report import build_all
        logger.info("Generating paper tables and figures from existing results...")
        made = build_all()
        logger.info("Generated %d artifacts", len(made))
        for p in made:
            print(f"  {p}")
        return True

    if args.validate_contract:
        report = validate_latest_results(strict=True)
        failed = False
        for exp, missing in report.items():
            if missing:
                failed = True
                print(f"[FAIL] {exp}")
                for item in missing:
                    print(f"  - {item}")
            else:
                print(f"[PASS] {exp}")
        if failed:
            logger.error("Contract validation failed")
            sys.exit(2)
        logger.info("Contract validation passed")
        return True

    if args.align:
        report = check_alignment()
        failed = print_alignment_report(report)
        if failed:
            sys.exit(2)
        return True

    if args.benchmark:
        from realeval import benchmark
        import torch
        import torch.nn as nn
        model = nn.Sequential(nn.Linear(64, 128), nn.ReLU(), nn.Linear(128, 2))
        r = benchmark.benchmark(model, torch.randn(64), warmup=10, repeat=100, batch_sizes=(1, 16, 64))
        s = benchmark.summary(r)
        print("Benchmark summary:", s)
        return True

    return False


def _resolve_experiment_selection(args) -> list[str]:
    """Resolve which experiments to run from CLI args."""
    if args.exp is not None:
        raw = args.exp
    elif args.experiments is not None:
        raw = args.experiments
    else:
        return [e.short for e in EXPERIMENTS]

    if raw == "all":
        return [e.short for e in EXPERIMENTS]

    parts = [p.strip() for p in raw.split(",") if p.strip()]
    digits = []
    for p in parts:
        if p.isdigit():
            digits.append(p)
        elif p.startswith("exp") and p[3:].isdigit():
            digits.append(p[3:])
        else:
            logger.error("Invalid experiment identifier: %s", p)
            sys.exit(1)

    from realeval.validation import validate_experiment_selection
    return validate_experiment_selection(
        ",".join(digits),
        [(e.short, e.description) for e in EXPERIMENTS],
    )


def main() -> int:
    """CLI entry point."""
    args = build_runner_parser().parse_args()
    if _handle_standalone_checks(args):
        return 0

    # --resume depends on existing results; archiving would delete them and break resume.
    no_archive = args.no_archive or args.resume
    if not no_archive:
        try:
            archived = archive_if_needed()
            if archived:
                logger.info("旧实验结果已归档至：%s", archived)
        except Exception as exc:
            logger.warning("归档步骤失败（继续运行）：%s", exc)

    config = load_config(args.config)
    if args.paper:
        logger.info("PAPER MODE: real Qwen + H100 backend")

    try:
        ensure_valid_config(config)
    except Exception as exc:
        logger.error("Config validation failed: %s", exc)
        sys.exit(1)

    selected = _resolve_experiment_selection(args)
    results = run_selected(
        config,
        selected,
        resume=args.resume,
        no_archive=True,  # already archived above
        aggregate=True,
    )
    logger.info("实验完成：%s", list(results.keys()))
    logger.info("结果已保存至 outputs/results/。运行 'python -m experiments.runner --report' 生成论文表格/图像。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
