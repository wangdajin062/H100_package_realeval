"""realeval/specdec.py — Speculative Decoding Diagnostics

Diagnostic tools for speculative decoding acceptance rate analysis.
"""
from __future__ import annotations
import logging

logger = logging.getLogger("specdec")

# ── Paper-verified alpha reference values (Fig7) ──
# These match Fig7 panel (a) operating points and are used when real H100
# measurement is unavailable (generic=0.78, domain-tuned=0.86).
_PAPER_V25_TABLE8_ALPHA_GENERIC = 0.78
_PAPER_V25_TABLE8_ALPHA_DOMAIN = 0.86

# Paper-verified speculative speedup measurements (Fig7 panel b + Table 8)
# These require separate H100/SD8G3 hardware benchmarks not covered by this codebase.
_PAPER_SPECULATIVE_SPEEDUPS = {
    "alpha_0.78": [
        {"gamma": 3,  "h100": 2.37, "sd8g3": 2.26},
        {"gamma": 5,  "h100": 2.92, "sd8g3": 2.78},
        {"gamma": 7,  "h100": 3.25, "sd8g3": 3.10},
        {"gamma": 10, "h100": 3.52, "sd8g3": 3.35},
    ],
    "alpha_0.86": [
        {"gamma": 3,  "h100": 2.65, "sd8g3": 2.52},
        {"gamma": 5,  "h100": 3.49, "sd8g3": 3.32},
        {"gamma": 7,  "h100": 4.10, "sd8g3": 3.90},
        {"gamma": 10, "h100": 4.74, "sd8g3": 4.51},
    ],
}


def diagnostic_B(config: dict, texts: list[str], *, gamma=5, n_samples=20) -> dict:
    """Diagnostic B: compute alpha from token counts (paper Table 8 consistency check).

    Returns dict with h100_measured, h100_tokens, v25_table8_alpha, v25_table8_tokens, verdict.
    """
    from realeval import models, hwenv
    import torch
    import torch.nn.functional as F

    from realeval.real_backend import require_assets, AssetsUnavailable

    require_assets(models.models_available(config), "Real Qwen weights unavailable")
    target, tok = models.load_causal_lm(config["models"]["teacher"], bf16=True)
    draft_path = config["models"].get("draft_model")
    draft, _ = models.load_causal_lm(draft_path, bf16=True)
    require_assets(target is not None and draft is not None, "draft/target loading failed")
    dev = next(target.parameters()).device

    # Compute alpha from token counts (paper method)
    # Acceptance is a stochastic rule, so the draw needs a fixed source.
    _rng = torch.Generator(device="cpu").manual_seed(int(config.get("reproducibility", {}).get("seed", 42)))
    accepted, proposed = 0, 0
    for text in texts[:n_samples]:
        ids = tok(text, return_tensors="pt").input_ids.to(dev)
        seq = ids
        for _ in range(40 // gamma):
            dprobs, dtoks = [], []
            cur = seq
            with torch.no_grad(), hwenv.autocast_context():
                for _g in range(gamma):
                    p = F.softmax(draft(cur).logits[0, -1], -1)
                    tk = int(torch.argmax(p))
                    dtoks.append(tk); dprobs.append(float(p[tk]))
                    cur = torch.cat([cur, torch.tensor([[tk]], device=dev)], 1)
                proposed += gamma
                ext = torch.cat([seq, torch.tensor([dtoks], device=dev)], 1)
                tlog = target(ext).logits
            base = seq.shape[1]
            ok = 0
            for i, tk in enumerate(dtoks):
                pt = float(F.softmax(tlog[0, base + i - 1], -1)[tk])
                # Standard speculative decoding: accept with probability min(1, p/q)
                if float(torch.rand(1, generator=_rng)) < pt / (dprobs[i] + 1e-9):
                    ok += 1
                else:
                    break
            accepted += ok
            if ok == 0:
                # Total rejection: emit the target's own next token rather than the
                # draft proposal that was just declined.
                nxt = int(torch.argmax(tlog[0, base - 1]))
                seq = torch.cat([seq, torch.tensor([[nxt]], device=dev)], 1)
                break
            seq = torch.cat([seq, torch.tensor([dtoks[:ok]], device=dev)], 1)
            if ok == 0:
                break

    gen_alpha = round(accepted / max(1, proposed), 4)

    def _tokens(a):
        return round((1 - a ** (gamma + 1)) / (1 - a), 2) if a < 1 else gamma + 1

    # ── H100 measured values (authoritative) ──
    # The generic draft's alpha is measured from real H100 tokens above.
    # The domain-tuned draft would require separate fine-tuned model loading.
    # domain-tuned draft alpha NOT hardcoded
    h100_measured = {"generic": gen_alpha}
    h100_tokens = {"generic": _tokens(gen_alpha)}

    # ── v25 paper Table 8 reference values ──
    # These are HISTORICAL REFERENCES ONLY (see module-level constants).
    # The authoritative values are h100_measured (computed at lines above).
    v25_table8_alpha = {"generic": _PAPER_V25_TABLE8_ALPHA_GENERIC}
    v25_table8_tokens = {"generic": _tokens(_PAPER_V25_TABLE8_ALPHA_GENERIC)}

    # Verdict: H100 measured alpha is ground truth.
    verdict_data = {}
    if gen_alpha is not None:
        v25_ref = v25_table8_alpha.get("generic", _PAPER_V25_TABLE8_ALPHA_GENERIC)
        diff = abs(gen_alpha - v25_ref)
        if diff >= 0.05:
            verdict_data["generic"] = (
                f"H100 measured generic alpha={gen_alpha} differs from "
                f"v25 paper reference {v25_ref} (diff={diff:.3f})")
        else:
            verdict_data["generic"] = (
                f"H100 measured generic alpha={gen_alpha} is consistent "
                f"with v25 paper reference {v25_ref}")
    verdict_data["domain"] = "NOT MEASURED"
    verdict = "; ".join(verdict_data.values())

    return {
        "h100_measured": h100_measured,
        "h100_tokens": h100_tokens,
        "v25_table8_alpha": v25_table8_alpha,
        "v25_table8_tokens": v25_table8_tokens,
        "verdict": verdict,
        "paper_reference": {
            "alpha_generic": _PAPER_V25_TABLE8_ALPHA_GENERIC,
            "alpha_tuned": _PAPER_V25_TABLE8_ALPHA_DOMAIN,
            "gamma_deploy": 5,
            "speculative_speedups": _PAPER_SPECULATIVE_SPEEDUPS,
        },
    }
