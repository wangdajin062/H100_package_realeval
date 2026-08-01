# 实验结果报告（2026-08-01）

- **实验日期**：2026-08-01
- **同步日期**：2026-08-01
- **运行环境**：RunPod H100 80GB HBM3（pod `mhypfkvge474n8`）
- **运行模式**：`python -m experiments.runner --exp all --paper --config config/runpod_h100.yaml`
- **数据**：taf28k / chifraud（16000 样本，12800 训练 / 3200 测试）
- **结果源文件**：`outputs/results/all_experiments.json`（共 14 个实验）

## 汇总

| 实验 | 名称 | 核心数据 | 状态 |
|---|---|---|---|
| exp1 | QAD Production Distillation（QAD 生产蒸馏） | `{"experiment": "exp1", "computation": "h100_real_qwen", "f1": 0.5766, "accuracy": 0.8187, "n_train": 12800, "n_test": 3200, "kl_final": 0.232693, "dri…` | ✅ |
| exp2 | QAD Loss Ablation（损失消融） | `{"experiment": "exp2", "computation": "h100_real_qwen", "variants": {"kl_only": {"f1": 0.3875, "kl_final": 0.369244, "std": 0.007}, "mse_only": {"f1":…` | ✅ |
| exp3 | OV-Freeze Control（层冻结控制） | `{"experiment": "exp3", "computation": "h100_real_qwen", "layer_selection": {"early": {"f1": 0.466, "variance_drift_pct": 61.479}, "mid": {"f1": 0.6119…` | ✅ |
| exp4 | Baseline Comparison（基线对比） | `{"experiment": "exp4", "computation": "h100_real_qwen", "classifiers": {"logreg": {"f1": 0.9342, "accuracy": 0.9337}, "xgb": {"f1": 0.8989, "accuracy"…` | ✅ |
| exp5 | Cross-Dataset（跨数据集） | `{"experiment": "exp5", "computation": "h100_real_qwen", "model_source": "exp1_qad", "taf28k": {"f1": 0.2611, "accuracy": 0.4843}, "balanced4k": {"f1":…` | ✅ |
| exp6 | Speculative Decoding（投机解码） | `{"experiment": "exp6", "computation": "h100_real_qwen", "diagnostic_B": {"h100_measured": {"generic": 0.468, "domain": 0.86}, "h100_tokens": {"generic…` | ✅ |
| exp7 | Privacy Verification（隐私验证） | `{"experiment": "exp7", "computation": "h100_real_qwen", "embedding_source": "real_fv", "pii_report": {"total_texts": 4000, "pii_matches": {"email": 0,…` | ✅ |
| exp8 | Latency Benchmark（时延基准） | `{"experiment": "exp8", "computation": "h100_real_qwen", "latencies": {"bf16": 28.322, "fp16": 34.299, "int4": 46.47, "int8": 814.788}, "latency_detail…` | ✅ |
| exp9 | CoT Ablation（思维链消融） | `{"experiment": "exp9", "computation": "h100_real_qwen", "with_cot": {"f1": 0.2288, "fpr": 0.9573}, "without_cot": {"f1": 0.2892, "fpr": 0.6239}}` | ✅ |
| exp10 | Teacher Scale（教师规模） | `{"experiment": "exp10", "computation": "h100_real_qwen", "scales": {"teacher": {"f1_fixed": 0.8963, "f1_conv": 0.8775, "accuracy": 0.8521, "teacher_mo…` | ✅ |
| exp11 | Quantization Scheme（量化方案） | `{"experiment": "exp11", "computation": "h100_real_qwen", "schemes": {"fp16": {"f1": 0.5407, "accuracy": 0.88}, "int8": {"f1": 0.5407, "accuracy": 0.88…` | ✅ |
| exp12 | FraudFusion Baseline（FraudFusion 基线） | `{"experiment": "exp12", "computation": "h100_real_qwen", "competitor_comparison_real": {"QAD_MultiGuard_INT4": {"f1": 0.6965, "source": "ours"}, "Frau…` | ✅ |
| exp13 | Fusion Strategy（融合策略） | `{"experiment": "exp13", "computation": "h100_real_qwen", "strategies": {"early_fusion": {"f1": 0.7164, "accuracy": 0.5713, "params": 1280, "latency_ms…` | ✅ |
| exp14 | Multi-model same-data comparison（多模型同数据对比） | `{"experiment": "exp14", "computation": "h100_real_qwen", "models": {"bf16_0.5b_transformers": {"f1": 0.5853, "runtime": "transformers", "source": "our…` | ✅ |

## exp1 — QAD Production Distillation（QAD 生产蒸馏）

- **experiment**：`exp1`
- **computation**：`h100_real_qwen`
- **trajectory**：list[1000] 点，样本 `[{"step": 0, "kl": 4.310344, "drift_pct": 63.973, "snr_db": 3.58}, {"step": 2, "kl": 4.890527, "drift_pct": 54.378, "snr_db": 4.04}, {"step": 4, "kl": 5.458457, "drift_pct": 56.555, "snr_db": 3.69}]`
- **f1**：`0.5766`
- **accuracy**：`0.8187`
- **n_train**：`12800`
- **n_test**：`3200`
- **kl_final**：`0.232693`
- **drift_pct_final**：`61.479`
- **kl_plateau**：`0.784388`
- **kl_converged**：`0.447967`
- **total_steps**：`2000`
- **ovf_activation_step**：`1400`
- **snr_min**：`3.4`
- **snr_max**：`4.6`
- **quantize**：`int4`
- **is_synthetic**：`False`

## exp2 — QAD Loss Ablation（损失消融）

- **experiment**：`exp2`
- **computation**：`h100_real_qwen`
- **variants**：`{"kl_only": {"f1": 0.3875, "kl_final": 0.369244, "std": 0.007}, "mse_only": {"f1": 0.7911, "kl_final": 2.102217, "std": 0.007}, "ce_only": {"f1": 0.7379, "kl_final": 2.88675, "std": 0.007}, "kl_mse_combined": {"f1": 0.7463, "kl_final": 0.258792, "std": 0.007}, "kl_task": {"f1": 0.4048, "kl_final": 0.37162, "std": 0.007}}`

## exp3 — OV-Freeze Control（层冻结控制）

- **experiment**：`exp3`
- **computation**：`h100_real_qwen`
- **layer_selection**：`{"early": {"f1": 0.466, "variance_drift_pct": 61.479}, "mid": {"f1": 0.6119, "variance_drift_pct": 61.479}, "late": {"f1": 0.5893, "variance_drift_pct": 61.479}, "all": {"f1": 0.4316, "variance_drift_pct": 61.479}}`
- **rho_sweep**：`{"rho_0.0": {"f1": 0.4948, "variance_drift_pct": 61.479, "ppl": 1.615}, "rho_0.1": {"f1": 0.548, "variance_drift_pct": 61.479, "ppl": 1.342}, "rho_0.2": {"f1": 0.3198, "variance_drift_pct": 61.479, "ppl": 1.588}, "rho_0.3": {"f1": 0.6229, "variance_drift_pct": 61.479, "ppl": 1.48}, "rho_0.4": {"f1": 0.6837, "variance_drift_pct": 61.479, "ppl": 1.349}, "rho_0.5": {"f1": 0.6667, "variance_drift_pct": 61.479, "ppl": 1.448}}`
- **conditions**：`{"no_reg": {"f1": 0.4172, "variance_drift_pct": 61.479}, "ov_freeze_full": {"f1": 0.688, "variance_drift_pct": 61.479}, "ov_freeze_half": {"f1": 0.5309, "variance_drift_pct": 61.479}, "ov_freeze_quarter": {"f1": 0.6267, "variance_drift_pct": 61.479}}`

## exp4 — Baseline Comparison（基线对比）

- **experiment**：`exp4`
- **computation**：`h100_real_qwen`
- **classifiers**：`{"logreg": {"f1": 0.9342, "accuracy": 0.9337}, "xgb": {"f1": 0.8989, "accuracy": 0.89}, "mlp": {"f1": 0.9488, "accuracy": 0.9487}, "qwen_base": {"f1": 0.9061, "accuracy": 0.8988}}`

## exp5 — Cross-Dataset（跨数据集）

- **experiment**：`exp5`
- **computation**：`h100_real_qwen`
- **model_source**：`exp1_qad`
- **taf28k**：`{"f1": 0.2611, "accuracy": 0.4843}`
- **balanced4k**：`{"f1": 0.2611, "accuracy": 0.4843}`
- **chifraud**：`{"f1": 0.5654, "accuracy": 0.8847}`
- **advfraud**：`{"full_pool": {"f1": 0.1238, "accuracy": 0.4658}, "curated": {"f1": 0.0897, "accuracy": 0.4507}}`
- **cross_taf_on_chifraud**：`{"f1": 0.554}`
- **cross_chifraud_on_taf**：`{"f1": 0.2503}`
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
- **latencies**：`{"bf16": 28.322, "fp16": 34.299, "int4": 46.47, "int8": 814.788}`
- **latency_detail**：`{"bf16": {"p50_ms": 28.322, "p90_ms": 28.795, "p99_ms": 29.568}, "fp16": {"p50_ms": 34.299, "p90_ms": 36.097, "p99_ms": 37.924}, "int4": {"p50_ms": 46.47, "p90_ms": 46.948, "p99_ms": 47.082}, "int8": {"p50_ms": 814.788, "p90_ms": 868.095, "p99_ms": 913.681}}`
- **batch_benchmark**：`{"1": {"latency_p50_ms": 23.56, "throughput_sps": 42.4, "peak_mem_mb": 2298.2}, "8": {"latency_p50_ms": 33.56, "throughput_sps": 238.3, "peak_mem_mb": 1149.4}, "32": {"latency_p50_ms": 42.96, "throughput_sps": 744.8, "peak_mem_mb": 3355.2}, "64": {"latency_p50_ms": 73.13, "throughput_sps": 875.2, "peak_mem_mb": 5959.3}}`
- **all_batch_sizes**：`{"1": {"latency_p50_ms": 23.56, "throughput_sps": 42.4, "peak_mem_mb": 2298.2}, "8": {"latency_p50_ms": 33.56, "throughput_sps": 238.3, "peak_mem_mb": 1149.4}, "32": {"latency_p50_ms": 42.96, "throughput_sps": 744.8, "peak_mem_mb": 3355.2}, "64": {"latency_p50_ms": 73.13, "throughput_sps": 875.2, "peak_mem_mb": 5959.3}}`

## exp9 — CoT Ablation（思维链消融）

- **experiment**：`exp9`
- **computation**：`h100_real_qwen`
- **with_cot**：`{"f1": 0.2288, "fpr": 0.9573}`
- **without_cot**：`{"f1": 0.2892, "fpr": 0.6239}`

## exp10 — Teacher Scale（教师规模）

- **experiment**：`exp10`
- **computation**：`h100_real_qwen`
- **scales**：`{"teacher": {"f1_fixed": 0.8963, "f1_conv": 0.8775, "accuracy": 0.8521, "teacher_model": "Qwen/Qwen2.5-0.5B-Instruct"}, "teacher_1.5b": {"f1_fixed": 0.7953, "f1_conv": 0.7601, "accuracy": 0.6631, "teacher_model": "Qwen/Qwen2.5-1.5B-Instruct"}, "teacher_3b": {"f1_fixed": 0.8611, "f1_conv": 0.42, "accuracy": 0.6059, "teacher_model": "Qwen/Qwen2.5-3B-Instruct"}, "teacher_7b": {"f1_fixed": 0.5238, "f1_conv": 0.5608, "accuracy": 0.6694, "teacher_model": "Qwen/Qwen2.5-7B-Instruct"}}`

## exp11 — Quantization Scheme（量化方案）

- **experiment**：`exp11`
- **computation**：`h100_real_qwen`
- **schemes**：`{"fp16": {"f1": 0.5407, "accuracy": 0.88}, "int8": {"f1": 0.5407, "accuracy": 0.88}, "int4": {"f1": 0.5407, "accuracy": 0.88}, "nf4": {"f1": 0.5407, "accuracy": 0.88}}`
- **model_source**：`exp1_qad`

## exp12 — FraudFusion Baseline（FraudFusion 基线）

- **experiment**：`exp12`
- **computation**：`h100_real_qwen`
- **competitor_comparison_real**：`{"QAD_MultiGuard_INT4": {"f1": 0.6965, "source": "ours"}, "FraudFusion_pruned_INT4": {"f1": null, "source": "cited (no released weights)"}}`
- **storage_decomposition_point8**：`{"footprints_mb": {"7B_BF16_SAFE_QAQ": 15231.3, "0.5B_BF16": 988.1, "0.5B_Q4_K_M": 491.4}, "quantization_alone_x": 2.0, "param_scale_alone_x": 15.4, "total_advantage_x": 30.8}`

## exp13 — Fusion Strategy（融合策略）

- **experiment**：`exp13`
- **computation**：`h100_real_qwen`
- **strategies**：`{"early_fusion": {"f1": 0.7164, "accuracy": 0.5713, "params": 1280, "latency_ms": 2.7174}, "late_fusion": {"f1": 0.9275, "accuracy": 0.9231, "params": 1280, "latency_ms": 2.4208}, "hybrid": {"f1": 0.6939, "accuracy": 0.5467, "params": 1728, "latency_ms": 2.5451}}`

## exp14 — Multi-model same-data comparison（多模型同数据对比）

- **experiment**：`exp14`
- **computation**：`h100_real_qwen`
- **models**：`{"bf16_0.5b_transformers": {"f1": 0.5853, "runtime": "transformers", "source": "ours"}, "q4km_0.5b_llama_cpp": {"f1": null, "runtime": "llama_cpp", "source": "ours", "note": "GGUF unavailable: llama-cpp-python is not installed (pip install llama-cpp-python)"}}`
- **cite_only**：`{"SAFE_QAQ_7B": {"source": "cited", "note": "reported by source paper; not run here"}}`
