"""exp8: Latency Benchmark — Measure inference latency across quantization schemes."""
from __future__ import annotations
import logging
from experiments.framework import load_first_nonempty, quantile_ms, run_with_mode

logger = logging.getLogger("exp8")


def run(config: dict) -> dict:
    from realeval import data
    dataset_name = config.get("data", {}).get("dataset", "balanced4k")
    max_samples = config.get("data", {}).get("max_samples", 100)
    ds = load_first_nonempty(
        loaders=[
            lambda: data.load_dataset(dataset_name, max_samples=max_samples),
            lambda: data.load_chifraud_balanced(max_samples=max_samples),
        ],
        synthetic_loader=lambda: data.load_synthetic(n=50),
    )
    texts = ds.texts

    def run_paper(config):
        from realeval import real_backend, models, hwenv
        import torch
        import time

        real_backend.require_assets(models.models_available(config), "Real Qwen weights unavailable")

        # Use the same prompt template as classification, but time pure forward inference only.
        prompts = [real_backend._cls_prompt(t) for t in texts[:20]]
        if not prompts:
            prompts = [real_backend._cls_prompt("测试消息")]

        batch_size = max(1, int(config.get("training", {}).get("batch_size", 8)))
        max_seq = int(config.get("distillation", {}).get("max_seq_length", 256))
        warmup = max(1, int(config.get("benchmark", {}).get("warmup", 2)))
        repeat = max(3, int(config.get("benchmark", {}).get("repeat", 10)))

        latency_detail = {}
        # bf16: quantize=None with bf16=True is the proper native-BF16 path on H100.
        # fp16: quantize="fp16" forces explicit float16.  int4/int8: bitsandbytes.
        quant_specs = [("bf16", None, True), ("fp16", "fp16", False),
                       ("int4", "int4", True), ("int8", "int8", True)]
        for quant_label, quant_arg, use_bf16 in quant_specs:
            model, tok = models.load_causal_lm(
                config["models"]["teacher"], quantize=quant_arg, bf16=use_bf16
            )
            real_backend.require_assets(model is not None, f"Model loading failed for {quant_label}")
            dev = next(model.parameters()).device

            # Attach LoRA adapter when available (consistent with normal inference path).
            # Convert adapter-not-found RuntimeError to AssetsUnavailable so smoke
            # fallback triggers cleanly when weights are absent on the local machine.
            from realeval.student_loader import attach_adapter
            from realeval.real_backend import AssetsUnavailable
            try:
                model = attach_adapter(model, config.get("student_variant", "base"), config, quantize=quant_arg)
            except RuntimeError as e:
                raise AssetsUnavailable(f"QAD adapter unavailable for latency benchmark: {e}") from e
            model.eval()

            times_ms = []
            with torch.inference_mode():
                # Warmup passes to reduce first-run effects.
                for _ in range(warmup):
                    for s in range(0, len(prompts), batch_size):
                        enc = tok(
                            prompts[s:s + batch_size],
                            return_tensors="pt",
                            padding=True,
                            truncation=True,
                            max_length=max_seq,
                        ).to(dev)
                        with hwenv.autocast_context():
                            _ = model(**enc).logits

                for _ in range(repeat):
                    t0 = time.perf_counter()
                    for s in range(0, len(prompts), batch_size):
                        enc = tok(
                            prompts[s:s + batch_size],
                            return_tensors="pt",
                            padding=True,
                            truncation=True,
                            max_length=max_seq,
                        ).to(dev)
                        with hwenv.autocast_context():
                            _ = model(**enc).logits
                    times_ms.append((time.perf_counter() - t0) * 1000)

            latency_detail[quant_label] = {
                "p50_ms": round(quantile_ms(times_ms, 50), 3),
                "p90_ms": round(quantile_ms(times_ms, 90), 3),
                "p99_ms": round(quantile_ms(times_ms, 99), 3),
            }

        latencies = {k: v["p50_ms"] for k, v in latency_detail.items()}

        # Batch-level efficiency benchmark (for Table 7)
        # Measures latency/throughput/memory at different batch sizes with int4 quant.
        batch_benchmark = {}
        try:
            import torch
            model, tok = models.load_causal_lm(
                config["models"]["teacher"], quantize="int4", bf16=True
            )
            dev = next(model.parameters()).device
            model.eval()
            for bs in (1, 8, 32, 64):
                try:
                    batch_prompts = prompts[:min(bs, len(prompts))]
                    if len(batch_prompts) < bs:
                        batch_prompts = batch_prompts * ((bs // len(batch_prompts)) + 1)
                    batch_prompts = batch_prompts[:bs]
                    enc = tok(batch_prompts, return_tensors="pt", padding=True,
                             truncation=True, max_length=max_seq).to(dev)
                    torch.cuda.reset_peak_memory_stats(dev)
                    # Warmup
                    for _ in range(2):
                        with torch.inference_mode():
                            _ = model(**enc).logits
                    torch.cuda.synchronize()
                    t0 = time.perf_counter()
                    for _ in range(repeat):
                        with torch.inference_mode():
                            _ = model(**enc).logits
                    torch.cuda.synchronize()
                    elapsed_ms = (time.perf_counter() - t0) / repeat * 1000
                    mem_mb = torch.cuda.max_memory_allocated(dev) / 1e6 if torch.cuda.is_available() else 0
                    batch_benchmark[str(bs)] = {
                        "latency_p50_ms": round(elapsed_ms, 2),
                        "throughput_sps": round(bs / (elapsed_ms / 1000), 1) if elapsed_ms > 0 else 0,
                        "peak_mem_mb": round(mem_mb, 1),
                    }
                except Exception as e:
                    logger.warning("Batch benchmark bs=%d failed: %s", bs, e)
        except Exception as e:
            logger.warning("Batch-level benchmark unavailable: %s", e)

        return {
            "experiment": "exp8",
            "computation": "h100_real_qwen",
            "latencies": latencies,
            "latency_detail": latency_detail,
            "batch_benchmark": batch_benchmark,
            "all_batch_sizes": batch_benchmark,  # alias for paper_pipeline compatibility
        }

    def run_smoke(_: dict) -> dict:
        logger.info("SMOKE: running small-model verification for exp8")
        import time
        import torch

        torch.manual_seed(0)
        x = torch.randn(64, 128)
        # Smoke: use separate passes for bf16/fp16 (both half()) and int8/int4 (uniform quant).
        # CPU doesn't distinguish BF16 from FP16 in a toy MLP, but keeping separate passes
        # preserves the same key structure as the paper path.
        latency_detail = {}
        for quant, bits in (("bf16", 16), ("fp16", 16), ("int8", 8), ("int4", 4)):
            torch.manual_seed(0)
            m = torch.nn.Sequential(torch.nn.Linear(128, 256), torch.nn.ReLU(), torch.nn.Linear(256, 2))
            if bits >= 16:
                m = m.half()
            xi = x.half() if bits >= 16 else x.clone()
            if bits < 16:
                levels = 2 ** bits
                xi = torch.round(xi * levels) / levels
            with torch.no_grad():
                for _ in range(3):
                    m(xi)
                ts = []
                for _ in range(20):
                    t0 = time.perf_counter()
                    m(xi)
                    ts.append((time.perf_counter() - t0) * 1000)
            latency_detail[quant] = {
                "p50_ms": round(quantile_ms(ts, 50), 4),
                "p90_ms": round(quantile_ms(ts, 90), 4),
                "p99_ms": round(quantile_ms(ts, 99), 4),
            }

        latencies = {k: v["p50_ms"] for k, v in latency_detail.items()}
        batch_benchmark = {
            str(bs): {
                "latency_p50_ms": round(latencies["int4"] * max(1, bs) / 8, 4),
                "throughput_sps": round(bs / (latencies["int4"] * max(1, bs) / 8 / 1000), 1),
                "peak_mem_mb": None,
            }
            for bs in (1, 8, 32, 64)
        }
        return {
            "experiment": "exp8",
            "computation": "smoke_cpu",
            "latencies": latencies,
            "latency_detail": latency_detail,
            "batch_benchmark": batch_benchmark,
            "all_batch_sizes": batch_benchmark,
        }

    return run_with_mode("exp8", config, run_paper, run_smoke)
