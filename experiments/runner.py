"""experiments/runner.py — CLI 入口与兼容层。

实际编排逻辑已迁移至 ``runner/orchestrator.py``；本文件保留为命令行入口，
并继续暴露 ``EXPERIMENTS`` / ``_SHORT_TO_FULL`` 等旧符号以兼容既有导入。
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cli.parser import build_runner_parser
from config import load_config
from runner.orchestrator import run_all, run_selected
from runner.registry import EXPERIMENTS, SHORT_TO_FULL
from utils.logging import configure_logging, get_logger

configure_logging()
logger = get_logger("experiments.runner")

# 兼容旧导入：外部可能引用 experiments.runner.EXPERIMENTS / _SHORT_TO_FULL / run_all
_SHORT_TO_FULL = SHORT_TO_FULL


def _import_exp(modname: str) -> Any:
    """按模块名导入实验模块（兼容旧 paper_pipeline 导入）。"""
    from runner.experiment_runner import import_experiment
    return import_experiment(modname)


def run_experiment(modname: str, short: str, config: dict[str, Any]) -> dict[str, Any]:
    """运行单个实验（兼容旧接口）。"""
    from runner.experiment_runner import run_experiment as _run
    return _run(modname, short, config)


def _handle_standalone_checks(args) -> bool:
    """处理不需要运行实验的独立子命令。"""
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
        from realeval.paths import list_local_models, storage_report
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
        from metrics.contract import validate_latest_results
        report = validate_latest_results()
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
        from metrics.contract import check_alignment, print_alignment_report
        report = check_alignment()
        failed = print_alignment_report(report)
        if failed:
            sys.exit(2)
        return True

    if args.benchmark:
        from realeval.benchmark import benchmark, summary
        import torch
        import torch.nn as nn
        model = nn.Sequential(nn.Linear(64, 128), nn.ReLU(), nn.Linear(128, 2))
        r = benchmark(model, torch.randn(64), warmup=10, repeat=100, batch_sizes=(1, 16, 64))
        s = summary(r)
        print("Benchmark summary:", s)
        return True

    return False


def _load_and_validate_config(args) -> dict[str, Any]:
    """加载配置、应用 smoke/paper 标记、写环境报告。"""
    from realeval import envreport, validation
    config = load_config(args.config, validate=False)
    if args.smoke:
        config["_smoke"] = True
        logger.info("SMOKE MODE: using small model verification path")
    if args.paper:
        config["_paper"] = True
        logger.info("PAPER MODE: using real Qwen + H100 backend")

    try:
        validation.validate_config(config)
    except validation.ValidationError as e:
        logger.error("Config validation failed: %s", e)
        sys.exit(1)

    envreport.write_report()
    from realeval.audit import log_environment
    log_environment(config)
    return config


def _resolve_experiment_selection(args) -> list[str]:
    """根据 CLI 参数解析要运行的实验列表。"""
    if args.exp is not None:
        raw = args.exp
    elif args.experiments is not None:
        raw = args.experiments
    else:
        raw = "all"

    if raw == "all":
        return [e.short for e in EXPERIMENTS]

    parts = [p.strip() for p in raw.split(",") if p.strip()]
    digits: list[str] = []
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
        [(e.short, e.description) for e in EXPERIMENTS]
    )


def main() -> int:
    parser = build_runner_parser()
    args = parser.parse_args()

    if _handle_standalone_checks(args):
        return 0

    config = _load_and_validate_config(args)
    selected = _resolve_experiment_selection(args)

    # --resume 模式下避免归档，否则 resume 会失效
    no_archive = getattr(args, "no_archive", False) or args.resume
    results = run_selected(
        config,
        selected,
        resume=args.resume,
        no_archive=no_archive,
        aggregate=True,
    )

    logger.info("实验完成：%s", list(results.keys()))
    logger.info("结果已保存至 outputs/results/。"
                "运行 'python -m experiments.runner --report' 生成论文表格/图像。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
