"""exp9: CoT Ablation — Compare chain-of-thought vs direct classification."""
from __future__ import annotations
import logging
from experiments.framework import leakage_safe_split, load_first_nonempty, run_with_mode

logger = logging.getLogger("exp9")


def run(config: dict) -> dict:
    from realeval import data
    ds = load_first_nonempty(
        loaders=[lambda: data.load_dataset(config.get("data", {}).get("dataset", "taf28k"),
                                           max_samples=config.get("data", {}).get("max_samples", 1000))],
        synthetic_loader=lambda: data.load_synthetic(n=100),
    )
    split = leakage_safe_split(ds, test_ratio=0.1, seed=42)

    def run_paper(config: dict) -> dict:
        from realeval import real_backend
        from experiments.common import resolve_qad_path

        qad_path = resolve_qad_path()
        finetuned_path = str(qad_path) if qad_path.exists() else None

        # no-CoT: uses fine-tuned head (head(last_hidden).argmax(1)).
        direct = real_backend.real_llm_classify(
            config, split.test_texts, split.test_labels, quantize="int4", use_cot=False,
            finetuned_path=finetuned_path,
        )
        # CoT: SAME fine-tuned model + head. The fine-tuned path now handles use_cot by
        # generating a short reasoning trace first, then head-scoring the (prompt+reasoning)
        # hidden state. Passing finetuned_path is now correct — it no longer bypasses CoT.
        # This isolates CoT as the ONLY variable (vs the old base-generate vs finetuned-head
        # confound). A null/negative effect is now a faithful CoT result.
        cot = real_backend.real_llm_classify(
            config, split.test_texts, split.test_labels, quantize="int4", use_cot=True,
            finetuned_path=finetuned_path,
        )
        return {"computation": "h100_real_qwen",
                "with_cot": {"f1": cot["f1"], "fpr": cot.get("fpr"),
                             "note": "fine-tuned model+head, CoT reasoning generated first "
                                     "(matched to no-CoT; only CoT differs)"},
                "without_cot": {"f1": direct["f1"], "fpr": direct.get("fpr"),
                                "note": "fine-tuned head path — head(last_hidden).argmax(1), "
                                        "matched to training paradigm"}}

    return run_with_mode("exp9", config, run_paper)
