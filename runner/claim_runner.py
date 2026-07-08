"""runner/claim_runner.py — Claim-Driven Experiment Runner

Loads claim YAML definitions, executes experiments, evaluates evidence,
and produces PASS/FAIL/UNSUPPORTED verdicts automatically.
"""
from __future__ import annotations
import json
import logging
from pathlib import Path

import yaml

from audit.evidence_graph import EvidenceGraph, evaluate_claim, validate_claim_definition

ROOT = Path(__file__).resolve().parent.parent
CLAIMS_DIR = ROOT / "claims"

logger = logging.getLogger("claim_runner")


def load_claim(path: Path) -> dict:
    """Load and validate a claim YAML file."""
    with open(path, encoding="utf-8") as f:
        claim = yaml.safe_load(f)
    ok, errors = validate_claim_definition(claim)
    if not ok:
        raise ValueError(f"Invalid claim {path}: {errors}")
    return claim


def list_claims() -> list[Path]:
    """List all claim YAML files in claims/."""
    if not CLAIMS_DIR.is_dir():
        return []
    return sorted(CLAIMS_DIR.glob("claim_*.yaml"))


def run_claim(claim_path: Path, experiment_fn, config: dict | None = None) -> dict:
    """Execute a single claim end-to-end.

    Args:
        claim_path: Path to claim YAML file.
        experiment_fn: Callable(config) → ExperimentResult.
        config: Optional config overlay.

    Returns:
        {claim, experiment_result, evidence_graph_path, verdict}
    """
    claim = load_claim(claim_path)
    claim_id = claim["id"]
    logger.info("Running claim %s: %s", claim_id, claim.get("hypothesis", ""))

    # Build config
    cfg = dict(config or {})
    cfg["claim_ids"] = [claim_id]
    cfg["experiment_id"] = claim_id

    # Initialize evidence graph
    graph = EvidenceGraph(claim_id)
    claim_node = graph.add_claim({
        "hypothesis": claim.get("hypothesis"),
        "independent_variables": claim.get("independent_variables"),
        "dependent_variables": claim.get("dependent_variables"),
        "controls": claim.get("controls"),
        "acceptance": claim.get("acceptance"),
    })

    # Run experiment
    try:
        result = experiment_fn(cfg)
    except Exception as e:
        logger.error("Claim %s experiment failed: %s", claim_id, e)
        return {"claim": claim, "error": str(e), "verdict": "UNSUPPORTED"}

    # Record evidence chain
    run_node = graph.add_run(result.provenance, parents=[claim_node])
    preds_node = graph.add_predictions({
        "n_samples": len(result.raw_predictions),
        "sample_ids": [p.get("sample_id") for p in result.raw_predictions[:10]],
    }, parents=[run_node])
    metric_node = graph.add_metric(result.collected_metrics, parents=[preds_node])
    stats_node = graph.add_statistics(result.statistics, parents=[metric_node])

    # Evaluate claim
    eval_result = evaluate_claim(claim, result.collected_metrics)
    evidence_node = graph.add_evidence({
        "supports_claim": eval_result["verdict"] == "PASS",
        "strength": "strong" if eval_result["verdict"] == "PASS" else "weak",
        "reason": eval_result["details"],
        "acceptance_results": eval_result.get("results", {}),
    }, parents=[stats_node])
    graph.add_conclusion({
        "verdict": eval_result["verdict"],
        "summary": f"Claim {claim_id}: {eval_result['verdict']} — {eval_result['details']}",
    }, parents=[evidence_node])

    # Validate and save
    ok, errors = graph.validate()
    if not ok:
        logger.warning("Evidence graph validation warnings: %s", errors)
    graph_path = graph.save()

    return {
        "claim": claim,
        "experiment_result": {
            "metrics": result.collected_metrics,
            "statistics": result.statistics,
        },
        "evidence_graph_path": str(graph_path),
        "verdict": eval_result["verdict"],
        "verdict_details": eval_result["details"],
        "acceptance_results": eval_result.get("results", {}),
    }


def run_all_claims(experiment_fn, config: dict | None = None) -> dict:
    """Run all claims in claims/ directory. Returns {claim_id: result}."""
    results = {}
    for claim_path in list_claims():
        try:
            results[claim_path.stem] = run_claim(claim_path, experiment_fn, config)
        except Exception as e:
            logger.error("Claim %s failed: %s", claim_path, e)
            results[claim_path.stem] = {"error": str(e), "verdict": "UNSUPPORTED"}
    return results


def print_verdicts(results: dict):
    """Print a summary table of all claim verdicts."""
    print("\n" + "=" * 60)
    print("CLAIM VERDICTS")
    print("=" * 60)
    for claim_id, r in results.items():
        verdict = r.get("verdict", "ERROR")
        symbol = {"PASS": "✓", "FAIL": "✗", "UNSUPPORTED": "?"}.get(verdict, "!")
        details = r.get("verdict_details", r.get("error", ""))
        print(f"  {symbol} {claim_id}: {verdict} — {details}")
    print("=" * 60)
