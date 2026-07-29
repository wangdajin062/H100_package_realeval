#!/usr/bin/env python3
"""
rerun_and_validate_contract.py
==============================

One-shot script for a torch-enabled environment (e.g. RunPod H100).

It re-runs the experiments whose result fields feed the paper figures/tables,
then validates the latest result JSON files against the contract defined in
experiments/contract.py.

Usage on RunPod / H100:
    python scripts/rerun_and_validate_contract.py --paper

Usage for smoke verification (small models, no GPU weights needed):
    python scripts/rerun_and_validate_contract.py --smoke

Exit code:
    0  all targeted experiments produced contract-aligned results
    1  runtime errors or contract validation failed
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Allow running without package install
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from experiments.runner import run_all
from experiments.contract import validate_latest_results

logger = logging.getLogger("rerun_and_validate_contract")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")

# Experiments consumed by the 8 paper figures (as listed in generate_all.py)
# plus exp4 which feeds realeval/report.py Table2.tex.
FIGURE_FEEDING_EXPERIMENTS = [
    "exp1",   # Fig 4, Fig 3 (QAD F1), report Table2
    "exp2",   # Fig 5(a)
    "exp3",   # Fig 6
    "exp4",   # report Table2 baselines
    "exp5",   # Fig 8(b)(c)
    "exp6",   # Fig 7
    "exp8",   # latency figure / Table 7
    "exp10",  # Fig 5(b)
    "exp11",  # Fig 3 QAT row / Fig 8(a)
]


def main() -> int:
    ap = argparse.ArgumentParser(description="Re-run figure-feeding experiments and validate contract")
    ap.add_argument("--paper", action="store_true", help="Paper-grade run (real Qwen + H100)")
    ap.add_argument("--smoke", action="store_true", help="Smoke verification (small models)")
    ap.add_argument("--config", type=str, default=None, help="Path to config YAML")
    ap.add_argument("--resume", action="store_true", help="Skip experiments that already have a result file")
    args = ap.parse_args()

    if not args.paper and not args.smoke:
        logger.error("Specify one of --paper or --smoke")
        return 1

    from realeval.io import load_config
    config = load_config(args.config)
    config["_smoke"] = args.smoke
    if args.paper:
        config["_paper"] = True

    logger.info("Running experiments: %s", ", ".join(FIGURE_FEEDING_EXPERIMENTS))
    try:
        run_all(config, selected=FIGURE_FEEDING_EXPERIMENTS, resume=args.resume)
    except Exception as e:
        logger.error("Experiment batch failed: %s", e, exc_info=True)
        return 1

    logger.info("Validating result contract for figure-feeding experiments...")
    report = validate_latest_results(targets=FIGURE_FEEDING_EXPERIMENTS)

    failed = False
    for exp, missing in report.items():
        if missing:
            failed = True
            logger.error("[FAIL] %s", exp)
            for item in missing:
                logger.error("  - %s", item)
        else:
            logger.info("[PASS] %s", exp)

    if failed:
        logger.error("Contract validation failed")
        return 1

    logger.info("All figure-feeding experiments passed contract validation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
