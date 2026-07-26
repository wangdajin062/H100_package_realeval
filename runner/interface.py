"""runner/interface.py — Unified Experiment Interface

NOTE: The Experiment ABC is currently unused. All 14 experiments implement
standalone run(config) functions rather than subclassing Experiment. This module
defines the target interface for a future refactoring pass. See
experiments/runner.py for the active experiment registry and dispatch.

Target protocol:
  prepare() → run() → collect() → evaluate() → statistics() → export()

Each method returns a standardized result object; the runner orchestrates the pipeline.
No experiment is allowed to mix these concerns.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ExperimentResult:
    """Standardized result container flowing through the experiment pipeline."""
    experiment_id: str
    claim_ids: list[str] = field(default_factory=list)
    # prepare
    dataset_info: dict = field(default_factory=dict)
    model_info: dict = field(default_factory=dict)
    # run
    raw_predictions: list[dict] = field(default_factory=list)  # [{sample_id, prediction, ground_truth, ...}]
    latency_samples: list[float] = field(default_factory=list)
    memory_samples: list[float] = field(default_factory=list)
    # collect
    collected_metrics: dict = field(default_factory=dict)
    # evaluate (statistics)
    statistics: dict = field(default_factory=dict)  # {metric: {mean, std, ci_95, p_value, ...}}
    # evidence
    evidence: dict = field(default_factory=dict)
    # export
    export_paths: list[Path] = field(default_factory=list)
    # provenance
    provenance: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class Experiment(ABC):
    """Abstract base for all experiments.

    Subclasses implement each phase; the runner calls them in order.
    Phases are independent — modifying one doesn't affect others.
    """

    def __init__(self, config: dict):
        self.config = config
        self.result = ExperimentResult(
            experiment_id=config.get("experiment_id", self.__class__.__name__),
            claim_ids=config.get("claim_ids", []),
        )

    # ── Pipeline phases ──

    @abstractmethod
    def prepare(self) -> dict:
        """Load dataset, resolve model paths, validate inputs.
        Returns: {dataset_info, model_info}"""
        ...

    @abstractmethod
    def run(self) -> list[dict]:
        """Execute inference. Produces raw predictions.
        Returns: [{sample_id, prediction, ground_truth, latency_ms, ...}]"""
        ...

    def collect(self, predictions: list[dict]) -> dict:
        """Aggregate raw predictions into structured metrics. Override for custom aggregation.
        Returns: {metric_name: value}"""
        return {}

    def evaluate(self, metrics: dict) -> dict:
        """Compute statistics: bootstrap CI, effect size, significance tests.
        Returns: {metric_name: {mean, std, ci_95, p_value, effect_size}}"""
        return {}

    def export(self) -> list[Path]:
        """Save results to disk. Returns list of output paths."""
        return []

    # ── Orchestration (do not override) ──

    def execute(self) -> ExperimentResult:
        """Run the full pipeline. Catches and records errors per-phase."""
        phases = [
            ("prepare", self.prepare),
            ("run", self.run),
            ("collect", lambda: self.collect(self.result.raw_predictions)),
            ("evaluate", lambda: self.evaluate(self.result.collected_metrics)),
            ("export", self.export),
        ]
        for phase_name, phase_fn in phases:
            try:
                output = phase_fn()
                self._store_phase(phase_name, output)
            except Exception as e:
                self.result.errors.append(f"{phase_name}: {type(e).__name__}: {e}")
        return self.result

    def _store_phase(self, phase: str, output: Any):
        if phase == "prepare" and isinstance(output, dict):
            self.result.dataset_info = output.get("dataset_info", {})
            self.result.model_info = output.get("model_info", {})
            self.result.provenance = output.get("provenance", {})
        elif phase == "run" and isinstance(output, list):
            self.result.raw_predictions = output
        elif phase == "collect" and isinstance(output, dict):
            self.result.collected_metrics = output
        elif phase == "evaluate" and isinstance(output, dict):
            self.result.statistics = output
        elif phase == "export" and isinstance(output, list):
            self.result.export_paths = output
