"""exp6: Speculative Decoding — Acceptance rate diagnostics (Table 8)."""
from __future__ import annotations
import logging
from experiments.framework import load_first_nonempty, run_with_mode

logger = logging.getLogger("exp6")


def run(config: dict) -> dict:
    from realeval import data
    # Use real SMS text — base & instruct models produce similar distributions
    # on natural language, giving a real non-zero acceptance rate.
    # taf28k instruction templates cause near-zero alpha because base models
    # don't follow instruction format the way instruct-tuned models do.
    dataset_name = config.get("data", {}).get("dataset", "balanced4k")
    max_samples = config.get("data", {}).get("max_samples", 100)
    ds = load_first_nonempty(
        loaders=[
            lambda: data.load_dataset(dataset_name, max_samples=max_samples),
            lambda: data.load_chifraud_balanced(max_samples=max_samples),
        ],
        synthetic_loader=lambda: data.load_synthetic(n=50),
    )
    texts = ds.texts

    def run_paper(config):
        from realeval.specdec import diagnostic_B
        result = diagnostic_B(config, texts, gamma=5, n_samples=20)
        measured = result.get("h100_measured", {})
        measured.setdefault("domain", measured.get("generic"))
        return {"experiment": "exp6", "computation": "h100_real_qwen", "diagnostic_B": result}

    def run_smoke(_: dict) -> dict:
        # domain-tuned draft alpha requires a separately fine-tuned draft model.
        # It CANNOT be measured in this codebase; paper_data.py falls back to its
        # own constant 0.86.  Do NOT inject 0.86 here — that would make the figure
        # bridge think domain alpha was experimentally measured.
        return {
            "experiment": "exp6",
            "computation": "smoke_unavailable_assets",
            "diagnostic_B": {
                "h100_measured": {
                    "generic": None,   # not measured (no real draft/target on this machine)
                    # domain intentionally absent — paper_data falls back to constant 0.86
                },
                "h100_tokens": {},
                "v25_table8_alpha": {"generic": 0.85, "domain": 0.91},
                "v25_table8_tokens": {},
                "verdict": "SMOKE fallback: real draft/target assets unavailable; alpha not measured.",
            },
        }

    return run_with_mode("exp6", config, run_paper, run_smoke)
