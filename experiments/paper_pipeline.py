"""paper_pipeline.py — 一键式 H100 论文验证流水线。

协调完整流程并向 results/ 写入论文交付物：
    CUDA 检测 -> GPU 探测 -> 环境报告 -> 模型加载 -> 基准测试 -> 指标 -> 保存

重跑行为：
    每次运行前，若 outputs/results/ 中已有旧实验结果，
    自动将其以带时间戳的 Markdown 归档到 outputs/archive/，
    然后清空结果目录（保留 paper_tables/、models/、audit/、logs/）。

运行：  bash run_h100.sh   （封装了 `python -m experiments.paper_pipeline --paper`）
"""
from __future__ import annotations

import csv
import json
import logging
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cli.parser import build_pipeline_parser
from config import load_config
from realeval.io.archive import archive_if_needed
from realeval.io.paths import RESULTS
from realeval.io.serialization import save_all_results, save_results
from metrics.extraction import extract_headline
from runner.registry import EXPERIMENTS, SHORT_TO_FULL
from utils.logging import configure_logging, get_logger

configure_logging()
logger = get_logger("paper_pipeline")

# Paper experiment groups -> underlying experiment short names.
PAPER_GROUPS = {
    "00_train":        ["exp1"],
    "01_baseline":     ["exp4"],
    "02_quantization": ["exp11"],
    "03_QAD":          ["exp2"],
    "04_OV-Freeze":    ["exp3"],
    "05_latency":      ["exp8", "exp6"],
    "06_robustness":   ["exp5", "exp7"],
    "07_fusion":       ["exp13", "exp12"],
    "08_ablations":    ["exp9", "exp10"],
    "09_edge":         ["exp14"],
}


def _cuda_check() -> tuple[bool, dict[str, Any]]:
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
        logger.warning("      envreport failed: %s", e)
        env = {}
    return has_cuda, env


def _apply_h100_optims(config: dict[str, Any], has_cuda: bool) -> dict[str, Any]:
    """启用 H100 相关设置：BF16、FlashAttention-2、DDP。"""
    hw = config.setdefault("hardware", {})
    if has_cuda:
        hw.setdefault("use_flash_attn", True)
        hw.setdefault("bf16", True)
        hw.setdefault("use_torch_compile", hw.get("use_torch_compile", False))
        import torch
        if torch.cuda.device_count() > 1:
            hw["ddp"] = True
            logger.info("      Multi-GPU (%d) -> DDP/NCCL enabled", torch.cuda.device_count())
        logger.info("      H100 optims: BF16=%s FlashAttn=%s compile=%s ddp=%s",
                    hw.get("bf16"), hw.get("use_flash_attn"),
                    hw.get("use_torch_compile"), hw.get("ddp"))
    return config


def _run_experiments(config: dict[str, Any]) -> dict[str, Any]:
    """运行各实验分组，收集结果并写入 all_experiments.json。"""
    logger.info("[4/7] 加载模型 + [5/7] 基准测试（运行实验分组）…")
    from runner.experiment_runner import import_experiment
    all_results: dict[str, Any] = {}
    for group, shorts in PAPER_GROUPS.items():
        for short in shorts:
            try:
                mod = import_experiment(SHORT_TO_FULL[short])
                res = mod.run(config)
                save_results(short, res)
                all_results[short] = res
                logger.info("      %s/%s -> %s", group, short, res.get("computation", "?"))
            except Exception as e:
                logger.error("      %s/%s 失败：%s", group, short, e, exc_info=True)
                all_results[short] = {"error": str(e)}

    if all_results:
        save_all_results(all_results)
    return all_results


def _device_benchmark(config: dict[str, Any], has_cuda: bool) -> dict[str, Any] | None:
    """真实设备延迟/吞吐/显存基准 -> outputs/metrics/benchmark.csv。"""
    if not has_cuda:
        logger.info("      No CUDA: skipping device benchmark CSVs (run on H100 for real numbers).")
        return None
    try:
        import torch
        from realeval import benchmark, models
        model, tok = models.load_causal_lm(config["models"]["teacher"], quantize="int4", bf16=True)
        sample_ids = tok("Detect fraud in this message.", return_tensors="pt").input_ids.squeeze(0)
        res = benchmark.benchmark(model, sample_ids, warmup=10, repeat=100,
                                  batch_sizes=(1, 8, 32))
        return benchmark.summary(res)
    except Exception as e:
        logger.error("      device benchmark failed: %s", e)
        return None


def _aggregate_and_save(
    all_results: dict[str, Any],
    bench_summary: dict[str, Any] | None,
    env: dict[str, Any],
) -> None:
    """[6/7] 指标聚合 + [7/7] 保存：metrics.json、CSV、LaTeX、md 表格。"""
    logger.info("[6/7] Aggregating metrics ...")
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "paper_tables").mkdir(exist_ok=True)

    metrics: dict[str, Any] = {"env": env, "groups": {}}
    for group, shorts in PAPER_GROUPS.items():
        metrics["groups"][group] = {s: extract_headline(s, all_results.get(s, {})) for s in shorts}
    if bench_summary:
        metrics["benchmark"] = bench_summary
    (RESULTS / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False))

    # 效率 CSV
    raw = (bench_summary or {}).get("all_batch_sizes", {})
    if raw:
        def _csv(name: str, cols: list[tuple[str, str]]) -> None:
            with open(RESULTS / name, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow([c[0] for c in cols])
                for bs, r in sorted(raw.items()):
                    w.writerow([r.get(c[1]) if c[1] != "batch_size" else bs for c in cols])
        _csv("latency.csv", [("batch_size", "batch_size"), ("p50_ms", "latency_p50_ms"),
                             ("p90_ms", "latency_p90_ms"), ("p99_ms", "latency_p99_ms")])
        _csv("throughput.csv", [("batch_size", "batch_size"), ("samples_per_sec", "throughput_sps")])
        _csv("memory.csv", [("batch_size", "batch_size"), ("peak_mem_mb", "peak_mem_mb")])

    logger.info("[7/7] Writing paper tables (md + LaTeX) ...")
    md = ["# Paper Tables (auto-generated from real results)", ""]
    for group, shorts in PAPER_GROUPS.items():
        md.append(f"## {group}")
        for s in shorts:
            ex = extract_headline(s, all_results.get(s, {}))
            comp = all_results.get(s, {}).get("computation", "-")
            md.append(f"- **{s}** ({comp}): " + ", ".join(f"{k}={v}" for k, v in ex.items()))
        md.append("")
    (RESULTS / "paper_table.md").write_text("\n".join(md) + "\n")

    def _latex(fname: str, title: str, header: list[str], body_rows: list[list[Any]]) -> None:
        L = ["\\begin{table}[t]", "\\centering", f"\\caption{{{title}}}",
             "\\begin{tabular}{" + "l" * len(header) + "}", "\\toprule",
             " & ".join(header) + " \\\\", "\\midrule"]
        L += [" & ".join(str(c) for c in row) + " \\\\" for row in body_rows]
        L += ["\\bottomrule", "\\end{tabular}", "\\end{table}"]
        (RESULTS / "paper_tables" / fname).write_text("\n".join(L) + "\n")

    main_rows = [
        ["exp13 (fusion)", all_results.get("exp13", {}).get("computation", "-"),
         extract_headline("exp13", all_results.get("exp13", {})).get("F1[late]", "-")],
        ["exp11 (int4)", all_results.get("exp11", {}).get("computation", "-"),
         extract_headline("exp11", all_results.get("exp11", {})).get("F1[int4]", "-")],
        ["exp1 (QAD-LLM)", all_results.get("exp1", {}).get("computation", "-"),
         extract_headline("exp1", all_results.get("exp1", {})).get("F1", "-")],
    ]
    _latex("table1_main.tex", "Main Result (F1)", ["Experiment", "Computation", "F1"], main_rows)
    abl_rows = [[k, v] for k, v in extract_headline("exp3", all_results.get("exp3", {})).items()]
    _latex("table2_ablation.tex", "OV-Freeze Ablation (variance drift \\%)",
           ["Condition", "Drift(\\%)"], abl_rows)
    eff_rows = [[bs, r.get("latency_p50_ms"), r.get("throughput_sps"),
                 r.get("peak_mem_mb")] for bs, r in sorted(raw.items())]
    _latex("table3_efficiency.tex", "Efficiency (H100 benchmark)",
           ["Batch", "p50(ms)", "samp/s", "peak mem(MB)"], eff_rows or [["-", "-", "-", "-"]])

    _print_summary(all_results, bench_summary)
    logger.info("Done. Deliverables in %s/", RESULTS)


def _print_summary(all_results: dict[str, Any], bench_summary: dict[str, Any] | None) -> None:
    """Final RealEval banner."""
    print("\n=== RealEval-v2 H100 Benchmark ===")
    print(f"QAD:         F1 {all_results.get('exp1', {}).get('f1', 'n/a')}")
    ov = extract_headline("exp3", all_results.get("exp3", {}))
    print(f"OV-Freeze:   drift {ov.get('drift[ov_freeze_full]', 'n/a')}% "
          f"(vs no_reg {ov.get('drift[no_reg]', 'n/a')}%)")
    sd = extract_headline("exp6", all_results.get("exp6", {}))
    print(f"Speculative: alpha generic={sd.get('alpha_generic', 'n/a')} "
          f"domain={sd.get('alpha_domain', 'NOT MEASURED')}")
    print(f"Privacy:     speaker-ID acc {all_results.get('exp7', {}).get('speaker_id_accuracy', 'n/a')}, "
          f"ASV-EER {all_results.get('exp7', {}).get('asv_eer_pct', 'n/a')}%")
    raw = (bench_summary or {}).get("all_batch_sizes", {})
    if raw:
        first_bs = min(raw)
        r0 = raw[first_bs]
        print(f"Latency:     P50 {r0.get('latency_p50_ms', 'n/a')} ms  "
              f"P99 {r0.get('latency_p99_ms', 'n/a')} ms (bs={first_bs})")
    else:
        print("Latency:     (run --paper on H100 for real latency)")
    print("DONE\n")


def main() -> int:
    ap = build_pipeline_parser()
    args = ap.parse_args()

    if not args.no_archive:
        try:
            archived = archive_if_needed()
            if archived:
                logger.info("旧实验结果已归档至：%s", archived)
        except Exception as _ae:
            logger.warning("归档步骤失败（继续运行）：%s", _ae)

    config = load_config(args.config, validate=False)
    if args.paper:
        config["_paper"] = True

    from realeval import validation
    try:
        validation.validate_config(config)
    except validation.ValidationError as e:
        logger.error("Config validation failed: %s", e)
        return 1

    has_cuda, env = _cuda_check()
    config = _apply_h100_optims(config, has_cuda)
    all_results = _run_experiments(config)
    bench_summary = _device_benchmark(config, has_cuda) if args.paper else None
    _aggregate_and_save(all_results, bench_summary, env)

    if args.paper:
        try:
            from experiments.consistency_check import audit, print_report
            report = audit()
            has_p0 = print_report(report)
            if has_p0:
                logger.warning("P0 DRIFT/SMOKE issues detected — update paper numbers before publication")
        except Exception as _ce:
            logger.warning("consistency_check skipped: %s", _ce)
    return 0


if __name__ == "__main__":
    sys.exit(main())
