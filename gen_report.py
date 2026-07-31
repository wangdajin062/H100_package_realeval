#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_report.py — 从 all_experiments.json 生成本地实验结果 markdown 文档（按日期）"""
import json
import os

RESULT = "outputs/results/all_experiments.json"
OUT_DIR = "reports"
EXPT_DATE = "2026-07-31"   # 实验完成日期
SYNC_DATE = "2026-08-01"   # 同步到本地日期

NAMES = {
    "exp1": "QAD Production Distillation（QAD 生产蒸馏）",
    "exp2": "QAD Loss Ablation（损失消融）",
    "exp3": "OV-Freeze Control（层冻结控制）",
    "exp4": "Baseline Comparison（基线对比）",
    "exp5": "Cross-Dataset（跨数据集）",
    "exp6": "Speculative Decoding（投机解码）",
    "exp7": "Privacy Verification（隐私验证）",
    "exp8": "Latency Benchmark（时延基准）",
    "exp9": "CoT Ablation（思维链消融）",
    "exp10": "Teacher Scale（教师规模）",
    "exp11": "Quantization Scheme（量化方案）",
    "exp12": "FraudFusion Baseline（FraudFusion 基线）",
    "exp13": "Fusion Strategy（融合策略）",
    "exp14": "Multi-model same-data comparison（多模型同数据对比）",
}

with open(RESULT, encoding="utf-8") as f:
    data = json.load(f)

os.makedirs(OUT_DIR, exist_ok=True)
out_path = os.path.join(OUT_DIR, f"{EXPT_DATE}_experiment_results.md")

L = []
L.append(f"# 实验结果报告（{EXPT_DATE}）\n")
L.append(f"- **实验日期**：{EXPT_DATE}")
L.append(f"- **同步日期**：{SYNC_DATE}")
L.append("- **运行环境**：RunPod H100 80GB HBM3（pod `mhypfkvge474n8`）")
L.append("- **运行模式**：`python -m experiments.runner --exp all --paper --config config/runpod_h100.yaml`")
L.append("- **数据**：taf28k / chifraud（16000 样本，12800 训练 / 3200 测试）")
L.append(f"- **结果源文件**：`outputs/results/all_experiments.json`（共 {len(data)} 个实验）\n")

# ── 汇总表 ──────────────────────────────────────────────
L.append("## 汇总\n")
L.append("| 实验 | 名称 | 核心数据 | 状态 |")
L.append("|---|---|---|---|")
for k in sorted(data.keys(), key=lambda x: int(x[3:])):
    v = data[k]
    core = {fk: fv for fk, fv in v.items() if fk != "trajectory"}
    core_s = json.dumps(core, ensure_ascii=False)
    if len(core_s) > 150:
        core_s = core_s[:150] + "…"
    core_s = core_s.replace("|", "\\|")
    status = "❌ " + str(v["error"])[:40] if v.get("error") else "✅"
    L.append(f"| {k} | {NAMES.get(k, k)} | `{core_s}` | {status} |")

# ── 详情 ────────────────────────────────────────────────
for k in sorted(data.keys(), key=lambda x: int(x[3:])):
    v = data[k]
    L.append(f"\n## {k} — {NAMES.get(k, k)}\n")
    for fk, fv in v.items():
        if fk == "trajectory":
            if isinstance(fv, list) and fv:
                sample = json.dumps(fv[:3], ensure_ascii=False)
                L.append(f"- **trajectory**：list[{len(fv)}] 点，样本 `{sample[:200]}`")
            continue
        if isinstance(fv, dict):
            L.append(f"- **{fk}**：`{json.dumps(fv, ensure_ascii=False)}`")
        elif isinstance(fv, list):
            L.append(f"- **{fk}**：list[{len(fv)}]")
        else:
            L.append(f"- **{fk}**：`{fv}`")

with open(out_path, "w", encoding="utf-8") as f:
    f.write("\n".join(L) + "\n")
print(f"已生成 {out_path}（{os.path.getsize(out_path)} 字节，{len(data)} 个实验）")
