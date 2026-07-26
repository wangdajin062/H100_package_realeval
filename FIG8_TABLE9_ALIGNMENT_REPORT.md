# Figure 8 & Table 9 Alignment Check Report
**Generated:** 2026-07-26  
**Status:** Figure 8 ⚠️ PARTIAL ALIGNMENT, Table 9 ✗ BLOCKED (exp12 missing)

---

## Executive Summary

Comprehensive check of **Figure 8** (3-panel revision ablations) and **Table 9** (FraudFusion baseline) against current archived experiment results, **excluding H100-only fields**.

| Component | Status | Key Finding |
|-----------|--------|-------------|
| Figure 8(a) Quantization | ⚠️ Incomplete | exp11 missing `schemes.int4.f1` |
| Figure 8(b) AdvFraud-3k | ⚠️ Partial | full_pool=1.0 (smoke), curated_subset never measured |
| Figure 8(c) LDP Trade-off | ✓ Data present | Both exp5 + exp8 present, but smoke-mode values (non-representative) |
| Table 9 FraudFusion | ✗ Blocked | **exp12 completely missing** |

---

## Detailed Findings

### Figure 8: Revision Ablations (3-Panel)

#### Panel (a): Quantization Scheme Ablation
**Paper Requirements (hardcoded):**
- Homogeneous INT4: F1 = 0.915
- Heterogeneous (NVFP4 + Q4_K_M): F1 = 0.923
- BF16 baseline: F1 = 0.931

**Experiment Source:** exp11  
**Archive Status:** ✓ exp11 present, but **schemes.int4.f1 = None**

| Field | Expected | Actual | Status |
|-------|----------|--------|--------|
| schemes.int4.f1 | 0.915 | None | ✗ MISSING |
| schemes.nvfp4_q4km.f1 | 0.923 | - | ⚠️ Not checked |

**Impact:** Panel (a) will use paper constant (no live experiment override)

---

#### Panel (b): AdvFraud-3k Robustness
**Paper Requirements (hardcoded):**
- Full pool (3,000 samples): F1 = 0.841
- Curated subset (517 samples): F1 = 0.875
- BF16 matched baseline: F1 = 0.882

**Experiment Source:** exp5  
**Archive Status:** ✓ exp5 present, **advfraud.full_pool.f1 = 1.0** (smoke_sklearn)

| Field | Expected | Actual | Diff | Reason |
|-------|----------|--------|------|--------|
| advfraud.full_pool.f1 | 0.841 | **1.0** | +18.9% | smoke_sklearn on synthetic features |
| advfraud.curated_subset.f1 | 0.875 | **None** | N/A | ✗ Never measured |

**Impact:** 
- Panel (b) will use paper constant (1.0 from smoke is too high, unrealistic)
- Curated subset ablation completely missing — cannot validate data robustness claim

**Key Issue:** exp5 runs `smoke_sklearn`, which trains GradientBoosting on synthetic verification features → F1≈1.0 is not representative of real Qwen performance

---

#### Panel (c): ε-LDP Privacy-Utility Trade-off
**Paper Requirements (hardcoded):**
- No LDP: F1 = 0.923, Latency P50 = 268.0 ms
- ε=1.5 LDP: F1 = 0.902, Latency P50 = 271.0 ms

**Experiment Sources:** exp5 (F1) + exp8 (latency)  
**Archive Status:** ✓ Both present, **values do NOT match paper**

| Field | Expected | Actual | Diff | Reason |
|-------|----------|--------|------|--------|
| ldp_tradeoff.no_ldp.f1 | 0.923 | **0.9962** | -7.9% | smoke_sklearn on synthetic data |
| ldp_tradeoff.eps_1.5.f1 | 0.902 | **0.8412** | +6.7% | smoke_sklearn on synthetic data |
| latencies.bf16 (ms) | 268.0 | **3.0621** | -98.9% | smoke_cpu (CPU inference, not H100) |

**Impact:**
- Panel (c) F1 values: slight mismatch from smoke mode (-7.9% and +6.7%)
- Panel (c) latency: HUGE mismatch (3ms vs 268ms) — smoke_cpu cannot measure H100 latency
- Solution: Figure will use paper constant latency (268→271 ms) but exp5 F1 values (overriding paper)

**Critical Issue:** exp5 and exp8 both run in smoke mode:
- exp5 = `smoke_sklearn` (CPU, synthetic features)
- exp8 = `smoke_cpu` (CPU, synthetic data)
- Therefore all Figure 8(c) metrics are non-representative of production H100 performance

---

### Table 9: FraudFusion Baseline Comparison

**Paper Requirement:** exp12 (exp12_fraudfusion_baseline.py → run_paper())

**Archive Status:** ✗ **exp12 COMPLETELY MISSING**

**Required Fields for Table 9:**
```
exp12
├── experiment: "exp12"
├── computation: "h100_real_qwen"
├── competitor_comparison_real
│   ├── QAD_MultiGuard_INT4
│   │   ├── f1: float (QAD+OVF F1 on TAF-28k)
│   │   └── source: "ours"
│   └── FraudFusion_pruned_INT4
│       ├── f1: null (no released weights)
│       └── source: "cited (no released weights)"
└── storage_decomposition_point8
    ├── footprints_mb
    │   ├── 7B_BF16_SAFE_QAQ: float (MB)
    │   ├── 0.5B_BF16: float (MB)
    │   └── 0.5B_Q4_K_M: float (MB)
    ├── quantization_alone_x: float (BF16 / Q4_K_M ratio)
    ├── param_scale_alone_x: float (7B / 0.5B ratio)
    └── total_advantage_x: float (product of above)
```

**Impact:** Table 9 cannot be auto-generated. **BLOCKING ISSUE**

---

## Root Cause Analysis

### Why Figure 8 Values Don't Match Paper Constants

| Factor | Impact | Reason |
|--------|--------|--------|
| **exp5 computation mode** | smoke_sklearn | Designed for CI testing: runs GradientBoosting on synthetic features, produces F1≈1.0 |
| **exp8 computation mode** | smoke_cpu | Designed for CI testing: runs inference on CPU with synthetic data, produces latency ≈ 3ms |
| **Paper constants in fig8_revision_ablations.py** | Hardcoded [0.923, 0.902] for F1 and [268.0, 271.0] for latency | These are from actual H100 paper run, not from current archive |
| **Data distribution** | smoke uses synthetic features, paper used real TAF-28k | GradientBoosting achieves F1≈1.0 on synthetic features but Qwen achieves F1≈0.90 on real data |

**Interpretation of User Query:** "除了需要H100跑的结果外"
> "Excluding H100-only results" means:
> - We're checking if non-H100 fields are present and correct
> - However, both exp5 and exp8 are currently in SMOKE mode (CI testing)
> - To get actual non-H100 results: exp5 needs `--paper` mode on H100 (for LDP privacy tests)
> - exp8 REQUIRES H100 to measure latency accurately (smoke_cpu is useless for latency)

---

## Alignment Matrix

| Field | Source | In Archive | Value | Paper Value | Aligned? |
|-------|--------|-----------|-------|-------------|----------|
| Fig 8(a) quant.int4 | exp11 | ✓ | **None** | 0.915 | ✗ No |
| Fig 8(a) quant.hetero | exp11 | ✓ | - | 0.923 | ? |
| Fig 8(b) advfraud.full | exp5 | ✓ | **1.0** | 0.841 | ✗ No (smoke) |
| Fig 8(b) advfraud.curated | exp5 | ✗ | - | 0.875 | ✗ No |
| Fig 8(c) ldp.no_ldp.f1 | exp5 | ✓ | **0.9962** | 0.923 | ✗ No (smoke) |
| Fig 8(c) ldp.eps1.5.f1 | exp5 | ✓ | **0.8412** | 0.902 | ✗ No (smoke) |
| Fig 8(c) latency.bf16 | exp8 | ✓ | **3.0621 ms** | 268.0 ms | ✗ No (smoke) |
| Table 9 qad.f1 | exp12 | ✗ | - | ? | ✗ No |
| Table 9 storage.total_x | exp12 | ✗ | - | ? | ✗ No |

---

## Blockers

### CRITICAL BLOCKER 1: Table 9 Completely Missing
- **What:** exp12 results not in archive
- **Why:** exp12 has never been run (or results deleted)
- **Impact:** Table 9 cannot be generated from live experiments
- **Resolution:** Run `python -m experiments.runner --exp 12 --paper` on H100

### BLOCKER 2: Figure 8 Values from Smoke Mode (Non-representative)
- **What:** exp5 and exp8 running in smoke mode (CI testing), not paper mode
- **Why:** Smoke mode is lightweight CPU testing with synthetic data
- **Impact:** 
  - exp5 F1 values overly optimistic (1.0 vs 0.9)
  - exp8 latency measurements garbage (3ms CPU ≠ 268ms H100)
- **Resolution:** 
  - Re-run: `python -m experiments.runner --exp 5 --paper` on H100
  - Re-run: `python -m experiments.runner --exp 8 --paper` on H100

### BLOCKER 3: exp11 Missing Quantization Results
- **What:** exp11.schemes.int4.f1 = None
- **Why:** Quantization ablation incomplete in exp11
- **Impact:** Figure 8(a) panel cannot show quantization comparison
- **Resolution:** Verify exp11 ran all quantization schemes, or re-run with full config

### BLOCKER 4: AdvFraud Curated Subset Never Measured
- **What:** exp5.advfraud.curated_subset field missing entirely
- **Why:** Experiment design only measured full_pool (3k) robustness
- **Impact:** Cannot show curated-subset vs full-pool robustness ablation
- **Resolution:** Extend exp5 to measure 517-sample curated subset separately

---

## Action Items (Priority Order)

### P1: CRITICAL
- [ ] **Run exp12 on H100** with `--paper` mode
  ```bash
  python -m experiments.runner --exp 12 --paper
  ```
  **Unblocks:** Table 9

### P2: HIGH
- [ ] **Re-run exp5 on H100** with `--paper` mode
  ```bash
  python -m experiments.runner --exp 5 --paper
  ```
  **Unblocks:** Figure 8(b) and 8(c) accuracy (replaces synthetic F1 values)

- [ ] **Re-run exp8 on H100** with `--paper` mode
  ```bash
  python -m experiments.runner --exp 8 --paper
  ```
  **Unblocks:** Figure 8(c) latency measurements

### P3: MEDIUM
- [ ] **Verify exp11 quantization** 
  ```bash
  python -m experiments.runner --exp 11 --paper
  ```
  **Check:** schemes.int4.f1, schemes.bf16.f1, etc. populated

- [ ] **Extend exp5 AdvFraud** to measure curated_subset (517 samples)
  **Unblocks:** Figure 8(b) second bar (curated-subset comparison)

### P4: DOCUMENTATION
- [ ] Archive results with timestamp: `scripts/archive_and_clear.py`
- [ ] Run: `check_fig8_table9_alignment.py` to re-validate

---

## Technical Notes

### Smoke Mode vs Paper Mode
| Aspect | Smoke Mode | Paper Mode |
|--------|-----------|-----------|
| **Computation** | sklearn on CPU | Real Qwen on H100 |
| **Data** | Synthetic features | Real dataset (TAF-28k, etc.) |
| **Speed** | ~1 sec | ~5-30 min per experiment |
| **Purpose** | CI/quick testing | Publication-quality results |
| **exp5 smoke** | GradientBoosting→F1≈1.0 | Qwen+LDP→F1≈0.92 |
| **exp8 smoke** | CPU inference→3ms | H100 inference→268ms |

### fig8_revision_ablations.py Strategy
- Uses **hardcoded DATA dict** (not experiment-driven like paper_data.py)
- Source of truth: `DATA = { "quant": {...}, "advfraud": {...}, "ldp": {...} }`
- When live exp results available AND representative (--paper mode), they SHOULD replace hardcoded values
- Current archive: all in smoke mode → hardcoded values will be used

### Archive Location
```
d:\Projects\H100_package_realeval\outputs\archive\2026-07-26_experiment_results.md
```

Experiments in archive:
```
✓ exp1, exp2, exp3, exp4, exp5, exp6, exp7, exp8, exp10, exp11
✗ exp9 (missing), exp12 (missing), exp13 (missing), exp14 (missing)
```

---

## Conclusion

### Alignment Status Summary
- **Figure 8 Panel (a):** ⚠️ Incomplete (exp11 missing int4 field)
- **Figure 8 Panel (b):** ⚠️ Partial (full_pool in smoke, curated_subset never measured)
- **Figure 8 Panel (c):** ⚠️ Data present but non-representative (smoke mode, using paper constants anyway)
- **Table 9:** ✗ **BLOCKED** (exp12 completely missing)

### Why Everything Uses Paper Constants
Because current exp5/exp8 are in **smoke mode** (not representative), the figure generation code defaults to **hardcoded paper constants** defined in `fig8_revision_ablations.py` and `paper_data.py`.

### Path to Full Alignment
1. Run exp12 (--paper) → Table 9 available ✓
2. Run exp5 (--paper) → Figure 8(b/c) F1 values from real Qwen ✓
3. Run exp8 (--paper) → Figure 8(c) latency from real H100 ✓
4. Extend exp5 → measure curated_subset ablation ✓
5. Verify exp11 → all quantization schemes present ✓

---

**Report Generated:** 2026-07-26  
**Analyzer:** check_fig8_table9_alignment.py  
**Archive:** outputs/archive/2026-07-26_experiment_results.md
