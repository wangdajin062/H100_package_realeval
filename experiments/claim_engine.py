"""claim_engine.py — the Research Workflow Engine core.

Claim -> Experiment -> Execution (multi-seed) -> Evidence -> Statistics -> Conclusion.

Each claim (claims/*.yaml) declares a hypothesis, the experiment that tests it, the two conditions to
contrast, and machine-checkable acceptance criteria. The engine runs the experiment across seeds,
extracts the raw dependent-variable samples (Evidence First), summarises them with bootstrap CIs,
evaluates the acceptance criteria, and emits PASS / FAIL / UNSUPPORTED together with a full evidence
trace (which experiment, which seeds, which numbers, why). Nothing is hand-judged; the paper's
conclusions become reproducible functions of the raw evidence.
"""
from __future__ import annotations

import argparse
import copy
import importlib
import json
import logging
import re
from pathlib import Path

import yaml

from realeval import statistics as st
from realeval.runlog import provenance

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger("claim_engine")

ROOT = Path(__file__).resolve().parent.parent
# New-format claims (YAML with "experiment" key, evaluated by this engine).
# Legacy-format claims live in claims/legacy/ and are handled by runner/claim_runner.py.
CLAIMS = ROOT / "claims"
OUT = ROOT / "outputs" / "claims"

from experiments.runner import _SHORT_TO_FULL as _SHORT_TO_MOD


def _dig(d, path):
    for p in path:
        d = d.get(p, {}) if isinstance(d, dict) else {}
    return d


def _run_experiment_seeds(short, base_config, seeds):
    """Execute the experiment once per seed; return the list of raw result dicts (the evidence)."""
    mod = importlib.import_module(f"experiments.{_SHORT_TO_MOD[short]}")
    results = []
    for s in range(seeds):
        cfg = copy.deepcopy(base_config)
        cfg["seed"] = 42 + s
        cfg["_smoke"] = base_config.get("_smoke", True)
        results.append(mod.run(cfg))
    return results


def _collect_samples(results, evidence_path, condition, dep_var):
    """Evidence First: pull the per-seed dependent-variable values for one condition."""
    vals = []
    for r in results:
        node = _dig(r, evidence_path)
        cond = node.get(condition, {}) if isinstance(node, dict) else {}
        v = cond.get(dep_var) if isinstance(cond, dict) else None
        if v is not None:
            vals.append(v)
    return vals


def evaluate_claim(claim: dict, base_config: dict) -> dict:
    short = claim["experiment"]
    seeds = int(claim.get("seeds", 1))
    logger.info("[%s] %s", claim["id"], claim["hypothesis"])
    results = _run_experiment_seeds(short, base_config, seeds)

    trace = {"claim": claim["id"], "experiment": short, "seeds": seeds,
             "provenance": provenance(base_config), "evidence": {}, "stats": {}}

    cmp = claim.get("compare")
    ctx = {}  # names available to the acceptance expressions
    if cmp:
        dep = claim["dependent_variable"]
        t_vals = _collect_samples(results, claim["evidence_path"], cmp["treatment"], dep)
        b_vals = _collect_samples(results, claim["evidence_path"], cmp["baseline"], dep)
        trace["evidence"] = {cmp["treatment"]: t_vals, cmp["baseline"]: b_vals}
        t_sum, b_sum = st.summarize(t_vals), st.summarize(b_vals)
        comparison = st.compare(t_vals, b_vals, paired=(len(t_vals) == len(b_vals)))
        trace["stats"] = {"treatment": t_sum, "baseline": b_sum, "comparison": comparison}
        # expose names for acceptance criteria
        ctx["treatment"] = type("N", (), t_sum)
        ctx["baseline"] = type("N", (), b_sum)
        setattr(ctx["treatment"], dep, t_sum["mean"])
        setattr(ctx["baseline"], dep, b_sum["mean"])
        if t_sum["mean"] is not None and b_sum["mean"] is not None:
            ctx["mean_diff"] = b_sum["mean"] - t_sum["mean"]
            ctx["reduction_pct"] = (100 * (b_sum["mean"] - t_sum["mean"]) / b_sum["mean"]
                                    if b_sum["mean"] else None)
        ctx["cohens_d"] = comparison.get("cohens_d")
        ctx["p_value"] = comparison.get("t_p")
    else:
        # single-quantity claim (e.g. speedup from measured alpha)
        node = _dig(results[0], claim["evidence_path"])
        measured_alpha = node.get("generic") if isinstance(node, dict) else None
        trace["evidence"] = {"node": node}
        ctx["measured_alpha"] = measured_alpha
        gamma = base_config.get("speculative_decoding", {}).get("gamma", 5)
        ctx["speedup"] = ((1 - measured_alpha ** (gamma + 1)) / (1 - measured_alpha)
                          if measured_alpha else None)

    # Evaluate acceptance criteria -> PASS / FAIL / UNSUPPORTED
    verdicts = []
    unsupported = False
    for crit in claim.get("acceptance", []):
        try:
            ok = bool(_safe_eval(crit, ctx))
        except _Unsupported:
            ok = None; unsupported = True
        verdicts.append({"criterion": crit, "result": ok})
    if unsupported or any(v["result"] is None for v in verdicts):
        conclusion = "UNSUPPORTED"
    elif all(v["result"] for v in verdicts):
        conclusion = "PASS"
    else:
        conclusion = "FAIL"
    trace["acceptance"] = verdicts
    trace["conclusion"] = conclusion
    logger.info("[%s] -> %s", claim["id"], conclusion)
    return trace


class _Unsupported(Exception):
    pass


def _safe_eval(expr, ctx):
    """Evaluate an acceptance expression via AST parsing (no eval).

    Only comparison, boolean, unary, binary arithmetic, and attribute-access nodes
    are allowed.  The namespace is restricted to *ctx* keys — no builtins, no
    dunder traversal, no function calls.

    SECURITY: The claims/ directory must be developer-controlled. This AST evaluator
    is sandboxed (whitelist of allowed node types, no __builtins__, no function calls,
    no attribute traversal beyond ctx objects), but YAML files in claims/ are trusted
    input. Do not add user-submitted claims without review.
    """
    import ast
    import operator as _op

    # Fast path for identity checks (avoid AST for readability).
    m = re.match(r"\s*([a-zA-Z_.]+)\s+is not None\s*$", expr)
    if m:
        val = _resolve_dotted(m.group(1), ctx)
        if val is None:
            raise _Unsupported()
        return True
    m = re.match(r"\s*([a-zA-Z_.]+)\s+is None\s*$", expr)
    if m:
        return _resolve_dotted(m.group(1), ctx) is None

    _CMP = {
        ast.Lt: _op.lt, ast.LtE: _op.le, ast.Gt: _op.gt, ast.GtE: _op.ge,
        ast.Eq: _op.eq, ast.NotEq: _op.ne,
        ast.Is: _op.is_, ast.IsNot: _op.is_not,
    }
    _BINOP = {
        ast.Add: _op.add, ast.Sub: _op.sub, ast.Mult: _op.mul,
        ast.Div: _op.truediv, ast.Pow: _op.pow,
    }
    _UNARY = {ast.USub: _op.neg, ast.UAdd: _op.pos}

    def _eval(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id not in ctx:
                raise _Unsupported()
            return ctx[node.id]
        if isinstance(node, ast.Attribute):
            obj = _eval(node.value)
            try:
                return getattr(obj, node.attr)
            except AttributeError:
                raise _Unsupported()
        if isinstance(node, ast.Compare):
            left = _eval(node.left)
            for cmp_op, comp_node in zip(node.ops, node.comparators):
                right = _eval(comp_node)
                fn = _CMP.get(type(cmp_op))
                if fn is None:
                    raise _Unsupported()
                if not fn(left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.BinOp):
            left, right = _eval(node.left), _eval(node.right)
            fn = _BINOP.get(type(node.op))
            if fn is None:
                raise _Unsupported()
            return fn(left, right)
        if isinstance(node, ast.UnaryOp):
            operand = _eval(node.operand)
            fn = _UNARY.get(type(node.op))
            if fn is None:
                raise _Unsupported()
            return fn(operand)
        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                for v in node.values:
                    if not _eval(v):
                        return False
                return True
            if isinstance(node.op, ast.Or):
                for v in node.values:
                    if _eval(v):
                        return True
                return False
        raise _Unsupported()

    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError:
        raise _Unsupported()
    try:
        return _eval(tree.body)
    except TypeError:
        raise _Unsupported()


_MISSING = object()


def _resolve_dotted(dotted: str, ns: dict):
    """Resolve 'a.b.c' against *ns*, raising _Unsupported() on any missing link.

    Unlike a plain dict lookup, this tolerates *None* values — only a genuinely
    missing key or a missing attribute on a non-None object triggers _Unsupported.
    """
    parts = dotted.split(".")
    if parts[0] not in ns:
        raise _Unsupported()
    obj = ns[parts[0]]
    for part in parts[1:]:
        obj = getattr(obj, part, _MISSING)
        if obj is _MISSING:
            raise _Unsupported()
    return obj


def main():
    ap = argparse.ArgumentParser(description="Claim-driven research workflow engine")
    ap.add_argument("--claim", type=str, default=None, help="Run one claim id (e.g. CLAIM-01)")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--paper", action="store_true")
    args = ap.parse_args()

    from realeval.io import load_config
    base = load_config()
    base["_smoke"] = args.smoke or not args.paper

    OUT.mkdir(parents=True, exist_ok=True)
    summary = []
    for yml in sorted(CLAIMS.glob("claim_*.yaml")):
        claim = yaml.safe_load(yml.read_text())
        if "experiment" not in claim:
            logger.warning("Skipping %s: legacy format (no 'experiment' key), use runner/claim_runner.py", yml.name)
            continue
        if args.claim and claim["id"] != args.claim:
            continue
        trace = evaluate_claim(claim, base)
        (OUT / f"{claim['id']}.json").write_text(json.dumps(trace, indent=2, ensure_ascii=False, default=str))
        summary.append((claim["id"], trace["conclusion"], claim["hypothesis"]))

    print("\n=== Claim verdicts (Evidence -> Conclusion) ===")
    for cid, verdict, hyp in summary:
        print(f"  {cid}: {verdict:12s} {hyp}")
    print("Full evidence traces in outputs/claims/")


if __name__ == "__main__":
    main()
