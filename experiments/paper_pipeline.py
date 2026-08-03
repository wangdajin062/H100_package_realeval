"""paper_pipeline.py — 一键式 H100 论文验证流水线

协调完整流程并向 results/ 写入论文交付物：

    CUDA 检测 -> GPU 探测 -> 环境报告 -> 模型加载 -> 基准测试 -> 指标 -> 保存

重跑行为：
    每次运行前，若 outputs/results/ 中已有旧实验结果，
    自动将其以带时间戳的 Markdown 归档到 outputs/archive/，
    然后清空结果目录（保留 paper_tables/、models/、audit/、logs/）。

输出（results/）：
    exp{N}_{timestamp}.json   各实验结果文件
    all_experiments.json      全量归并结果（paper_data.py 主要候补来源）
    metrics.json              聚合指标（accuracy/F1/FPR，按实验分组）
    latency.csv               各批次大小延迟（p50/p90/p99）
    throughput.csv            tokens/samples per second
    memory.csv                峰值/已用显存
    paper_table.md            可直接粘贴的论文表格（主表/消融表/效率表/鲁棒性表）

运行：  bash run_h100.sh   （封装了 `python -m experiments.paper_pipeline --paper`）
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger("paper_pipeline")

RESULTS = Path(__file__).resolve().parent.parent / "outputs" / "results"

# Paper experiment groups -> the underlying experiment short names that produce their metrics.
PAPER_GROUPS = {
    "00_train":        ["exp1"],           # fine-tune first → saves model for exp4/exp11
    "01_baseline":     ["exp4"],           # BF16 teacher + classical baselines (uses exp1 model)
    "02_quantization": ["exp11"],          # INT4 / NVFP4 scheme comparison (uses exp1 model)
    "03_QAD":          ["exp2"],           # KL loss ablation
    "04_OV-Freeze":    ["exp3"],           # OV-Freeze ablation + matched-regulariser control
    "05_latency":      ["exp8", "exp6"],   # H100 latency/throughput + speculative-decoding speedup
    "06_robustness":   ["exp5", "exp7"],   # OOD/cross-dataset + adversarial/privacy
    "07_fusion":       ["exp13", "exp12"], # multimodal fusion ablation (→ 0.923) + FraudFusion baseline
    "08_ablations":    ["exp9", "exp10"],  # CoT ablation + teacher-scale selection
    "09_edge":         ["exp14"],          # BF16 vs Q4_K_M GGUF edge deployment comparison
}


def _cuda_check():
    """CUDA -> GPU detect -> env report. Returns (has_cuda, env_dict)."""
    logger.info("[1/7] CUDA check ...")
    try:
        import torch
        has_cuda = torch.cuda.is_available()
    except Exception as e:
        logger.error("torch import failed: %s", e)
        return False, {}
    logger.info("      CUDA available: %s", has_cuda)

    logger.info("[2/7] GPU detect ...")
    n_gpu = torch.cuda.device_count() if has_cuda else 0
    for i in range(n_gpu):
        p = torch.cuda.get_device_properties(i)
        logger.info("      GPU %d: %s (%.1f GB)", i, p.name, p.total_memory / 1e9)
    if has_cuda and not any("H100" in torch.cuda.get_device_properties(i).name for i in range(n_gpu)):
        logger.warning("      No H100 detected — pipeline runs but numbers are not H100-grade.")

    logger.info("[3/7] Environment report ...")
    try:
        from realeval import envreport
        env = envreport.collect()
    except Exception as e:
        logger.warning("      envreport failed: %s", e); env = {}
    return has_cuda, env


def _apply_h100_optims(config: dict, has_cuda: bool) -> dict:
    """Enable H100-oriented settings: BF16, FlashAttention-2, (optional) torch.compile, NCCL/DDP."""
    hw = config.setdefault("hardware", {})
    if has_cuda:
        hw.setdefault("use_flash_attn", True)     # FlashAttention-2
        hw.setdefault("bf16", True)               # BF16 compute
        hw.setdefault("use_torch_compile", hw.get("use_torch_compile", False))
        import torch
        if torch.cuda.device_count() > 1:
            hw["ddp"] = True                      # NCCL multi-GPU
            logger.info("      Multi-GPU (%d) -> DDP/NCCL enabled", torch.cuda.device_count())
        # NVFP4/QAD path is driven by config['models'] + quantize=int4/nf4 (already wired).
        logger.info("      H100 optims: BF16=%s FlashAttn=%s compile=%s ddp=%s",
                    hw.get("bf16"), hw.get("use_flash_attn"), hw.get("use_torch_compile"), hw.get("ddp"))
    return config


def _run_experiments(config: dict, smoke: bool) -> dict:
    """[4/7] 加载模型 + [5/7] 基准测试：运行各实验分组，收集真实指标。
    运行完成后将全量结果写入 all_experiments.json。
    """
    logger.info("[4/7] 加载模型 + [5/7] 基准测试（运行实验分组）…")
    from experiments.runner import _import_exp, _SHORT_TO_FULL
    from realeval.io import save_results, save_all_results
    all_results = {}
    for group, shorts in PAPER_GROUPS.items():
        for short in shorts:
            try:
                mod = _import_exp(_SHORT_TO_FULL[short])
                res = mod.run(config)
                save_results(short, res)
                all_results[short] = res
                logger.info("      %s/%s -> %s", group, short, res.get("computation", "?"))
            except Exception as e:
                logger.error("      %s/%s 失败：%s", group, short, e, exc_info=True)
                all_results[short] = {"error": str(e)}

    # 写入全量归并文件，供 paper_data.py 候补加载
    if all_results:
        save_all_results(all_results)

    return all_results


def _device_benchmark(config: dict, has_cuda: bool):
    """Real device latency/throughput/memory benchmark -> outputs/metrics/benchmark.csv."""
    if not has_cuda:
        logger.info("      No CUDA: skipping device benchmark CSVs (run on H100 for real numbers).")
        return None
    try:
        import torch
        from realeval import models, benchmark
        model, tok = models.load_causal_lm(config["models"]["teacher"], quantize="int4", bf16=True)
        sample_ids = tok("Detect fraud in this message.", return_tensors="pt").input_ids.squeeze(0)
        res = benchmark.benchmark(model, sample_ids, warmup=10, repeat=100,
                                  batch_sizes=(1, 8, 32))
        return benchmark.summary(res)
    except Exception as e:
        logger.error("      device benchmark failed: %s", e)
        return None


def _extract(short, all_results):
    """Pull headline metrics from each experiment's own result shape."""
    r = all_results.get(short, {})
    if short == "exp1":
        return {"F1": r.get("f1"), "kl_final": r.get("kl_final"),
                "drift_pct_final": r.get("drift_pct_final"),
                "kl_plateau": r.get("kl_plateau"), "kl_converged": r.get("kl_converged"),
                "total_steps": r.get("total_steps"), "ovf_step": r.get("ovf_activation_step"),
                "snr_min": r.get("snr_min"), "snr_max": r.get("snr_max")}
    if short == "exp2":
        v = r.get("variants", {})
        return {f"kl_final[{k}]": x.get("kl_final") for k, x in v.items()}
    if short == "exp3":
        c = r.get("conditions", {})
        return {f"drift[{k}]": x.get("variance_drift_pct") for k, x in c.items()}
    if short == "exp4":
        c = r.get("classifiers", {})
        return {f"F1[{k}]": x.get("f1") for k, x in c.items()}
    if short == "exp5":
        taf = r.get("taf28k", {}).get("f1")
        if taf is None:
            taf = r.get("balanced4k", {}).get("f1")
        chi = r.get("chifraud", {}).get("f1")
        adv = r.get("advfraud", {}).get("full_pool", {}).get("f1") if isinstance(r.get("advfraud"), dict) else None
        adv_curated = r.get("advfraud", {}).get("curated", {}).get("f1") if isinstance(r.get("advfraud"), dict) else None
        cross_tc = r.get("cross_taf_on_chifraud", {}).get("f1")
        cross_ct = r.get("cross_chifraud_on_taf", {}).get("f1")
        bf16_matched = r.get("bf16_matched_advfraud")
        out = {}
        if taf is not None: out["taf28k"] = taf
        if chi is not None: out["chifraud"] = chi
        if adv is not None: out["advfraud"] = adv
        if adv_curated is not None: out["advfraud_curated"] = adv_curated
        if cross_tc is not None: out["cross_taf->chi"] = cross_tc
        if cross_ct is not None: out["cross_chi->taf"] = cross_ct
        if bf16_matched is not None: out["bf16_matched"] = bf16_matched
        return out or {"cross_taf->chi": None, "cross_chi->taf": None}
    if short == "exp6":
        d = r.get("diagnostic_B", {})
        hm = d.get("h100_measured", {})
        ref = r.get("paper_reference", {})
        out = {}
        if hm.get("generic") is not None: out["alpha_generic"] = hm["generic"]
        if hm.get("domain") is not None: out["alpha_domain"] = hm["domain"]
        if ref.get("alpha_generic") is not None: out["ref_alpha_generic"] = ref["alpha_generic"]
        if ref.get("alpha_tuned") is not None: out["ref_alpha_tuned"] = ref["alpha_tuned"]
        return out or {"alpha_generic": None}
    if short == "exp7":
        return {"speaker_id_acc": r.get("speaker_id_accuracy"), "asv_eer_pct": r.get("asv_eer_pct")}
    if short == "exp8":
        out = {f"lat_ms[{k}]": v for k, v in r.get("latencies", {}).items()}
        bb = r.get("batch_benchmark", {})
        if bb:
            out["batch_benchmark"] = bb
        return out
    if short == "exp9":
        wc = r.get("with_cot", {}); wo = r.get("without_cot", {})
        return {"cot_f1": wc.get("f1"), "direct_f1": wo.get("f1"),
                "cot_fpr": wc.get("fpr"), "direct_fpr": wo.get("fpr")}
    if short == "exp10":
        scales = r.get("scales", {})
        out = {}
        for k, x in scales.items():
            if x.get("f1_fixed") is not None:
                out[f"F1_fixed[{k}]"] = x["f1_fixed"]
            if x.get("f1_conv") is not None:
                out[f"F1_conv[{k}]"] = x["f1_conv"]
        return out
    if short == "exp11":
        schemes = r.get("schemes", {})
        out = {f"F1[{k}]": x.get("f1") for k, x in schemes.items() if x.get("f1") is not None}
        return out
    if short == "exp12":
        comp = r.get("competitor_comparison_real", {})
        storage = r.get("storage_decomposition_point8", {})
        out = {f"F1[{k}]": x.get("f1") for k, x in comp.items()}
        for k, v in storage.get("footprints_mb", {}).items():
            out[f"fp[{k}]"] = v
        if storage.get("total_advantage_x") is not None:
            out["total_advantage_x"] = storage["total_advantage_x"]
        return out
    if short == "exp13":
        return {f"F1[{k}]": x.get("f1") for k, x in r.get("strategies", {}).items()}
    if short == "exp14":
        models = r.get("models", {})
        return {f"F1[{k}]": x.get("f1") for k, x in models.items() if x.get("f1") is not None}
    if "f1" in r:
        return {"F1": r["f1"]}
    return {}


def _aggregate_and_save(all_results: dict, bench_summary, env: dict):
    """[6/7] metrics stats + [7/7] save: metrics.json, latency/throughput/memory.csv, LaTeX + md tables."""
    logger.info("[6/7] Aggregating metrics ...")
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "paper_tables").mkdir(exist_ok=True)

    metrics = {"env": env, "groups": {}}
    for group, shorts in PAPER_GROUPS.items():
        metrics["groups"][group] = {s: _extract(s, all_results) for s in shorts}
    if bench_summary:
        metrics["benchmark"] = bench_summary
    (RESULTS / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False))

    # Write efficiency CSVs from benchmark results (dict keyed by batch_size).
    raw = (bench_summary or {}).get("all_batch_sizes", {})
    if raw:
        def _csv(name, cols):
            import csv as _csv_mod
            with open(RESULTS / name, "w", newline="") as f:
                w = _csv_mod.writer(f); w.writerow([c[0] for c in cols])
                for bs, r in sorted(raw.items()):
                    w.writerow([r.get(c[1]) if c[1] != "batch_size" else bs for c in cols])
        _csv("latency.csv", [("batch_size", "batch_size"), ("p50_ms", "latency_p50_ms"),
                             ("p90_ms", "latency_p90_ms"), ("p99_ms", "latency_p99_ms")])
        _csv("throughput.csv", [("batch_size", "batch_size"), ("samples_per_sec", "throughput_sps")])
        _csv("memory.csv", [("batch_size", "batch_size"), ("peak_mem_mb", "peak_mem_mb")])

    logger.info("[7/7] Writing paper tables (md + LaTeX) ...")
    # Markdown summary
    md = ["# Paper Tables (auto-generated from real results)", ""]
    for group, shorts in PAPER_GROUPS.items():
        md.append(f"## {group}")
        for s in shorts:
            ex = _extract(s, all_results)
            comp = all_results.get(s, {}).get("computation", "-")
            md.append(f"- **{s}** ({comp}): " + ", ".join(f"{k}={v}" for k, v in ex.items()))
        md.append("")
    (RESULTS / "paper_table.md").write_text("\n".join(md) + "\n")

    # LaTeX tables: table1_main, table2_ablation, table3_efficiency
    def _latex(fname, title, header, body_rows):
        L = ["\\begin{table}[t]", "\\centering", f"\\caption{{{title}}}",
             "\\begin{tabular}{" + "l" * len(header) + "}", "\\toprule",
             " & ".join(header) + " \\\\", "\\midrule"]
        L += [" & ".join(str(c) for c in r) + " \\\\" for r in body_rows]
        L += ["\\bottomrule", "\\end{tabular}", "\\end{table}"]
        (RESULTS / "paper_tables" / fname).write_text("\n".join(L) + "\n")

    main_rows = [
        ["exp13 (fusion)", all_results.get("exp13", {}).get("computation", "-"),
         _extract("exp13", all_results).get("F1[late]", "-")],
        ["exp11 (int4)",   all_results.get("exp11", {}).get("computation", "-"),
         _extract("exp11", all_results).get("F1[int4]", "-")],
        ["exp1 (QAD-LLM)", all_results.get("exp1", {}).get("computation", "-"),
         _extract("exp1", all_results).get("F1", "-")],
    ]
    _latex("table1_main.tex", "Main Result (F1)", ["Experiment", "Computation", "F1"], main_rows)
    abl_rows = [[k, v] for k, v in _extract("exp3", all_results).items()]
    _latex("table2_ablation.tex", "OV-Freeze Ablation (variance drift \\%)",
           ["Condition", "Drift(\\%)"], abl_rows)
    eff_rows = [[bs, r.get("latency_p50_ms"), r.get("throughput_sps"),
                 r.get("peak_mem_mb")] for bs, r in sorted(raw.items())]
    _latex("table3_efficiency.tex", "Efficiency (H100 benchmark)",
           ["Batch", "p50(ms)", "samp/s", "peak mem(MB)"], eff_rows or [["-", "-", "-", "-"]])

    _print_summary(all_results, bench_summary)
    logger.info("Done. Deliverables in %s/", RESULTS)


def _print_summary(all_results, bench_summary):
    """Final RealEval banner."""
    def g(short, *path, default="n/a"):
        r = all_results.get(short, {})
        for p in path:
            r = r.get(p, {}) if isinstance(r, dict) else {}
        return r if r not in ({}, None) else default
    print("\n=== RealEval-v2 H100 Benchmark ===")
    print(f"QAD:         F1 {all_results.get('exp1', {}).get('f1', 'n/a')}")
    ov = _extract("exp3", all_results)
    print(f"OV-Freeze:   drift {ov.get('drift[ov_freeze_full]', 'n/a')}% (vs no_reg {ov.get('drift[no_reg]', 'n/a')}%)")
    sd = _extract("exp6", all_results)
    print(f"Speculative: alpha generic={sd.get('alpha_generic', 'n/a')} "
          f"domain={sd.get('alpha_domain', 'NOT MEASURED')}")
    print(f"Privacy:     speaker-ID acc {all_results.get('exp7', {}).get('speaker_id_accuracy', 'n/a')}, "
          f"ASV-EER {all_results.get('exp7', {}).get('asv_eer_pct', 'n/a')}%")
    raw = (bench_summary or {}).get("all_batch_sizes", {})
    if raw:
        first_bs = min(raw)
        r0 = raw[first_bs]
        print(f"Latency:     P50 {r0.get('latency_p50_ms', 'n/a')} ms  P99 {r0.get('latency_p99_ms', 'n/a')} ms (bs={first_bs})")
    else:
        print("Latency:     (run --paper on H100 for real latency)")
    print("DONE\n")


def main():
    ap = argparse.ArgumentParser(description="一键式 H100 论文验证流水线")
    ap.add_argument("--paper",      action="store_true", help="论文级运行（真实 Qwen + H100）")
    ap.add_argument("--smoke",      action="store_true", help="沙盒验证（无 GPU/权重）")
    ap.add_argument("--no-archive", action="store_true", help="跳过运行前的自动归档步骤")
    ap.add_argument("--config",     type=str, default=None, help="配置 YAML 路径")
    args = ap.parse_args()
    smoke = args.smoke or not args.paper

    # ── 运行前自动归档旧结果 ────────────────────────────────────────────────
    if not args.no_archive:
        try:
            import sys as _sys
            _sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
            from archive_and_clear import archive_if_needed
            archived = archive_if_needed()
            if archived:
                logger.info("旧实验结果已归档至：%s", archived)
        except Exception as _ae:
            logger.warning("归档步骤失败（继续运行）：%s", _ae)

    from realeval.io import load_config
    config = load_config(args.config)
    config["_smoke"] = smoke
    if args.paper:
        config["_paper"] = True

    has_cuda, env = _cuda_check()
    config = _apply_h100_optims(config, has_cuda)
    all_results = _run_experiments(config, smoke)
    bench_summary = _device_benchmark(config, has_cuda) if args.paper else None
    _aggregate_and_save(all_results, bench_summary, env)
    return 0


if __name__ == "__main__":
    sys.exit(main())
