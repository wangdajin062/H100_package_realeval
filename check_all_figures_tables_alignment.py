#!/usr/bin/env python3
"""
COMPREHENSIVE ALIGNMENT CHECK: All 8 Figures & 9 Tables
========================================================

Check alignment between ALL paper figures/tables and experiment results in archive.
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

print("\n" + "=" * 140)
print("COMPREHENSIVE PAPER ALIGNMENT CHECK: All 8 Figures & 9 Tables")
print("=" * 140)

# ─────────────────────────────────────────────────────────────────────────────
# FIGURE REQUIREMENTS FROM generate_all.py
# ─────────────────────────────────────────────────────────────────────────────

FIGURES = [
    {
        "num": 1,
        "title": "Architecture Diagram",
        "script": "fig1_architecture.py",
        "requires": [],
        "type": "diagram (no experiment data needed)",
    },
    {
        "num": 2,
        "title": "Acoustic Embedding",
        "script": "fig2_acoustic_embedding.py",
        "requires": [],
        "type": "diagram (no experiment data needed)",
    },
    {
        "num": 3,
        "title": "Main Results (QAD+OVF vs baselines)",
        "script": "fig3_main_results.py",
        "requires": ["exp11"],
        "type": "bar chart",
    },
    {
        "num": 4,
        "title": "Loss Convergence Trajectory",
        "script": "fig4_loss_convergence.py",
        "requires": ["exp1"],
        "type": "line plot",
    },
    {
        "num": 5,
        "title": "Loss Ablation & Teacher Scale",
        "script": "fig5_loss_teacher_ablation.py",
        "requires": ["exp2", "exp10"],
        "type": "2-panel ablation",
    },
    {
        "num": 6,
        "title": "OV-Freeze Ablation (layer · rho)",
        "script": "fig6_ovf_ablation.py",
        "requires": ["exp3"],
        "type": "heatmap",
    },
    {
        "num": 7,
        "title": "Speculative Decoding Alpha Measurement",
        "script": "fig7_speculative_decoding.py",
        "requires": ["exp6"],
        "type": "alpha plot",
    },
    {
        "num": 8,
        "title": "Revision Ablations (3-panel)",
        "script": "fig8_revision_ablations.py",
        "requires": ["exp5", "exp7"],
        "type": "3-panel: quant/advfraud/ldp",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# TABLE REQUIREMENTS FROM README
# ─────────────────────────────────────────────────────────────────────────────

TABLES = [
    {
        "num": 4,
        "title": "Main Results (QAD+OVF, QAT quantization)",
        "requires": ["exp1", "exp4", "exp11"],
        "fields": ["exp1.f1", "exp4.f1", "exp11.schemes.int4.f1"],
    },
    {
        "num": 5,
        "title": "Cross-Dataset Evaluation + LDP",
        "requires": ["exp5"],
        "fields": ["exp5.taf28k.f1", "exp5.cross_taf_on_chifraud.f1", "exp5.ldp_tradeoff"],
    },
    {
        "num": 6,
        "title": "Privacy Verification (ASV-EER, GLO attack)",
        "requires": ["exp7"],
        "fields": ["exp7.asv_eer_pct", "exp7.glo_reconstruction_corr"],
    },
    {
        "num": 7,
        "title": "Latency Benchmark (BF16/FP16/INT4/INT8)",
        "requires": ["exp8"],
        "fields": ["exp8.latencies.bf16", "exp8.latencies.fp16", "exp8.latencies.int4", "exp8.latencies.int8"],
    },
    {
        "num": 8,
        "title": "Speculative Decoding (throughput, latency)",
        "requires": ["exp6"],
        "fields": ["exp6.alpha", "exp6.speedup", "exp6.latency"],
    },
    {
        "num": 9,
        "title": "FraudFusion Baseline + Storage Decomposition",
        "requires": ["exp12"],
        "fields": ["exp12.competitor_comparison_real.QAD_MultiGuard_INT4.f1", 
                   "exp12.storage_decomposition_point8.total_advantage_x"],
    },
    {
        "num": 10,
        "title": "Fusion Strategy (TAF-28k multimodal)",
        "requires": ["exp13"],
        "fields": ["exp13.multimodal_f1", "exp13.fusion_type"],
    },
    {
        "num": 11,
        "title": "BF16 vs Q4_K_M GGUF Comparison",
        "requires": ["exp14"],
        "fields": ["exp14.bf16_f1", "exp14.gguf_q4km_f1", "exp14.model_size_ratio"],
    },
    {
        "num": "A1",
        "title": "Appendix: CoT Ablation",
        "requires": ["exp9"],
        "fields": ["exp9.cot_on.f1", "exp9.cot_off.f1"],
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# FIGURE ALIGNMENT CHECK
# ─────────────────────────────────────────────────────────────────────────────

print("\n[FIGURES] 8 Paper Figures Alignment\n")
print(f"{'#':<3} {'Title':<45} {'Status':<20} {'Experiments':<30}")
print("-" * 140)

fig_status = {}
for fig in FIGURES:
    num = fig["num"]
    title = fig["title"]
    requires = fig["requires"]
    
    if not requires:
        status = "✓ DIAGRAM"
        available = "N/A"
    else:
        missing = [e for e in requires if e not in exps]
        if missing:
            status = f"✗ Missing: {missing}"
            available = ", ".join(requires)
        else:
            # Check if values are non-None
            all_ok = True
            for exp_name in requires:
                if exp_name in exps:
                    exp_data = exps[exp_name]
                    if exp_data.get("computation") == "smoke_sklearn" or exp_data.get("computation") == "smoke_cpu":
                        status = "⚠️ SMOKE MODE"
                        all_ok = False
                        break
            if all_ok and all(e in exps for e in requires):
                status = "✓ DATA OK"
            else:
                if status != "⚠️ SMOKE MODE":
                    status = "⚠️ PARTIAL"
            available = ", ".join(requires)
    
    fig_status[f"fig{num}"] = status
    print(f"{num:<3} {title:<45} {status:<20} {available:<30}")

# ─────────────────────────────────────────────────────────────────────────────
# TABLE ALIGNMENT CHECK
# ─────────────────────────────────────────────────────────────────────────────

print("\n[TABLES] 9 Paper Tables Alignment\n")
print(f"{'Tbl':<5} {'Title':<45} {'Status':<20} {'Experiments':<30}")
print("-" * 140)

tbl_status = {}
for tbl in TABLES:
    num = tbl["num"]
    title = tbl["title"]
    requires = tbl["requires"]
    fields = tbl["fields"]
    
    missing_exp = [e for e in requires if e not in exps]
    if missing_exp:
        status = f"✗ Missing: {missing_exp}"
    else:
        # Check field availability
        missing_fields = []
        for field in fields:
            keys = field.split(".")
            val = exps.get(keys[0], {})
            for k in keys[1:]:
                if isinstance(val, dict):
                    val = val.get(k, {})
                else:
                    val = None
                    break
            if val is None or val == {}:
                missing_fields.append(field)
        
        if missing_fields:
            status = f"⚠️ Missing fields: {len(missing_fields)}/{len(fields)}"
        else:
            status = "✓ ALL FIELDS OK"
    
    tbl_status[f"tbl{num}"] = status
    available = ", ".join(requires)
    print(f"{num:<5} {title:<45} {status:<20} {available:<30}")

# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 140)
print("ALIGNMENT SUMMARY")
print("=" * 140)

fig_ok = sum(1 for s in fig_status.values() if "✓" in str(s))
fig_warn = sum(1 for s in fig_status.values() if "⚠️" in str(s))
fig_err = sum(1 for s in fig_status.values() if "✗" in str(s))

tbl_ok = sum(1 for s in tbl_status.values() if "✓" in str(s))
tbl_warn = sum(1 for s in tbl_status.values() if "⚠️" in str(s))
tbl_err = sum(1 for s in tbl_status.values() if "✗" in str(s))

print(f"\nFigures (8 total):")
print(f"  ✓ OK: {fig_ok} | ⚠️ Partial: {fig_warn} | ✗ Blocked: {fig_err}")

print(f"\nTables (9 total):")
print(f"  ✓ OK: {tbl_ok} | ⚠️ Partial: {tbl_warn} | ✗ Blocked: {tbl_err}")

print(f"\nOverall Alignment:")
total_ok = fig_ok + tbl_ok
total_items = len(FIGURES) + len(TABLES)
alignment_pct = round(total_ok / total_items * 100, 1)
print(f"  {total_ok}/{total_items} items fully aligned ({alignment_pct}%)")

# ─────────────────────────────────────────────────────────────────────────────
# CRITICAL BLOCKERS
# ─────────────────────────────────────────────────────────────────────────────

print("\n[CRITICAL BLOCKERS]\n")

blockers = []

# Missing experiments
missing_exps = set()
for fig in FIGURES:
    for e in fig.get("requires", []):
        if e not in exps:
            missing_exps.add(e)
for tbl in TABLES:
    for e in tbl["requires"]:
        if e not in exps:
            missing_exps.add(e)

if missing_exps:
    for exp in sorted(missing_exps):
        blockers.append(f"exp{exp[3:]} completely missing from archive")

# Smoke mode experiments
for exp_name, exp_data in exps.items():
    comp = exp_data.get("computation", "")
    if "smoke" in comp:
        # Check if this exp is used by any figure/table
        used_by = []
        for fig in FIGURES:
            if exp_name in fig.get("requires", []):
                used_by.append(f"Fig{fig['num']}")
        for tbl in TABLES:
            if exp_name in tbl["requires"]:
                used_by.append(f"Tbl{tbl['num']}")
        
        if used_by:
            blockers.append(f"{exp_name} in {comp} mode → non-representative values for {', '.join(used_by)}")

if blockers:
    for i, blocker in enumerate(blockers, 1):
        print(f"  {i}. {blocker}")
else:
    print("  No critical blockers detected (all required experiments present)")

# ─────────────────────────────────────────────────────────────────────────────
# EXPERIMENTS IN ARCHIVE vs NEEDED
# ─────────────────────────────────────────────────────────────────────────────

print("\n[EXPERIMENT COVERAGE]\n")

all_needed = set()
for fig in FIGURES:
    all_needed.update(fig.get("requires", []))
for tbl in TABLES:
    all_needed.update(tbl["requires"])

in_archive = set(exps.keys())

print(f"Needed by paper: {sorted(all_needed) if all_needed else '(no experiment required)'}")
print(f"In archive:      {sorted(in_archive)}")
print(f"Missing:         {sorted(all_needed - in_archive) if (all_needed - in_archive) else '(none)'}")
print(f"Extra:           {sorted(in_archive - all_needed) if (in_archive - all_needed) else '(none)'}")

# ─────────────────────────────────────────────────────────────────────────────
# RECOMMENDATIONS
# ─────────────────────────────────────────────────────────────────────────────

print("\n[RECOMMENDATIONS]\n")

print("To achieve FULL alignment (100%), execute in this order:")
print()

needed_in_order = [
    ("exp1", "Fig 4, Table 4"),
    ("exp2", "Fig 5(a)"),
    ("exp3", "Fig 6"),
    ("exp4", "Table 4"),
    ("exp5", "Table 5, Fig 8(c)"),
    ("exp6", "Fig 7, Table 8"),
    ("exp7", "Table 6, Fig 8"),
    ("exp8", "Table 7"),
    ("exp9", "Appendix"),
    ("exp11", "Fig 3, Table 4 QAT"),
    ("exp12", "Table 9"),
    ("exp13", "Table 10"),
    ("exp14", "Table 11"),
]

priority_order = [
    ("exp12", "CRITICAL", "Table 9 completely blocked"),
    ("exp5", "HIGH", "Fig 8(b/c) need real data (currently smoke)"),
    ("exp8", "HIGH", "Table 7 need real latency (currently smoke CPU)"),
    ("exp11", "HIGH", "Fig 3, Table 4 need quantization data"),
    ("exp13", "MEDIUM", "Table 10 needs fusion strategy results"),
    ("exp14", "MEDIUM", "Table 11 needs GGUF comparison"),
    ("exp9", "LOW", "Appendix CoT ablation (non-critical)"),
]

print("Priority-ordered (run on H100 with --paper mode):\n")
for exp, priority, reason in priority_order:
    if exp in (all_needed - in_archive):
        print(f"  [{priority:8}] {exp}  →  {reason}")
        print(f"              python -m experiments.runner --exp {exp[3:]} --paper\n")
    elif exp in all_needed and exp in exps and "smoke" in exps[exp].get("computation", ""):
        print(f"  [{priority:8}] {exp} (re-run)  →  {reason}")
        print(f"              python -m experiments.runner --exp {exp[3:]} --paper\n")

print("\n" + "=" * 140)
print("END OF COMPREHENSIVE ALIGNMENT REPORT")
print("=" * 140 + "\n")
