"""exp15: Modality ablation — text-only / audio-only / fused F1 (R3 A-road).

The reviewers flagged that no single-modality baselines were reported, so the
marginal contribution of the acoustic branch was never quantified. This experiment
computes, on the SAME leakage-safe TAF-28k test partition as exp1/exp5/exp13/exp14:

  * text-only  — the Qwen zero-shot soft score thresholded at 0.5 (the exact text
                 branch that feeds the fusion head in exp13).
  * audio-only — a logistic calibrator fit on the TRAIN acoustic feature (the
                 384-d Whisper-pooled encoder feature from ``taf28k.npz`` — the same
                 acoustic branch exp13's fusion consumes; NOT the 128-d F_v of
                 Eq.~\ref{eq:f-v}, whose real-F_v path is R2's ``build_fv_from_wav``),
                 scored on TEST.
  * fused      — the paper's sigmoid_linear decision-level fusion (Eq. fusion).

The ``marginal_contribution`` field reports the fused-vs-single deltas so the claim
"acoustic branch is the secondary contributor (w_audio=0.30 < w_text=0.40)" can be
reconciled with measured F1, not asserted.
"""
from __future__ import annotations
import logging

from experiments.framework import run_with_mode

logger = logging.getLogger("exp15")


def run(config: dict) -> dict:
    from realeval import data
    import numpy as np

    ds = data.load_taf28k(max_samples=config.get("data", {}).get("max_samples", 2000), source="multimodal")
    texts, labels = ds["texts"], ds["labels"]
    audio_emb = ds.get("embeddings")
    is_synthetic = False
    if not texts or audio_emb is None:
        ds = data.load_synthetic(n=200)
        texts, labels = ds["texts"], ds["labels"]
        audio_emb = ds["embeddings"]
        is_synthetic = True
    n = min(len(texts), len(audio_emb))
    texts, labels, audio_emb = texts[:n], labels[:n], np.asarray(audio_emb[:n])

    from experiments.common import shared_test_indices
    test_idx = shared_test_indices("taf28k", texts, labels)
    test_texts = [texts[i] for i in test_idx]
    test_labels = [labels[i] for i in test_idx]
    test_audio = audio_emb[test_idx]
    _test_set = set(test_idx)
    train_idx = [i for i in range(n) if i not in _test_set]
    train_texts = [texts[i] for i in train_idx]
    train_labels = [labels[i] for i in train_idx]
    train_audio = audio_emb[train_idx]

    def run_paper(config: dict) -> dict:
        from realeval import real_backend
        from realeval.metrics import classification_metrics
        from sklearn.linear_model import LogisticRegression
        import numpy as np

        quantize = config.get("training", {}).get("quantize", "nvfp4")

        # Text-only branch (the exact branch exp13 feeds into the fusion heads).
        txt = real_backend.real_llm_classify(
            config, test_texts, test_labels, quantize=quantize,
            return_preds=True, return_scores=True)
        txt_score = np.asarray(txt.get("scores") or txt["preds"], dtype=float)
        text_only = classification_metrics(test_labels, (txt_score >= 0.5).astype(int).tolist())

        # Audio-only branch: calibrator fit on the TRAIN acoustic feature only (no eval
        # leakage). NOTE: this is the 384-d Whisper-pooled feature (taf28k.npz), the same
        # acoustic branch exp13 fuses — not the 128-d F_v of Eq. f-v (R2 real-F_v path).
        ac_clf = LogisticRegression(max_iter=500).fit(train_audio, train_labels)
        audio_prob = ac_clf.predict_proba(test_audio)[:, 1]
        audio_only = classification_metrics(test_labels, (audio_prob >= 0.5).astype(int).tolist())

        # Fused (paper headline) for the marginal-contribution delta.
        fused = real_backend.real_fusion_classify(
            config, test_texts, test_labels, test_audio, quantize=quantize,
            fusion_strategy="sigmoid_linear",
            fit_data={"texts": train_texts, "labels": train_labels, "audio": train_audio},
            text_scores=txt_score)

        fused_f1 = fused.get("f1")
        delta_text = round(float(fused_f1 - text_only["f1"]), 4) if fused_f1 is not None else None
        delta_audio = round(float(fused_f1 - audio_only["f1"]), 4) if fused_f1 is not None else None

        return {
            "computation": "h100_real_qwen",
            "is_synthetic": is_synthetic,
            "quantize": quantize,
            "n_test": len(test_labels),
            "text_only": {"f1": text_only["f1"], "accuracy": text_only["accuracy"]},
            "audio_only": {"f1": audio_only["f1"], "accuracy": audio_only["accuracy"]},
            "fused": {"f1": fused_f1, "accuracy": fused.get("accuracy"),
                      "fusion_head": fused.get("fusion_head"),
                      "fusion_degraded": fused.get("fusion_degraded", False)},
            "marginal_contribution": {
                "fused_minus_text_only": delta_text,
                "fused_minus_audio_only": delta_audio,
                "note": "positive delta = the other modality adds over the single-modality baseline",
            },
        }

    return run_with_mode("exp15", config, run_paper)
