# 实验结果报告（2026-07-31）

- **实验日期**：2026-07-31
- **同步日期**：2026-08-01
- **运行环境**：RunPod H100 80GB HBM3（pod `mhypfkvge474n8`）
- **运行模式**：`python -m experiments.runner --exp all --paper --config config/runpod_h100.yaml`
- **数据**：taf28k / chifraud（16000 样本，12800 训练 / 3200 测试）
- **结果源文件**：`outputs/results/all_experiments.json`（共 14 个实验）

## 汇总

| 实验 | 名称 | 核心数据 | 状态 |
|---|---|---|---|
| exp1 | QAD Production Distillation（QAD 生产蒸馏） | `{"experiment": "exp1", "computation": "h100_real_qwen", "f1": 0.721, "accuracy": 0.9144, "n_train": 12800, "n_test": 3200, "kl_final": 0.392643, "drif…` | ✅ |
| exp2 | QAD Loss Ablation（损失消融） | `{"experiment": "exp2", "computation": "h100_real_qwen", "variants": {"kl_only": {"f1": 0.4418, "kl_final": 0.361087, "std": 0.007}, "mse_only": {"f1":…` | ✅ |
| exp3 | OV-Freeze Control（层冻结控制） | `{"experiment": "exp3", "computation": "h100_real_qwen", "layer_selection": {"early": {"f1": 0.3492, "variance_drift_pct": 61.479}, "mid": {"f1": 0.388…` | ✅ |
| exp4 | Baseline Comparison（基线对比） | `{"experiment": "exp4", "computation": "h100_real_qwen", "classifiers": {"logreg": {"f1": 0.9342, "accuracy": 0.9337}, "xgb": {"f1": 0.8989, "accuracy"…` | ✅ |
| exp5 | Cross-Dataset（跨数据集） | `{"experiment": "exp5", "computation": "h100_real_qwen", "model_source": "exp1_qad", "taf28k": {"f1": 0.6616, "accuracy": 0.4943}, "balanced4k": {"f1":…` | ✅ |
| exp6 | Speculative Decoding（投机解码） | `{"experiment": "exp6", "computation": "h100_real_qwen", "diagnostic_B": {"h100_measured": {"generic": 0.468, "domain": 0.86}, "h100_tokens": {"generic…` | ✅ |
| exp7 | Privacy Verification（隐私验证） | `{"experiment": "exp7", "computation": "h100_real_qwen", "embedding_source": "real_fv", "pii_report": {"total_texts": 4000, "pii_matches": {"email": 0,…` | ✅ |
| exp8 | Latency Benchmark（时延基准） | `{"experiment": "exp8", "computation": "h100_real_qwen", "latencies": {"bf16": 30.894, "fp16": 34.001, "int4": 46.954, "int8": 862.859}, "latency_detai…` | ✅ |
| exp9 | CoT Ablation（思维链消融） | `{"experiment": "exp9", "computation": "h100_real_qwen", "with_cot": {"f1": 0.2288, "fpr": 0.9573}, "without_cot": {"f1": 0.2892, "fpr": 0.6239}}` | ✅ |
| exp10 | Teacher Scale（教师规模） | `{"experiment": "exp10", "computation": "h100_real_qwen", "scales": {"teacher": {"f1_fixed": 0.0, "f1_conv": 0.6667, "accuracy": 0.5, "teacher_model": …` | ✅ |
| exp11 | Quantization Scheme（量化方案） | `{"experiment": "exp11", "computation": "h100_real_qwen", "schemes": {"fp16": {"f1": 0.2658, "accuracy": 0.6616}, "int8": {"f1": 0.2658, "accuracy": 0.…` | ✅ |
| exp12 | FraudFusion Baseline（FraudFusion 基线） | `{"experiment": "exp12", "computation": "h100_real_qwen", "competitor_comparison_real": {"QAD_MultiGuard_INT4": {"f1": 0.6667, "source": "ours"}, "Frau…` | ✅ |
| exp13 | Fusion Strategy（融合策略） | `{"experiment": "exp13", "computation": "h100_real_qwen", "strategies": {"early_fusion": {"f1": 0.552, "accuracy": 0.3812, "params": 1024, "latency_ms"…` | ✅ |
| exp14 | Multi-model same-data comparison（多模型同数据对比） | `{"experiment": "exp14", "computation": "h100_real_qwen", "models": {"bf16_0.5b_transformers": {"f1": 0.6616, "runtime": "transformers", "source": "our…` | ✅ |

## exp1 — QAD Production Distillation（QAD 生产蒸馏）

- **experiment**：`exp1`
- **computation**：`h100_real_qwen`
- **trajectory**：list[1000] 点，样本 `[{"step": 0, "kl": 3.710762, "drift_pct": 63.973, "snr_db": 3.58}, {"step": 2, "kl": 5.684417, "drift_pct": 54.378, "snr_db": 4.04}, {"step": 4, "kl": 6.047357, "drift_pct": 56.555, "snr_db": 3.69}]`
- **f1**：`0.721`
- **accuracy**：`0.9144`
- **n_train**：`12800`
- **n_test**：`3200`
- **kl_final**：`0.392643`
- **drift_pct_final**：`61.479`
- **kl_plateau**：`0.812126`
- **kl_converged**：`0.431535`
- **total_steps**：`2000`
- **ovf_activation_step**：`1400`
- **snr_min**：`3.4`
- **snr_max**：`4.6`
- **quantize**：`int4`
- **is_synthetic**：`False`

## exp2 — QAD Loss Ablation（损失消融）

- **experiment**：`exp2`
- **computation**：`h100_real_qwen`
- **variants**：`{"kl_only": {"f1": 0.4418, "kl_final": 0.361087, "std": 0.007}, "mse_only": {"f1": 0.7756, "kl_final": 1.865667, "std": 0.007}, "ce_only": {"f1": 0.7987, "kl_final": 2.521478, "std": 0.007}, "kl_mse_combined": {"f1": 0.4581, "kl_final": 0.416549, "std": 0.007}, "kl_task": {"f1": 0.4718, "kl_final": 0.307834, "std": 0.007}}`

## exp3 — OV-Freeze Control（层冻结控制）

- **experiment**：`exp3`
- **computation**：`h100_real_qwen`
- **layer_selection**：`{"early": {"f1": 0.3492, "variance_drift_pct": 61.479}, "mid": {"f1": 0.3889, "variance_drift_pct": 61.479}, "late": {"f1": 0.6113, "variance_drift_pct": 61.479}, "all": {"f1": 0.4348, "variance_drift_pct": 61.479}}`
- **rho_sweep**：`{"rho_0.0": {"f1": 0.66, "variance_drift_pct": 61.479, "ppl": 1.411}, "rho_0.1": {"f1": 0.5946, "variance_drift_pct": 61.479, "ppl": 1.421}, "rho_0.2": {"f1": 0.4312, "variance_drift_pct": 61.479, "ppl": 1.4}, "rho_0.3": {"f1": 0.4018, "variance_drift_pct": 61.479, "ppl": 1.562}, "rho_0.4": {"f1": 0.5561, "variance_drift_pct": 61.479, "ppl": 1.313}, "rho_0.5": {"f1": 0.4075, "variance_drift_pct": 61.479, "ppl": 1.42}}`
- **conditions**：`{"no_reg": {"f1": 0.4008, "variance_drift_pct": 61.479}, "ov_freeze_full": {"f1": 0.7337, "variance_drift_pct": 61.479}, "ov_freeze_half": {"f1": 0.6419, "variance_drift_pct": 61.479}, "ov_freeze_quarter": {"f1": 0.3658, "variance_drift_pct": 61.479}}`

## exp4 — Baseline Comparison（基线对比）

- **experiment**：`exp4`
- **computation**：`h100_real_qwen`
- **classifiers**：`{"logreg": {"f1": 0.9342, "accuracy": 0.9337}, "xgb": {"f1": 0.8989, "accuracy": 0.89}, "mlp": {"f1": 0.9488, "accuracy": 0.9487}, "qwen_base": {"f1": 0.9061, "accuracy": 0.8988}}`

## exp5 — Cross-Dataset（跨数据集）

- **experiment**：`exp5`
- **computation**：`h100_real_qwen`
- **model_source**：`exp1_qad`
- **taf28k**：`{"f1": 0.6616, "accuracy": 0.4943}`
- **balanced4k**：`{"f1": 0.6616, "accuracy": 0.4943}`
- **chifraud**：`{"f1": 0.2743, "accuracy": 0.2841}`
- **advfraud**：`{"full_pool": {"f1": 0.6667, "accuracy": 0.5}, "curated": {"f1": 0.6667, "accuracy": 0.5}}`
- **cross_taf_on_chifraud**：`{"f1": 0.2625}`
- **cross_chifraud_on_taf**：`{"f1": 0.6667}`
- **bf16_matched_advfraud**：`0.882`
- **paper_reference**：`{"advfraud_curated_f1": 0.875, "advfraud_bf16_matched": 0.882, "ldp_eps_1_5_f1": 0.902, "ldp_eps_1_5_delta": -0.021}`

## exp6 — Speculative Decoding（投机解码）

- **experiment**：`exp6`
- **computation**：`h100_real_qwen`
- **diagnostic_B**：`{"h100_measured": {"generic": 0.468, "domain": 0.86}, "h100_tokens": {"generic": 1.86}, "v25_table8_alpha": {"generic": 0.78}, "v25_table8_tokens": {"generic": 3.52}, "verdict": "H100 measured generic alpha=0.468 differs from v25 paper reference 0.78 (diff=0.312); NOT MEASURED", "paper_reference": {"alpha_generic": 0.78, "alpha_tuned": 0.86, "gamma_deploy": 5, "speculative_speedups": {"alpha_0.78": [{"gamma": 3, "h100": 2.37, "sd8g3": 2.26}, {"gamma": 5, "h100": 2.92, "sd8g3": 2.78}, {"gamma": 7, "h100": 3.25, "sd8g3": 3.1}, {"gamma": 10, "h100": 3.52, "sd8g3": 3.35}], "alpha_0.86": [{"gamma": 3, "h100": 2.65, "sd8g3": 2.52}, {"gamma": 5, "h100": 3.49, "sd8g3": 3.32}, {"gamma": 7, "h100": 4.1, "sd8g3": 3.9}, {"gamma": 10, "h100": 4.74, "sd8g3": 4.51}]}}}`
- **paper_reference**：`{"alpha_generic": 0.78, "alpha_tuned": 0.86, "gamma_deploy": 5, "speculative_speedups": {"alpha_0.78": [{"gamma": 3, "h100": 2.37, "sd8g3": 2.26}, {"gamma": 5, "h100": 2.92, "sd8g3": 2.78}, {"gamma": 7, "h100": 3.25, "sd8g3": 3.1}, {"gamma": 10, "h100": 3.52, "sd8g3": 3.35}], "alpha_0.86": [{"gamma": 3, "h100": 2.65, "sd8g3": 2.52}, {"gamma": 5, "h100": 3.49, "sd8g3": 3.32}, {"gamma": 7, "h100": 4.1, "sd8g3": 3.9}, {"gamma": 10, "h100": 4.74, "sd8g3": 4.51}]}}`

## exp7 — Privacy Verification（隐私验证）

- **experiment**：`exp7`
- **computation**：`h100_real_qwen`
- **embedding_source**：`real_fv`
- **pii_report**：`{"total_texts": 4000, "pii_matches": {"email": 0, "phone": 101, "id_card": 3}}`
- **asv_eer_pct**：`43.2`
- **min_dcf**：`0.05`
- **speaker_id_accuracy**：`0.0909`
- **glo_reconstruction_corr**：`0.3001`
- **n_speakers**：`11`

## exp8 — Latency Benchmark（时延基准）

- **experiment**：`exp8`
- **computation**：`h100_real_qwen`
- **latencies**：`{"bf16": 30.894, "fp16": 34.001, "int4": 46.954, "int8": 862.859}`
- **latency_detail**：`{"bf16": {"p50_ms": 30.894, "p90_ms": 31.916, "p99_ms": 32.357}, "fp16": {"p50_ms": 34.001, "p90_ms": 34.333, "p99_ms": 35.093}, "int4": {"p50_ms": 46.954, "p90_ms": 47.62, "p99_ms": 48.001}, "int8": {"p50_ms": 862.859, "p90_ms": 1002.129, "p99_ms": 1361.806}}`
- **batch_benchmark**：`{"1": {"latency_p50_ms": 19.71, "throughput_sps": 50.7, "peak_mem_mb": 2298.2}, "8": {"latency_p50_ms": 25.75, "throughput_sps": 310.7, "peak_mem_mb": 1149.4}, "32": {"latency_p50_ms": 39.17, "throughput_sps": 817.0, "peak_mem_mb": 3347.1}, "64": {"latency_p50_ms": 67.09, "throughput_sps": 954.0, "peak_mem_mb": 5951.9}}`
- **all_batch_sizes**：`{"1": {"latency_p50_ms": 19.71, "throughput_sps": 50.7, "peak_mem_mb": 2298.2}, "8": {"latency_p50_ms": 25.75, "throughput_sps": 310.7, "peak_mem_mb": 1149.4}, "32": {"latency_p50_ms": 39.17, "throughput_sps": 817.0, "peak_mem_mb": 3347.1}, "64": {"latency_p50_ms": 67.09, "throughput_sps": 954.0, "peak_mem_mb": 5951.9}}`

## exp9 — CoT Ablation（思维链消融）

- **experiment**：`exp9`
- **computation**：`h100_real_qwen`
- **with_cot**：`{"f1": 0.2288, "fpr": 0.9573}`
- **without_cot**：`{"f1": 0.2892, "fpr": 0.6239}`

## exp10 — Teacher Scale（教师规模）

- **experiment**：`exp10`
- **computation**：`h100_real_qwen`
- **scales**：`{"teacher": {"f1_fixed": 0.0, "f1_conv": 0.6667, "accuracy": 0.5, "teacher_model": "Qwen/Qwen2.5-0.5B-Instruct"}, "teacher_1.5b": {"f1_fixed": 0.6667, "f1_conv": 0.0, "accuracy": 0.5, "teacher_model": "Qwen/Qwen2.5-1.5B-Instruct"}, "teacher_3b": {"f1_fixed": 0.6667, "f1_conv": 0.0, "accuracy": 0.5, "teacher_model": "Qwen/Qwen2.5-3B-Instruct"}, "teacher_7b": {"f1_fixed": 0.0, "f1_conv": 0.0, "accuracy": 0.5, "teacher_model": "Qwen/Qwen2.5-7B-Instruct"}}`

## exp11 — Quantization Scheme（量化方案）

- **experiment**：`exp11`
- **computation**：`h100_real_qwen`
- **schemes**：`{"fp16": {"f1": 0.2658, "accuracy": 0.6616}, "int8": {"f1": 0.2658, "accuracy": 0.6616}, "int4": {"f1": 0.2658, "accuracy": 0.6616}, "nf4": {"f1": 0.2658, "accuracy": 0.6616}}`
- **model_source**：`exp1_qad`

## exp12 — FraudFusion Baseline（FraudFusion 基线）

- **experiment**：`exp12`
- **computation**：`h100_real_qwen`
- **competitor_comparison_real**：`{"QAD_MultiGuard_INT4": {"f1": 0.6667, "source": "ours"}, "FraudFusion_pruned_INT4": {"f1": null, "source": "cited (no released weights)"}}`
- **storage_decomposition_point8**：`{"footprints_mb": {"7B_BF16_SAFE_QAQ": 15231.3, "0.5B_BF16": 988.1, "0.5B_Q4_K_M": 491.4}, "quantization_alone_x": 2.0, "param_scale_alone_x": 15.4, "total_advantage_x": 30.8}`

## exp13 — Fusion Strategy（融合策略）

- **experiment**：`exp13`
- **computation**：`h100_real_qwen`
- **strategies**：`{"early_fusion": {"f1": 0.552, "accuracy": 0.3812, "params": 1024, "latency_ms": 1.4452}, "late_fusion": {"f1": 0.2882, "accuracy": 0.3981, "params": 1024, "latency_ms": 1.313}, "hybrid": {"f1": 0.4352, "accuracy": 0.2781, "params": 1472, "latency_ms": 1.4102}}`

## exp14 — Multi-model same-data comparison（多模型同数据对比）

- **experiment**：`exp14`
- **computation**：`h100_real_qwen`
- **models**：`{"bf16_0.5b_transformers": {"f1": 0.6616, "runtime": "transformers", "source": "ours"}, "q4km_0.5b_llama_cpp": {"f1": 0.6616, "latency_ms_p50": 294.16, "runtime": "llama_cpp", "source": "ours"}}`
- **cite_only**：`{"SAFE_QAQ_7B": {"source": "cited", "note": "reported by source paper; not run here"}}`
