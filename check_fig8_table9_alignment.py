#!/usr/bin/env python3
"""
FINAL ALIGNMENT REPORT: Figure 8 & Table 9 vs Archived Experiment Results
==========================================================================

Purpose: Check complete alignment between paper requirements (Figure 8, Table 9)
and current experiment results in archive, EXCLUDING H100-only fields.

User Query: "检查文档结果和论文中8图和9表中的所需变量结果和字段是否完全对齐，除了需要H100跑的结果外。"
Translation: "Check if Figure 8 & Table 9 required fields completely align with archived 
results, excluding H100-only results."
"""

import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Load archive
arc = ROOT / "outputs" / "archive" / "2026-07-26_experiment_results.md"
chunks = re.split(r"### (exp\d+) .+\n\n```json\n", arc.read_text("utf-8"))
exps = {}
for i in range(1, len(chunks), 2):
    name, body = chunks[i], chunks[i + 1].split("\n```")[0]
    try:
        exps[name] = json.loads(body)
    except:
        pass

print("\n" + "=" * 130)
print("FIGURE 8 & TABLE 9 ALIGNMENT REPORT (Excluding H100-Only Results)")
print("=" * 130)

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: FIGURE 8 REQUIREMENTS & STATUS
# ─────────────────────────────────────────────────────────────────────────────

print("\n[1] FIGURE 8: Revision Ablations (3-panel)")
print("-" * 130)

FIG8_SPEC = {
    "panel_a": {
        "title": "Quantization scheme ablation (INT4 vs heterogeneous)",
        "paper_source": "fig8_revision_ablations.py hardcoded DATA dict",
        "requires": "exp11 quantization results (or use paper constant 0.931)",
        "paper_values": {"homogeneous_int4_f1": 0.915, "heterogeneous_f1": 0.923, "bf16_ref": 0.931},
        "fields_to_check": ["schemes.int4.f1", "schemes.nvfp4_q4km.f1"],
    },
    "panel_b": {
        "title": "AdvFraud-3k curated vs full pool robustness",
        "paper_source": "fig8_revision_ablations.py hardcoded DATA dict (computed from paper, not exp5)",
        "requires": "exp5 advfraud.full_pool F1 + exp5 advfraud.curated_subset (517) F1",
        "paper_values": {"full_pool_f1": 0.841, "curated_517_f1": 0.875, "bf16_matched": 0.882},
        "fields_to_check": ["advfraud.full_pool.f1", "advfraud.curated_subset.f1"],
    },
    "panel_c": {
        "title": "ε-LDP privacy-utility trade-off",
        "paper_source": "fig8_revision_ablations.py hardcoded DATA dict (computed from paper, not exp5+exp8)",
        "requires": "exp5 ldp_tradeoff.no_ldp.f1 + exp5 ldp_tradeoff.eps_1.5.f1 + exp8 latencies",
        "paper_values": {"no_ldp_f1": 0.923, "eps_1p5_f1": 0.902, "lat_no_ldp_ms": 268.0, "lat_eps_ms": 271.0},
        "fields_to_check": ["ldp_tradeoff.no_ldp.f1", "ldp_tradeoff.eps_1.5.f1", "latencies.bf16"],
    }
}

fig8_results = {}

# Panel A
print("\nPanel (a) Quantization scheme:")
print(f"  Paper values: homogeneous INT4 F1={FIG8_SPEC['panel_a']['paper_values']['homogeneous_int4_f1']}, "
      f"heterogeneous F1={FIG8_SPEC['panel_a']['paper_values']['heterogeneous_f1']}, "
      f"BF16 ref={FIG8_SPEC['panel_a']['paper_values']['bf16_ref']}")
if "exp11" in exps:
    exp11_quant = exps["exp11"].get("schemes", {})
    int4_f1 = exp11_quant.get("int4", {}).get("f1")
    print(f"  exp11 status: Found")
    print(f"    schemes.int4.f1 = {int4_f1}")
    if int4_f1:
        fig8_results["panel_a"] = "✓ Available from exp11"
    else:
        fig8_results["panel_a"] = "⚠ exp11 missing schemes.int4"
else:
    print(f"  exp11 status: NOT IN ARCHIVE → uses paper constant (0.915, 0.923)")
    fig8_results["panel_a"] = "⚠ exp11 missing → hardcoded"

# Panel B
print("\nPanel (b) AdvFraud-3k robustness:")
print(f"  Paper values: full_pool F1={FIG8_SPEC['panel_b']['paper_values']['full_pool_f1']}, "
      f"curated-517 F1={FIG8_SPEC['panel_b']['paper_values']['curated_517_f1']}, "
      f"BF16 matched={FIG8_SPEC['panel_b']['paper_values']['bf16_matched']}")
if "exp5" in exps:
    exp5_adf = exps["exp5"].get("advfraud", {})
    full_pool_f1 = exp5_adf.get("full_pool", {}).get("f1")
    curated_f1 = exp5_adf.get("curated_subset", {}).get("f1")
    print(f"  exp5 status: Found")
    print(f"    advfraud.full_pool.f1 = {full_pool_f1}")
    print(f"    advfraud.curated_subset.f1 = {curated_f1}")
    if full_pool_f1 is not None and curated_f1 is not None:
        fig8_results["panel_b"] = "✓ Both fields available"
    elif full_pool_f1 is not None:
        fig8_results["panel_b"] = "⚠ full_pool available, curated_subset MISSING"
    else:
        fig8_results["panel_b"] = "✗ Both fields missing"
else:
    print(f"  exp5 status: NOT IN ARCHIVE → uses paper constant (0.841, 0.875)")
    fig8_results["panel_b"] = "✗ exp5 missing → hardcoded"

# Panel C
print("\nPanel (c) ε-LDP privacy-utility trade-off:")
print(f"  Paper values: no-LDP F1={FIG8_SPEC['panel_c']['paper_values']['no_ldp_f1']}, "
      f"eps-1.5 F1={FIG8_SPEC['panel_c']['paper_values']['eps_1p5_f1']}, "
      f"latency {FIG8_SPEC['panel_c']['paper_values']['lat_no_ldp_ms']}→"
      f"{FIG8_SPEC['panel_c']['paper_values']['lat_eps_ms']} ms")
exp5_ldp_ok = "exp5" in exps and exps["exp5"].get("ldp_tradeoff", {}).get("no_ldp", {}).get("f1")
exp5_eps_ok = "exp5" in exps and exps["exp5"].get("ldp_tradeoff", {}).get("eps_1.5", {}).get("f1")
exp8_lat_ok = "exp8" in exps and exps["exp8"].get("latencies", {}).get("bf16")
if "exp5" in exps:
    exp5_ldp = exps["exp5"].get("ldp_tradeoff", {})
    print(f"  exp5.ldp_tradeoff status: Found")
    print(f"    no_ldp.f1 = {exp5_ldp.get('no_ldp', {}).get('f1')}")
    print(f"    eps_1.5.f1 = {exp5_ldp.get('eps_1.5', {}).get('f1')}")
else:
    print(f"  exp5.ldp_tradeoff status: NOT IN ARCHIVE")
if "exp8" in exps:
    exp8_lat = exps["exp8"].get("latencies", {})
    print(f"  exp8.latencies status: Found")
    print(f"    bf16 = {exp8_lat.get('bf16')} ms")
else:
    print(f"  exp8.latencies status: NOT IN ARCHIVE")

if exp5_ldp_ok and exp5_eps_ok and exp8_lat_ok:
    fig8_results["panel_c"] = "✓ All fields available (but values from smoke mode)"
elif exp5_ldp_ok and exp5_eps_ok:
    fig8_results["panel_c"] = "⚠ LDP data OK, latencies missing (exp8)"
elif exp8_lat_ok:
    fig8_results["panel_c"] = "⚠ Latencies OK, LDP data missing (exp5)"
else:
    fig8_results["panel_c"] = "✗ Critical fields missing"

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: TABLE 9 REQUIREMENTS & STATUS
# ─────────────────────────────────────────────────────────────────────────────

print("\n[2] TABLE 9: FraudFusion Baseline Comparison")
print("-" * 130)

TABLE9_SPEC = {
    "title": "FraudFusion baseline comparison + storage decomposition",
    "paper_source": "exp12_fraudfusion_baseline.py run_paper()",
    "requires": [
        "QAD_MultiGuard_INT4 F1 (ours)",
        "FraudFusion_pruned_INT4 F1 (null, no released weights)",
        "Storage footprints: 7B BF16, 0.5B BF16, 0.5B Q4_K_M",
        "Quantization advantage ratio: BF16 / Q4_K_M",
        "Parameter scale ratio: 7B / 0.5B",
        "Total advantage: quant_x * param_scale_x",
    ],
    "requires_h100": True,
}

print("\nTable 9 (from exp12 FraudFusion Baseline):")
print(f"  Purpose: Compare QAD+OVF (INT4) vs FraudFusion baseline")
print(f"  Computation: h100_real_qwen")

if "exp12" not in exps:
    print(f"  Status: ✗ CRITICAL - exp12 NOT IN ARCHIVE")
    print(f"  Cannot auto-generate Table 9 without exp12 results")
    fig8_results["table9"] = "✗ exp12 completely missing"
else:
    exp12 = exps["exp12"]
    print(f"  Status: ✓ Found in archive")
    print(f"  computation: {exp12.get('computation')}")
    comp_real = exp12.get("competitor_comparison_real", {})
    qad_f1 = comp_real.get("QAD_MultiGuard_INT4", {}).get("f1")
    storage = exp12.get("storage_decomposition_point8", {})
    print(f"  QAD_MultiGuard_INT4.f1: {qad_f1}")
    print(f"  storage footprints: {storage.get('footprints_mb', {})}")
    print(f"  total_advantage_x: {storage.get('total_advantage_x')}")
    if qad_f1 and storage.get('total_advantage_x'):
        fig8_results["table9"] = "✓ Key fields present"
    else:
        fig8_results["table9"] = "⚠ Some fields missing"

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: SMOKE VS PAPER MODE IMPACT
# ─────────────────────────────────────────────────────────────────────────────

print("\n[3] SMOKE vs PAPER MODE Impact on Figure 8 & Table 9")
print("-" * 130)

if "exp5" in exps:
    exp5_comp = exps["exp5"].get("computation")
    print(f"\nexp5 computation mode: {exp5_comp}")
    if exp5_comp == "smoke_sklearn":
        print("  → Running sklearn classifier on synthetic features")
        print("  → F1 values overly high (≈1.0) due to synthetic data, not representative")
        print("  → Figure 8(b) and 8(c) will display paper constants, not exp5 synthetic values")
    elif exp5_comp == "h100_real_qwen":
        print("  → Running real Qwen LLM on H100")
        print("  → Values representative of actual system")

if "exp8" in exps:
    exp8_comp = exps["exp8"].get("computation")
    print(f"\nexp8 computation mode: {exp8_comp}")
    if exp8_comp == "smoke_cpu":
        print("  → Running on CPU with synthetic data")
        print("  → Latencies NOT representative of H100 performance (3ms ≠ 268ms)")
        print("  → Figure 8(c) latency will display paper constants (268.0→271.0 ms)")
    elif exp8_comp == "h100_real_qwen":
        print("  → Running on H100")
        print("  → Latencies representative of actual hardware")

print("\nUser Query Interpretation:")
print("  '除了需要H100跑的结果外' (excluding H100-only results)")
print("  → Focusing on fields that CAN be computed without H100")
print("  → exp5 LDP tradeoff: mostly smoke, but can run with --paper on H100")
print("  → exp8 latencies: REQUIRES H100 to measure accurately")
print("  → exp12: REQUIRES H100 to run real Qwen + measure storage")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: SUMMARY & ACTION ITEMS
# ─────────────────────────────────────────────────────────────────────────────

print("\n[4] ALIGNMENT SUMMARY")
print("-" * 130)

print("\nFigure 8 Status:")
for panel, status in fig8_results.items():
    if panel != "table9":
        print(f"  Panel ({panel.replace('panel_', '')}): {status}")

print("\nTable 9 Status:")
print(f"  {fig8_results.get('table9', 'Unknown')}")

print("\n[5] COMPLETENESS MATRIX")
print("-" * 130)

matrix = [
    ["Field", "Required", "In Archive", "Value", "Alignment Status"],
    ["-" * 20, "-" * 15, "-" * 15, "-" * 20, "-" * 30],
    ["Figure 8(a) quant.int4", "exp11", "No", "N/A", "✗ Missing exp11"],
    ["Figure 8(b) advfraud.full", "exp5", "Yes", f"{exps['exp5'].get('advfraud',{}).get('full_pool',{}).get('f1')}", "⚠ 1.0 vs paper 0.841 (smoke)"],
    ["Figure 8(b) advfraud.curated", "exp5", "No", "N/A", "✗ Never measured"],
    ["Figure 8(c) ldp.no_ldp.f1", "exp5", "Yes", f"{exps['exp5'].get('ldp_tradeoff',{}).get('no_ldp',{}).get('f1')}", "⚠ 0.9962 vs paper 0.923 (smoke)"],
    ["Figure 8(c) ldp.eps1.5.f1", "exp5", "Yes", f"{exps['exp5'].get('ldp_tradeoff',{}).get('eps_1.5',{}).get('f1')}", "⚠ 0.8412 vs paper 0.902 (smoke)"],
    ["Figure 8(c) latency.bf16", "exp8", "Yes", f"{exps.get('exp8',{}).get('latencies',{}).get('bf16')}", "⚠ 3.06ms vs paper 268ms (smoke CPU)"],
    ["Table 9 qad.f1", "exp12", "No", "N/A", "✗ Missing exp12"],
    ["Table 9 storage.total_x", "exp12", "No", "N/A", "✗ Missing exp12"],
]

for row in matrix:
    print(f"  {row[0]:<22} {row[1]:<17} {row[2]:<17} {row[3]:<22} {row[4]:<30}")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: BLOCKERS & RECOMMENDATIONS
# ─────────────────────────────────────────────────────────────────────────────

print("\n[6] BLOCKERS & RECOMMENDATIONS")
print("-" * 130)

blockers = []
if "exp11" not in exps:
    blockers.append(("Figure 8(a)", "exp11 quantization", "MISSING", "Run exp11 with --paper on H100"))
if "exp5" not in exps:
    blockers.append(("Figure 8(b/c)", "exp5 AdvFraud + LDP", "MISSING", "Run exp5 with --paper on H100"))
else:
    exp5 = exps["exp5"]
    if exp5.get("computation") == "smoke_sklearn":
        blockers.append(("Figure 8(b/c)", "exp5 in smoke mode", "VALUES NOT REPRESENTATIVE", 
                        "Re-run exp5 with --paper on H100 for real Qwen results"))
if "exp8" not in exps:
    blockers.append(("Figure 8(c)", "exp8 latencies", "MISSING", "Run exp8 with --paper on H100"))
else:
    exp8 = exps["exp8"]
    if exp8.get("computation") in ["smoke_cpu", "smoke_sklearn"]:
        blockers.append(("Figure 8(c)", "exp8 in smoke mode", "LATENCIES NOT REPRESENTATIVE",
                        "Re-run exp8 with --paper on H100"))
if "exp12" not in exps:
    blockers.append(("Table 9", "exp12 FraudFusion", "COMPLETELY MISSING", "Run exp12 with --paper on H100"))

print(f"\nFound {len(blockers)} blocking issues:\n")
for i, (fig_tbl, experiment, status, action) in enumerate(blockers, 1):
    print(f"  {i}. [{fig_tbl:15}] {experiment:25} → {status:35}")
    print(f"     Action: {action}\n")

print("\n" + "=" * 130)
print("CONCLUSION")
print("=" * 130)
print("""
Figure 8 (Revision Ablations):
  ✗ Panel (a): exp11 missing
  ⚠ Panel (b): exp5.advfraud.full_pool.f1=1.0 (smoke), curated_subset never measured
  ⚠ Panel (c): exp5.ldp_tradeoff data exists but from smoke_sklearn (not representative)
               exp8.latencies exist but from smoke_cpu (3ms ≠ 268ms H100 value)
  
  → To align with paper Figure 8: must run exp5 + exp8 + exp11 on H100 with --paper mode

Table 9 (FraudFusion Baseline):
  ✗ exp12 completely missing from archive
  
  → To generate Table 9: must run exp12 on H100 with --paper mode

Impact of User Query "除了需要H100跑的结果外":
  - Figure 8 requires H100 for latency (exp8), but privacy F1 (exp5) can theoretically run on CPU
  - Table 9 requires H100 for storage measurements and real Qwen inference (exp12)
  - Currently NO figure/table can use live experiment results — all use hardcoded paper values
  - Archive contains smoke-mode runs which override paper constants but are NOT representative

Next Steps (Priority Order):
  1. Run exp12 on H100 (Table 9 completely blocked)
  2. Re-run exp5 on H100 with --paper (Figure 8(b/c) need real data)
  3. Re-run exp8 on H100 with --paper (Figure 8(c) latency needs H100)
  4. Run exp11 on H100 (Figure 8(a) needs quantization results)
""")

print("=" * 130 + "\n")
