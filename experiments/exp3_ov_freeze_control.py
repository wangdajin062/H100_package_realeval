"""exp3: OV-Freeze Control — 4-condition ablation + layer selection + rho sweep."""
from __future__ import annotations
import logging

from experiments.framework import run_with_mode
from experiments.common import (
    config_override,
    load_and_split_dataset,
    multi_seed_std,
    n_seeds_from_config,
    set_seed,
)

logger = logging.getLogger("exp3")


def run(config: dict) -> dict:
    split = load_and_split_dataset(config, default_dataset="balanced4k")

    def _train(cfg: dict, frac: float, window: float, rho: float) -> tuple[float, float, float]:
        from realeval import real_backend
        import math

        overrides = config_override(cfg, training={
            "freeze_frac": frac, "window": window, "rho": rho,
        })
        result = real_backend.real_qad_distill_train(
            overrides,
            split.train_texts, split.train_labels,
            split.test_texts, split.test_labels,
            quantize="int4", apply_ov_rescaling=True,
            # freeze_frac/window are FUNCTION PARAMS of real_qad_distill_train, NOT read
            # from config. Must pass them as kwargs, otherwise every condition silently
            # runs the default (1.0/1.0) and the OV-Freeze ablation collapses to identical
            # results (regression introduced by the 307c679 refactor).
            freeze_frac=frac, window=window, rho=rho,
        )
        drift = result.get("drift_pct_final", 0.0)
        ppl = math.exp(min(result.get("kl_final", 10.0), 10.0))
        return float(result["f1"]), drift, ppl

    def run_paper(config: dict) -> dict:
        import numpy as np
        n_seeds = n_seeds_from_config(config, "exp3")

        layer_specs = [
            ("early", 0.25, 0.25),
            ("mid", 0.5, 0.5),
            ("late", 0.75, 0.75),
            ("all", 1.0, 1.0),
        ]
        layer_selection: dict[str, dict] = {}
        for name, frac, window in layer_specs:
            f1s, drifts = [], []
            for s in range(n_seeds):
                set_seed(1000 + s)
                f1, drift, _ = _train(config, frac, window, 1.0)
                f1s.append(f1)
                drifts.append(drift)
            layer_selection[name] = {
                "f1": round(float(np.mean(f1s)), 4),
                "variance_drift_pct": round(float(np.mean(drifts)), 1),
                "std": multi_seed_std(f1s),
            }

        rho_sweep: dict[str, dict] = {}
        for rho_val in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]:
            f1s, drifts = [], []
            for s in range(n_seeds):
                set_seed(1000 + s)
                # rho sweeps the OV-Freeze activation WINDOW (freeze_frac stays 1.0).
                # rho=0 disables OV-Freeze entirely (freeze_frac=0), matching v25 semantics.
                f1, drift, _ = _train(config, 1.0 if rho_val > 0 else 0.0, rho_val, rho_val)
                f1s.append(f1)
                drifts.append(drift)
            # ppl from last seed only (diagnostic)
            _, _, ppl = _train(config, 1.0 if rho_val > 0 else 0.0, rho_val, rho_val)
            rho_sweep[f"rho_{rho_val}"] = {
                "f1": round(float(np.mean(f1s)), 4),
                "ppl": round(ppl, 3),
                "variance_drift_pct": round(float(np.mean(drifts)), 1),
                "std": multi_seed_std(f1s),
            }

        cond_specs = [
            ("no_reg", 0.0, 0.0, 1.0),
            ("ov_freeze_quarter", 0.25, 0.25, 1.0),
            ("ov_freeze_half", 0.5, 0.5, 1.0),
            ("ov_freeze_full", 1.0, 1.0, 1.0),
        ]
        conditions: dict[str, dict] = {}
        for name, frac, window, rho in cond_specs:
            f1s, drifts = [], []
            for s in range(n_seeds):
                set_seed(1000 + s)
                f1, drift, _ = _train(config, frac, window, rho)
                f1s.append(f1)
                drifts.append(drift)
            conditions[name] = {
                "f1": round(float(np.mean(f1s)), 4),
                "variance_drift_pct": round(float(np.mean(drifts)), 1),
                "std": multi_seed_std(f1s),
            }

        return {
            "computation": "h100_real_qwen",
            "layer_selection": layer_selection,
            "rho_sweep": rho_sweep,
            "conditions": conditions,
        }

    return run_with_mode("exp3", config, run_paper)
