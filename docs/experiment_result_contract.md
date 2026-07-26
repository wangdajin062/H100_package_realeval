# Experiment Result Contract (for Figure Scripts)

This document defines the minimum JSON fields required by
`docs/figure_scripts/paper_data.py`.

## Required top-level fields for every experiment

- `experiment`: short id such as `exp1`
- `computation`: execution path such as `h100_real_qwen` or `smoke_sklearn`

## Figure-driven experiment contracts

- `exp1`
  - `f1: float`
  - `trajectory: list[dict]` with `ce` key used by Figure 4 bridge
- `exp2`
  - `variants.kl_only.f1`, `variants.kl_only.kl_final`
  - `variants.mse_only.f1`, `variants.mse_only.kl_final`
  - `variants.kl_mse_combined.f1`, `variants.kl_mse_combined.kl_final`
- `exp3`
  - `conditions.no_reg.variance_drift_pct`
  - `conditions.ov_freeze_full.f1`
  - `conditions.ov_freeze_full.variance_drift_pct`
  - `conditions.ov_freeze_half.variance_drift_pct`
  - `conditions.ov_freeze_quarter.variance_drift_pct`
  - `layer_selection.mid.variance_drift_pct`
  - `layer_selection.late.variance_drift_pct`
  - `rho_sweep.rho_0.0..rho_0.5` each with `f1` and `ppl`
- `exp5`
  - `taf28k.f1`
  - `chifraud.f1`
  - `advfraud.full_pool.f1`
- `exp6`
  - `diagnostic_B.h100_measured.generic`
  - `diagnostic_B.h100_measured.domain`
- `exp8`
  - `latencies.int4`, `latencies.fp16`, `latencies.bf16` (P50 milliseconds)
  - optional detail: `latency_detail.<quant>.p50_ms/p90_ms/p99_ms`
- `exp10`
  - `scales.teacher.f1`
  - `scales.teacher_1.5b.f1`
  - `scales.teacher_7b.f1`
- `exp11`
  - `schemes.int4.f1` (plus optional fp16/int8/nf4)

## Notes

- Baseline constants in figure scripts remain untouched by design.
- If an experiment does not provide a field, `paper_data.py` falls back to
  paper-verified constants.
- New experiments should preserve backward compatibility with these keys.

## Validation command

- Run `python -m experiments.runner --validate-contract` to check the latest
  result JSON files against this contract.
