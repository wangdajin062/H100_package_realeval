"""exp3: OV-Freeze Control — projection-layer selection + rescale-strength sweep."""
from __future__ import annotations
import logging

from experiments.framework import run_with_mode
from experiments.common import (
    load_and_split_dataset,
    multi_seed_std,
    n_seeds_from_config,
    seed_base_from_config,
    set_seed,
)

logger = logging.getLogger("exp3")


def run(config: dict) -> dict:
    split = load_and_split_dataset(config, default_dataset="taf28k")

    def _train(cfg: dict, ovf_layers: tuple[str, ...], rescale_strength: float,
               need_ppl: bool = False) -> tuple[float, float, float | None]:
        from realeval import real_backend

        # ovf_layers / rescale_strength are FUNCTION PARAMS of real_qad_distill_train,
        # NOT read from config. Must pass them as kwargs, otherwise every condition
        # silently runs the default (("q","v","k","o") / 1.0) and the OV-Freeze ablation
        # collapses to identical results (regression introduced by the 307c679 refactor).
        result = real_backend.real_qad_distill_train(
            cfg,
            split.train_texts, split.train_labels,
            split.test_texts, split.test_labels,
            quantize="nvfp4", apply_ov_rescaling=True,
            loss_fn="pure_kl",   # 论文 Table 4 的 QAD+OVF 是纯 KL + OVF
            ovf_layers=ovf_layers, rescale_strength=rescale_strength,
            compute_ppl=need_ppl,   # real LM perplexity (Fig6b) — only the strength sweep needs it
        )
        drift = result.get("drift_pct_final", 0.0)
        # Real causal-LM perplexity exp(−mean token NLL) computed inside the backend
        # (audit P1-2); the old exp(min(KL,10)) pseudo-perplexity was merely a monotone
        # transform of the distillation KL and could not support the paper's PPL-fluctuation
        # claim. None when need_ppl=False — layer-selection / conditions ignore PPL and
        # skip the full test-set forward.
        ppl = result.get("ppl")
        return float(result["f1"]), drift, ppl

    def run_paper(config: dict) -> dict:
        import numpy as np
        n_seeds = n_seeds_from_config(config, "exp3")

        # Layer selection (paper Fig6a, q→v→k→o cumulative order): which attention
        # projection layers receive OV-Freeze. These replace the old early/mid/late/all
        # "freeze_frac" dimension-ratio keys with real projection-layer subsets, so the
        # paper's q / q,v / q,k,v / q,k,v,o bars are produced directly (no FFN alias).
        layer_specs = [
            ("q",       ("q",)),
            ("q_v",     ("q", "v")),
            ("q_v_k",   ("q", "v", "k")),
            ("q_v_k_o", ("q", "v", "k", "o")),
        ]
        layer_selection: dict[str, dict] = {}
        for name, layers in layer_specs:
            f1s, drifts = [], []
            for s in range(n_seeds):
                set_seed(seed_base_from_config(config) + s)
                f1, drift, _ = _train(config, layers, 1.0)
                f1s.append(f1)
                drifts.append(drift)
            layer_selection[name] = {
                "f1": round(float(np.mean(f1s)), 4),
                "variance_drift_pct": round(float(np.mean(drifts)), 1),
                "std": multi_seed_std(f1s),
            }

        # Rescale-strength sweep: interpolates the forward rescaling factor (Eq.8)
        # between none (0.0) and the full c_ℓ (1.0). The variance-matching loss L_OVF
        # stays active throughout; this isolates the incremental contribution of the
        # stop-gradient forward rescaling term (paper Lemma A.1 / Prop A.2). The
        # production strength is 1.0 (full rescaling), included as the sweep's endpoint.
        window_sweep: dict[str, dict] = {}
        for strength in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]:
            f1s, drifts = [], []
            ppl = None
            for s in range(n_seeds):
                set_seed(seed_base_from_config(config) + s)
                f1, drift, ppl = _train(config, ("q", "v", "k", "o"), strength, need_ppl=True)
                f1s.append(f1)
                drifts.append(drift)
            # ppl = last seed's value, taken from the loop above. (Previously this ran an
            # EXTRA, unseeded _train() per strength — non-reproducible and ~6 wasted trainings.)
            window_sweep[f"strength_{strength}"] = {
                "f1": round(float(np.mean(f1s)), 4),
                "ppl": round(ppl, 3) if ppl is not None else None,
                "variance_drift_pct": round(float(np.mean(drifts)), 1),
                "std": multi_seed_std(f1s),
            }

        # Four-condition control: no OV-Freeze vs partial vs full projection-layer set.
        cond_specs = [
            ("no_reg",            ()),
            ("ov_freeze_quarter", ("q",)),
            ("ov_freeze_half",    ("q", "v")),
            ("ov_freeze_full",    ("q", "v", "k", "o")),
        ]
        conditions: dict[str, dict] = {}
        for name, layers in cond_specs:
            f1s, drifts = [], []
            for s in range(n_seeds):
                set_seed(seed_base_from_config(config) + s)
                f1, drift, _ = _train(config, layers, 1.0)
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
            "window_sweep": window_sweep,
            "conditions": conditions,
        }

    return run_with_mode("exp3", config, run_paper)
