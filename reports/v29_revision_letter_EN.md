# Response to Reviewers

**Manuscript:** QAD-MultiGuard: An Edge–Cloud Framework for Multimodal Fraud Detection and Risk Assessment
**Journal:** Expert Systems with Applications
**Decision:** Major Revision
**Revision:** v28 → v29
**Date:** 2026-08-27

---

Dear Editor and Reviewers,

We thank you for the thorough and constructive review of our manuscript. We have carefully addressed each comment in the revised version (v29). Reviewer comments are summarised in *italics*, our responses follow in plain text, and manuscript changes are located by line reference. Where a requested change is an experiment-level item (a hardware re-run or a new baseline) rather than a text revision, we state its status explicitly rather than overclaim completion.

## Summary of Changes

The revised manuscript (i) converges the headline claims to the controlled-environment evidence boundary (abstract, highlights, conclusion), (ii) states the novelty boundary of the contribution explicitly, and (iii) further qualifies the SAFE-QAQ comparison at the point of use. Reproducibility backfill (R1) and the additional LoRA/Adapter baseline (R4) require H100 re-runs; their status is reported below.

---

## Point-by-Point Response

### R1 — Reproducibility of the core results (Critical)

*The public repository does not currently reproduce the NVFP4 QAD main tables, leaving the formal H100 run as the sole authority.*

**Response.** We acknowledge this limitation. The Reproducibility statement (L509) already commits to backfilling the QAT/NBE path (Eq. 5) and adding an exact commit pointer once the reproduction run completes. This is a hardware-run item, not a text revision; we will complete the re-run and add the pointer before final acceptance.

---

### R2 — Calibration of headline claims (Major)

*"practical template" / "real-time … on commodity hardware" overstate the controlled-environment evidence; the 2.1× figure needs explicit NBE qualification.*

**Response.** Done. We made five edits that converge the claims to the evidence boundary:

- **Abstract (L76):** "real-time … without sacrificing accuracy, offering a practical template" → "near-real-time … at a small accuracy cost, establishing a feasibility baseline … generalisation to unconstrained real-world deployment remains to be validated through field studies."
- **Highlight #4 (L83):** the speculative-decoding speedup is now scoped to "the cloud-side review draft model."
- **Highlight #5 (L84):** the on-device result is now scoped to "the TAF-28k benchmark."
- **Contribution statement (L147):** the novelty boundary is stated explicitly (see R4).
- **Conclusion (L909):** "indicating suitability for real-time edge deployment under the evaluated conditions" → "indicating feasibility for real-time edge deployment under the evaluated benchmark conditions."

The 2.1× figure is already qualified as an isolated compute-kernel throughput margin under the NBE protocol in three places: Table 2 note (L318), §System-level interpretation (L336), and §Measurement scope (L507). No headline-level change was therefore required for this number.

---

### R3 — Fairness of the SAFE-QAQ comparison (Major)

*SAFE-QAQ is a cited, different-scale, different-deployment-target baseline; the 57× comparison should not read as a like-for-like competition.*

**Response.** Done. The Table 3 footnote (L665) already identifies SAFE-QAQ as a high-capacity reference baseline at a different scale (7B vs. 0.5B) and deployment target, cited from [2] rather than reproduced in-house. The main-results paragraph (L684) now additionally labels it "a cited reference point at a different scale and deployment target, not a like-for-like competitor", and reports the 57× figure as "a deployment-efficiency observation rather than an accuracy claim on equal footing".

---

### R4 — Novelty boundary and the fine-tuning-vs-distillation confound (Major)

*Clarify which components are new versus domain-adapted combinations, and add a LoRA/Adapter-finetune + PTQ baseline to rule out the alternative explanation that the gain stems from fine-tuning rather than the pure-KL objective.*

**Response.**
1. **Novelty boundary (done).** The contribution statement (L147) now states: "The novelty lies not in any single component—each draws on established techniques—but in their integrated co-design and empirical validation for privacy-constrained on-device fraud detection, a multimodal setting that existing single-modality and server-only baselines do not address."
2. **Confounding baseline (designed, to be run).** We have specified the LoRA/Adapter-finetune + 4-bit PTQ baseline (see the accompanying design note). It isolates the pure-KL objective from domain fine-tuning by keeping training budget, quantisation protocol, and evaluation identical to the QAD pipeline. It will be run and added to Table 3 in the next round.

---

### S1–S4 — Suggested revisions

- **S1 (effect size for the +0.007 F₁ OV-Freeze gain).** Planned — we will add a standardised effect size alongside the existing 95% CI ([+0.31, +1.08] pp, L505) to justify the practical significance.
- **S2 (field/pilot evidence).** Planned — the Discussion (L898) already notes a planned pilot deployment; if a pilot is not feasible within the revision window, we will explicitly downgrade it to future work.
- **S3 (privacy-embedding ablation).** Planned — we will disentangle the Whisper-tiny information bottleneck from the MFCC+pooling design in accounting for WER ≥ 0.95.
- **S4 (power analysis for speaker identification).** Planned — we will add a sample-size/power analysis for the 11-speaker closed-set result (8.3% vs. 9.1% chance baseline).

---

We believe these revisions materially strengthen the manuscript's claim calibration and reproducibility posture, and we look forward to your further feedback.

Sincerely,

The Authors
