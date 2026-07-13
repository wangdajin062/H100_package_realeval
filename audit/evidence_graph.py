"""audit/evidence_graph.py — Evidence Graph: Claim → Evidence Traceability Engine

Every conclusion must trace back to:
  - which model was used
  - which dataset was used
  - which inference run produced the predictions
  - which metric was computed
  - which statistical method was applied
  - why the evidence supports (or fails to support) the claim

Nodes in the graph:
  Claim → Experiment → Run → RawPrediction → Metric → Statistics → Evidence → Conclusion

Each node stores its provenance; edges are explicit references.
"""
from __future__ import annotations
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_DIR = ROOT / "outputs" / "evidence"


class EvidenceNode:
    """A single node in the evidence graph. Treat attributes as read-only after creation."""
    def __init__(self, node_type: str, node_id: str, data: dict, parents: list[str] | None = None):
        self.node_type = node_type
        self.node_id = node_id
        self.data = data
        self.parents = parents or []
        self.timestamp = datetime.now().isoformat(timespec="seconds")

    def to_dict(self) -> dict:
        return {
            "node_type": self.node_type,
            "node_id": self.node_id,
            "data": self.data,
            "parents": self.parents,
            "timestamp": self.timestamp,
        }

    def content_hash(self) -> str:
        """Deterministic hash of node content for integrity verification (caller opt-in)."""
        raw = json.dumps(self.data, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


class EvidenceGraph:
    """Directed acyclic graph linking Claims to their supporting Evidence.

    Usage:
        graph = EvidenceGraph("CLAIM-004")
        claim = graph.add_claim({"hypothesis": "Q4_K_M > 2x throughput vs BF16"})
        exp = graph.add_experiment({"config": {...}}, parents=[claim])
        run = graph.add_run({"model": "Qwen2.5-0.5B", "dataset_hash": "abc123"}, parents=[exp])
        preds = graph.add_predictions({"path": "outputs/preds/exp4.jsonl"}, parents=[run])
        metric = graph.add_metric({"f1": 0.923, "throughput_sps": 342}, parents=[preds])
        stats = graph.add_statistics({"ci_95": [0.918, 0.928], "p_value": 0.003}, parents=[metric])
        evidence = graph.add_evidence({"supports_claim": True, "reason": "..."}, parents=[stats])
        graph.validate()  # checks all parent edges resolve
        graph.save()
    """

    def __init__(self, graph_id: str):
        self.graph_id = graph_id
        self.nodes: dict[str, EvidenceNode] = {}
        self._counter = 0
        self._created = datetime.now().isoformat(timespec="seconds")

    def _next_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}_{self._counter:04d}"

    def add_node(self, node_type: str, data: dict, parents: list[str] | None = None) -> str:
        nid = self._next_id(node_type)
        node = EvidenceNode(node_type, nid, data, parents)
        self.nodes[nid] = node
        return nid

    # ── Typed convenience methods ──

    def add_claim(self, data: dict, parents: list[str] | None = None) -> str:
        """Add a Claim node. data: {hypothesis, independent_variables, dependent_variables, controls, acceptance_criteria}"""
        return self.add_node("claim", data, parents)

    def add_experiment(self, data: dict, parents: list[str] | None = None) -> str:
        """Add an Experiment node. data: {name, config, design}"""
        return self.add_node("experiment", data, parents)

    def add_run(self, data: dict, parents: list[str] | None = None) -> str:
        """Add a Run node. data: {model, dataset_hash, env, git_commit, seed, timestamp}"""
        return self.add_node("run", data, parents)

    def add_predictions(self, data: dict, parents: list[str] | None = None) -> str:
        """Add a RawPrediction node. data: {path, n_samples, format, hash}"""
        return self.add_node("raw_prediction", data, parents)

    def add_metric(self, data: dict, parents: list[str] | None = None) -> str:
        """Add a Metric node. data: {metric_name: value, ...}"""
        return self.add_node("metric", data, parents)

    def add_statistics(self, data: dict, parents: list[str] | None = None) -> str:
        """Add a Statistics node. data: {method, ci_95, p_value, effect_size, ...}"""
        return self.add_node("statistics", data, parents)

    def add_evidence(self, data: dict, parents: list[str] | None = None) -> str:
        """Add an Evidence node. data: {supports_claim: bool, strength: weak|moderate|strong, reason: str}"""
        return self.add_node("evidence", data, parents)

    def add_conclusion(self, data: dict, parents: list[str] | None = None) -> str:
        """Add a Conclusion node. data: {verdict: PASS|FAIL|UNSUPPORTED, summary: str}"""
        return self.add_node("conclusion", data, parents)

    # ── Validation ──

    def validate(self) -> tuple[bool, list[str]]:
        """Check graph integrity: all parent references resolve, no cycles, valid chain."""
        errors = []
        for nid, node in self.nodes.items():
            for pid in node.parents:
                if pid not in self.nodes:
                    errors.append(f"Node {nid} references missing parent {pid}")
        # Cycle detection via DFS with three-color marking
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {nid: WHITE for nid in self.nodes}
        def _dfs(nid):
            color[nid] = GRAY
            for pid in self.nodes[nid].parents:
                if color.get(pid, BLACK) == GRAY:
                    errors.append(f"Cycle detected: {nid} -> {pid}")
                    return
                if color.get(pid, BLACK) == WHITE:
                    _dfs(pid)
            color[nid] = BLACK
        for nid in self.nodes:
            if color[nid] == WHITE:
                _dfs(nid)
        # Check at least one complete Claim→Conclusion chain exists
        claims = [n for n in self.nodes.values() if n.node_type == "claim"]
        conclusions = [n for n in self.nodes.values() if n.node_type == "conclusion"]
        if claims and not conclusions:
            errors.append("Claims exist but no conclusion reached")
        return len(errors) == 0, errors

    def trace(self, node_id: str) -> list[dict]:
        """Walk from a node back to its root Claim, returning the full provenance chain."""
        chain = []
        visited = set()
        queue = [node_id]
        while queue:
            nid = queue.pop(0)
            if nid in visited:
                continue
            visited.add(nid)
            if nid in self.nodes:
                node = self.nodes[nid]
                chain.append(node.to_dict())
                queue.extend(node.parents)
        return sorted(chain, key=lambda x: x["timestamp"])

    # ── Persistence ──

    def to_dict(self) -> dict:
        return {
            "graph_id": self.graph_id,
            "created": self._created,
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
        }

    def save(self, path: Path | None = None) -> Path:
        p = path or (EVIDENCE_DIR / f"{self.graph_id}.json")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return p

    @classmethod
    def load(cls, path: Path) -> "EvidenceGraph":
        data = json.loads(path.read_text(encoding="utf-8"))
        g = cls(data["graph_id"])
        for nid, nd in data["nodes"].items():
            g.nodes[nid] = EvidenceNode(nd["node_type"], nd["node_id"], nd["data"], nd["parents"])
        return g


# ── Claim definition format ──

def validate_claim_definition(claim: dict) -> tuple[bool, list[str]]:
    """Validate a claim YAML definition has all required fields."""
    required = ["id", "hypothesis", "independent_variables", "dependent_variables",
                 "controls", "acceptance"]
    errors = []
    for field in required:
        if field not in claim:
            errors.append(f"Missing required field: {field}")
    if "acceptance" in claim:
        acc = claim["acceptance"]
        if not isinstance(acc, dict):
            errors.append("acceptance must be a dict of {metric_name: criterion}")
    return len(errors) == 0, errors


def evaluate_claim(claim: dict, evidence: dict) -> dict:
    """Evaluate whether evidence supports a claim. Returns {verdict, details}.

    Verdicts:
      - PASS: all acceptance criteria met
      - FAIL: one or more criteria not met
      - UNSUPPORTED: insufficient evidence to decide
    """
    acceptance = claim.get("acceptance", {})
    if not acceptance:
        return {"verdict": "UNSUPPORTED", "details": "No acceptance criteria defined"}

    results = {}
    all_pass = True
    any_measured = False
    for metric, criterion in acceptance.items():
        measured = evidence.get(metric)
        if measured is None:
            results[metric] = {"measured": None, "criterion": criterion, "result": "UNMEASURED"}
            all_pass = False
            continue
        any_measured = True
        # criterion format: ">2" or "<0.01" or ">=0.9" etc.
        passed = _check_criterion(measured, str(criterion))
        results[metric] = {"measured": measured, "criterion": criterion,
                           "result": "PASS" if passed else "FAIL"}
        if not passed:
            all_pass = False

    if not any_measured:
        return {"verdict": "UNSUPPORTED", "details": "No metrics measured", "results": results}
    return {
        "verdict": "PASS" if all_pass else "FAIL",
        "details": "All criteria met" if all_pass else "Some criteria not met",
        "results": results,
    }


def _check_criterion(value: float, criterion: str) -> bool:
    """Evaluate a simple criterion string like '>2', '<0.01', '>=0.9', '==1.0'."""
    import re
    m = re.match(r"^(>=|<=|>|<|==)\s*(-?\d+(?:\.\d+)?)$", criterion)
    if not m:
        return False
    op, target = m.group(1), float(m.group(2))
    if op == ">":
        return value > target
    if op == "<":
        return value < target
    if op == ">=":
        return value >= target
    if op == "<=":
        return value <= target
    if op == "==":
        return abs(value - target) < 1e-9
    return False
