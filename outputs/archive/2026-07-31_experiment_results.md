# Experiment Results Archive

**Generated:** 2026-07-31 09:53:20  
**Experiments archived:** ['exp1', 'exp11', 'exp15', 'exp16', 'exp2', 'exp3', 'exp4', 'exp5', 'exp6', 'exp7', 'exp8']  
**Total result files:** 15  

---

## Summary (latest result per experiment)

| Experiment | Computation | F1 (headline) |
|------------|-------------|---------------|
| exp1 | h100_real_qwen | 0.9987 |
| exp11 | h100_real_qwen | 0.9937 |
| exp15 | h100_hybrid_audio | — |
| exp16 | h100_audio_encoders | — |
| exp2 | h100_real_qwen | — |
| exp3 | h100_real_qwen | 0.9117 |
| exp4 | h100_real_qwen | 0.9320 |
| exp5 | smoke_sklearn | — |
| exp6 | h100_real_qwen | — |
| exp7 | h100_real_qwen | — |
| exp8 | h100_real_qwen | — |

---

## Full Experiment Data

### exp1 — `exp1_20260715_031133.json`

```json
{
  "experiment": "exp1",
  "computation": "h100_real_qwen",
  "trajectory": [
    {
      "epoch": 0,
      "ce": 0.300662,
      "val_ce": 0.001039
    },
    {
      "epoch": 1,
      "ce": 0.004173,
      "val_ce": 0.000381
    },
    {
      "epoch": 2,
      "ce": 0.000487,
      "val_ce": 0.000236
    },
    {
      "epoch": 3,
      "ce": 0.003357,
      "val_ce": 0.000285
    },
    {
      "epoch": 4,
      "ce": 0.000237,
      "val_ce": 0.000421
    },
    {
      "epoch": 5,
      "ce": 0.000111,
      "val_ce": 0.000257
    },
    {
      "epoch": 6,
      "ce": 7.9e-05,
      "val_ce": 0.000274
    },
    {
      "epoch": 7,
      "ce": 7.8e-05,
      "val_ce": 0.000146
    },
    {
      "epoch": 8,
      "ce": 4.2e-05,
      "val_ce": 0.000149
    },
    {
      "epoch": 9,
      "ce": 5.1e-05,
      "val_ce": 0.000144
    },
    {
      "epoch": 10,
      "ce": 3.4e-05,
      "val_ce": 0.000153
    },
    {
      "epoch": 11,
      "ce": 3.3e-05,
      "val_ce": 0.000142
    },
    {
      "epoch": 12,
      "ce": 3.9e-05,
      "val_ce": 0.000152
    },
    {
      "epoch": 13,
      "ce": 3.4e-05,
      "val_ce": 0.000106
    },
    {
      "epoch": 14,
      "ce": 2.9e-05,
      "val_ce": 8.8e-05
    },
    {
      "epoch": 15,
      "ce": 1.9e-05,
      "val_ce": 9.9e-05
    },
    {
      "epoch": 16,
      "ce": 2.1e-05,
      "val_ce": 0.000103
    },
    {
      "epoch": 17,
      "ce": 1.8e-05,
      "val_ce": 0.000102
    },
    {
      "epoch": 18,
      "ce": 2.7e-05,
      "val_ce": 0.000108
    },
    {
      "epoch": 19,
      "ce": 1.5e-05,
      "val_ce": 9e-05
    },
    {
      "epoch": 20,
      "ce": 1.4e-05,
      "val_ce": 8.9e-05
    },
    {
      "epoch": 21,
      "ce": 1.2e-05,
      "val_ce": 8.8e-05
    },
    {
      "epoch": 22,
      "ce": 1.6e-05,
      "val_ce": 8.1e-05
    },
    {
      "epoch": 23,
      "ce": 1.3e-05,
      "val_ce": 5.9e-05
    },
    {
      "epoch": 24,
      "ce": 1.3e-05,
      "val_ce": 8.2e-05
    },
    {
      "epoch": 25,
      "ce": 1e-05,
      "val_ce": 6.7e-05
    },
    {
      "epoch": 26,
      "ce": 1.4e-05,
      "val_ce": 5.2e-05
    },
    {
      "epoch": 27,
      "ce": 1.1e-05,
      "val_ce": 4.4e-05
    },
    {
      "epoch": 28,
      "ce": 8e-06,
      "val_ce": 4.5e-05
    },
    {
      "epoch": 29,
      "ce": 1.1e-05,
      "val_ce": 4.9e-05
    }
  ],
  "f1": 0.9987,
  "accuracy": 0.9988,
  "n_train": 2880,
  "n_test": 800,
  "best_epoch": 28,
  "best_val_ce": 4.4e-05,
  "is_synthetic": false
}
```

### exp11 — `exp11_20260715_031234.json`

```json
{
  "experiment": "exp11",
  "computation": "h100_real_qwen",
  "schemes": {
    "fp32": {
      "f1": 0.9937,
      "accuracy": 0.9938
    },
    "fp16": {
      "f1": 0.9937,
      "accuracy": 0.9938
    },
    "bf16": {
      "f1": 0.995,
      "accuracy": 0.995
    }
  }
}
```

### exp15 — `exp15_20260722_024452.json`

```json
{
  "experiment": "exp15",
  "computation": "h100_hybrid_audio",
  "audio_only": {
    "f1": 0.9695,
    "accuracy": 0.97,
    "latency_ms_per_sample": 0.01653,
    "classifier": "MLP(128,32)+Calibrated",
    "n_params": 0
  },
  "text_only": {
    "f1": 0.6667,
    "accuracy": 0.5,
    "latency_ms_per_sample": 20.0,
    "classifier": "Qwen2.5-0.5B (base, zero-shot)"
  },
  "hybrid_sweep": {
    "thresh_0.5": {
      "f1": 0.9695,
      "accuracy": 0.97,
      "coverage_pct": 100.0,
      "n_fast": 400,
      "n_slow": 0,
      "avg_latency_ms": 0.0165,
      "speedup_vs_text_only": 1210.0
    },
    "thresh_0.6": {
      "f1": 0.98,
      "accuracy": 0.98,
      "coverage_pct": 98.2,
      "n_fast": 393,
      "n_slow": 7,
      "avg_latency_ms": 0.3665,
      "speedup_vs_text_only": 54.6
    },
    "thresh_0.7": {
      "f1": 0.9825,
      "accuracy": 0.9825,
      "coverage_pct": 96.5,
      "n_fast": 386,
      "n_slow": 14,
      "avg_latency_ms": 0.7165,
      "speedup_vs_text_only": 27.9
    },
    "thresh_0.75": {
      "f1": 0.9825,
      "accuracy": 0.9825,
      "coverage_pct": 96.0,
      "n_fast": 384,
      "n_slow": 16,
      "avg_latency_ms": 0.8165,
      "speedup_vs_text_only": 24.5
    },
    "thresh_0.8": {
      "f1": 0.9825,
      "accuracy": 0.9825,
      "coverage_pct": 96.0,
      "n_fast": 384,
      "n_slow": 16,
      "avg_latency_ms": 0.8165,
      "speedup_vs_text_only": 24.5
    },
    "thresh_0.85": {
      "f1": 0.9778,
      "accuracy": 0.9775,
      "coverage_pct": 93.5,
      "n_fast": 374,
      "n_slow": 26,
      "avg_latency_ms": 1.3165,
      "speedup_vs_text_only": 15.2
    },
    "thresh_0.9": {
      "f1": 0.9682,
      "accuracy": 0.9675,
      "coverage_pct": 92.2,
      "n_fast": 369,
      "n_slow": 31,
      "avg_latency_ms": 1.5665,
      "speedup_vs_text_only": 12.8
    },
    "thresh_0.95": {
      "f1": 0.9567,
      "accuracy": 0.955,
      "coverage_pct": 89.2,
      "n_fast": 357,
      "n_slow": 43,
      "avg_latency_ms": 2.1665,
      "speedup_vs_text_only": 9.2
    }
  },
  "optimal": {
    "threshold": "thresh_0.5",
    "f1": 0.9695,
    "avg_latency_ms": 0.0165,
    "speedup_vs_text_only": 1210.0
  },
  "architecture": {
    "fast_path": "MLP(512→128→32→2) on audio embeddings, ~0.1ms CPU",
    "slow_path": "Qwen2.5-0.5B zero-shot text classification, ~20ms GPU",
    "gate": "Confidence threshold on audio classifier softmax output",
    "production_estimate": "60-80% samples fast path → 5-13ms avg latency"
  }
}
```

### exp16 — `exp16_20260715_061945.json`

```json
{
  "experiment": "exp16",
  "computation": "h100_audio_encoders",
  "encoders": {
    "logreg": {
      "f1": 0.9774,
      "accuracy": 0.9775,
      "latency_ms": 0.000587,
      "n_params": 1025
    },
    "mlp_small(64)": {
      "f1": 0.9848,
      "accuracy": 0.985,
      "latency_ms": 0.003751
    },
    "mlp_medium(128,32)": {
      "f1": 0.9645,
      "accuracy": 0.965,
      "latency_ms": 0.001883
    },
    "svm_rbf": {
      "f1": 0.9435,
      "accuracy": 0.9425,
      "latency_ms": 0.2386,
      "note": "trained on 2000 subsample"
    }
  },
  "pareto_best": "mlp_small(64)",
  "n_train": 4000,
  "n_test": 400
}
```

### exp2 — `exp2_20260715_031258.json`

```json
{
  "experiment": "exp2",
  "computation": "h100_real_qwen",
  "variants": {
    "kl_only": {
      "f1": 0.9117,
      "kl_final": 0.8505190670490265
    },
    "mse_only": {
      "f1": 0.9117,
      "kl_final": 1.644385335445404
    },
    "kl_mse_combined": {
      "f1": 0.9117,
      "kl_final": 2.4949043941497804
    }
  }
}
```

### exp3 — `exp3_20260715_031422.json`

```json
{
  "experiment": "exp3",
  "computation": "h100_real_qwen",
  "layer_selection": {
    "early": {
      "f1": 0.9117,
      "variance_drift_pct": 9.779375
    },
    "mid": {
      "f1": 0.9117,
      "variance_drift_pct": 6.696875
    },
    "late": {
      "f1": 0.9117,
      "variance_drift_pct": 2.77875
    },
    "all": {
      "f1": 0.9117,
      "variance_drift_pct": 0.3126953125
    }
  },
  "rho_sweep": {
    "rho_0.1": {
      "f1": 0.9117,
      "variance_drift_pct": 11.7,
      "ppl": 2.341
    },
    "rho_0.3": {
      "f1": 0.9117,
      "variance_drift_pct": 9.021875,
      "ppl": 2.341
    },
    "rho_0.5": {
      "f1": 0.9117,
      "variance_drift_pct": 6.469375,
      "ppl": 2.341
    },
    "rho_0.7": {
      "f1": 0.9117,
      "variance_drift_pct": 3.8528125,
      "ppl": 2.341
    },
    "rho_0.9": {
      "f1": 0.9117,
      "variance_drift_pct": 1.35875,
      "ppl": 2.341
    }
  },
  "conditions": {
    "no_reg": {
      "f1": 0.9117,
      "variance_drift_pct": 13.0525
    },
    "ov_freeze_full": {
      "f1": 0.9117,
      "variance_drift_pct": 0.3126953125
    },
    "ov_freeze_half": {
      "f1": 0.9117,
      "variance_drift_pct": 6.696875
    },
    "ov_freeze_quarter": {
      "f1": 0.9117,
      "variance_drift_pct": 9.779375
    }
  }
}
```

### exp4 — `exp4_20260715_031159.json`

```json
{
  "experiment": "exp4",
  "computation": "h100_real_qwen",
  "classifiers": {
    "logreg": {
      "f1": 0.932,
      "accuracy": 0.9313
    },
    "xgb": {
      "f1": 0.9017,
      "accuracy": 0.8938
    },
    "mlp": {
      "f1": 0.9494,
      "accuracy": 0.95
    },
    "qwen_base": {
      "f1": 0.9184,
      "accuracy": 0.9163
    }
  }
}
```

### exp5 — `exp5_20260723_160535.json`

```json
{
  "experiment": "exp5",
  "computation": "smoke_sklearn",
  "taf28k": {
    "f1": 0.8462,
    "accuracy": 0.8333
  },
  "cross_taf_on_chifraud": {
    "f1": 0.4255
  },
  "cross_chifraud_on_taf": {
    "f1": 0.6667
  },
  "advfraud": {
    "full_pool": {
      "f1": 1.0,
      "accuracy": 1.0
    }
  },
  "ldp_tradeoff": {
    "no_ldp": {
      "epsilon": Infinity,
      "f1": 0.8462
    },
    "eps_0.5": {
      "epsilon": 0.5,
      "f1": 0.6667
    },
    "eps_1.0": {
      "epsilon": 1.0,
      "f1": 0.6667
    },
    "eps_1.5": {
      "epsilon": 1.5,
      "f1": 0.6667
    },
    "eps_3.0": {
      "epsilon": 3.0,
      "f1": 0.6667
    }
  },
  "strict_evaluation": {
    "time_split": {
      "n_test": 800,
      "fraud_ratio": 0.4975,
      "mode": "index_proxy",
      "accuracy": 0.9708,
      "f1": 0.9689,
      "precision": 0.9561,
      "recall": 0.982,
      "fpr": 0.0388,
      "auc": null
    },
    "source_split": {
      "n_test": 889,
      "fraud_ratio": 1.0,
      "mode": "heldout_source",
      "accuracy": 0.9963,
      "f1": 0.9981,
      "precision": 1.0,
      "recall": 0.9963,
      "fpr": 0.0,
      "auc": null,
      "heldout_source": "web_link",
      "source_counts": {
        "other": 1668,
        "web_link": 889,
        "finance": 44,
        "benign_daily": 1088,
        "social_im": 302,
        "gambling": 9
      }
    },
    "hard_set": {
      "n_test": 800,
      "fraud_ratio": 0.425,
      "mode": "uncertainty_mined",
      "accuracy": 1.0,
      "f1": 1.0,
      "precision": 1.0,
      "recall": 1.0,
      "fpr": 0.0,
      "auc": null
    },
    "template_hard_split": {
      "n_test": 800,
      "fraud_ratio": 0.4163,
      "mode": "template_group_holdout",
      "accuracy": 0.9875,
      "f1": 0.9767,
      "precision": 0.9545,
      "recall": 1.0,
      "fpr": 0.0169,
      "auc": null,
      "n_groups": 3816,
      "largest_group": 48
    }
  }
}
```

### exp6 — `exp6_20260715_031436.json`

```json
{
  "experiment": "exp6",
  "computation": "h100_real_qwen",
  "diagnostic_B": {
    "h100_measured": {
      "generic": 0.0
    },
    "h100_tokens": {
      "generic": 1.0
    },
    "v25_table8_alpha": {
      "generic": 0.85
    },
    "v25_table8_tokens": {
      "generic": 4.15
    },
    "verdict": "H100 measured generic alpha=0.0 differs from v25 paper reference 0.85 (diff=0.850); NOT MEASURED"
  }
}
```

### exp7 — `exp7_20260723_154706.json`

```json
{
  "experiment": "exp7",
  "computation": "h100_real_qwen",
  "embedding_source": "real_fv",
  "pii_report": {
    "total_texts": 4000,
    "pii_matches": {
      "email": 0,
      "phone": 101,
      "id_card": 3
    }
  },
  "asv_eer_pct": 43.2,
  "min_dcf": 0.05,
  "speaker_id_accuracy": 0.0909,
  "glo_reconstruction_corr": 0.3001,
  "n_speakers": 11
}
```

### exp8 — `exp8_20260715_031429.json`

```json
{
  "experiment": "exp8",
  "computation": "h100_real_qwen",
  "latencies": {
    "fp16": 1.481,
    "int8": 3.097,
    "int4": 2.276
  }
}
```

## Result File Index

| File | Size (KB) | Modified |
|------|-----------|----------|
| exp11_20260715_031234.json | 0.3 | 2026-07-15 11:15:31 |
| exp15_20260722_024452.json | 2.5 | 2026-07-22 10:44:52 |
| exp16_20260715_061945.json | 0.6 | 2026-07-15 14:20:26 |
| exp1_20260715_031133.json | 2.5 | 2026-07-15 11:15:34 |
| exp2_20260715_031258.json | 0.3 | 2026-07-15 11:15:30 |
| exp3_20260715_031422.json | 1.3 | 2026-07-15 11:15:30 |
| exp4_20260715_031159.json | 0.3 | 2026-07-15 11:15:33 |
| exp5_20260715_031441.json | 0.3 | 2026-07-15 11:15:27 |
| exp5_20260722_024446.json | 0.3 | 2026-07-22 10:44:46 |
| exp5_20260723_160535.json | 2.0 | 2026-07-23 16:05:35 |
| exp6_20260715_031436.json | 0.4 | 2026-07-15 11:15:28 |
| exp7_20260715_031444.json | 0.3 | 2026-07-15 11:15:26 |
| exp7_20260715_061932.json | 0.3 | 2026-07-15 14:20:27 |
| exp7_20260723_154706.json | 0.4 | 2026-07-23 15:47:06 |
| exp8_20260715_031429.json | 0.1 | 2026-07-15 11:15:29 |

---

## Aggregated metrics.json

```json
{
  "env": {
    "timestamp": "2026-07-30T05:04:34",
    "python": {
      "version": "3.12.3",
      "executable": "/usr/local/bin/python"
    },
    "os": {
      "system": "Linux",
      "release": "6.8.0-90-generic",
      "machine": "x86_64",
      "platform": "Linux-6.8.0-90-generic-x86_64-with-glibc2.39"
    },
    "cpu": {
      "processor": "x86_64",
      "count": 208
    },
    "torch": {
      "version": "2.8.0+cu128",
      "cuda_version": "12.8",
      "cudnn_version": "91002"
    },
    "gpu": {
      "cuda_available": true,
      "n_gpus": 1,
      "names": [
        "NVIDIA H100 80GB HBM3"
      ],
      "is_h100": true,
      "compute_capability": [
        [
          9,
          0
        ]
      ],
      "driver_version": "580.126.09",
      "nvidia_smi": "NVIDIA H100 80GB HBM3, 81559 MiB, 4 MiB, 0 %"
    },
    "distributed": {
      "nccl_available": true,
      "nccl_version": null
    },
    "optimizations": {
      "bf16_supported": true,
      "torch_compile_available": true,
      "flash_attn_available": false
    },
    "key_packages": {
      "transformers": "5.14.1",
      "accelerate": "1.14.0",
      "bitsandbytes": "0.50.0",
      "scikit-learn": "1.9.0",
      "numpy": "2.1.2",
      "matplotlib": "3.11.1"
    }
  },
  "groups": {
    "00_train": {
      "exp1": {
        "F1": 0.9925,
        "kl_final": 0.306483,
        "drift_pct_final": 158.079,
        "kl_plateau": 1.47977,
        "kl_converged": 0.367643,
        "total_steps": 2000,
        "ovf_step": 1400,
        "snr_min": 5.0,
        "snr_max": 5.6
      }
    },
    "01_baseline": {
      "exp4": {
        "F1[logreg]": 0.9342,
        "F1[xgb]": 0.8989,
        "F1[mlp]": 0.9488,
        "F1[qwen_base]": 0.912
      }
    },
    "02_quantization": {
      "exp11": {
        "F1[fp16]": 0.9573,
        "F1[int8]": 0.9573,
        "F1[int4]": 0.9573,
        "F1[nf4]": 0.9573
      }
    },
    "03_QAD": {
      "exp2": {
        "kl_final[kl_only]": 2.299364,
        "kl_final[mse_only]": 6.362068,
        "kl_final[ce_only]": 7.120353,
        "kl_final[kl_mse_combined]": 0.908714,
        "kl_final[kl_task]": 1.070668
      }
    },
    "04_OV-Freeze": {
      "exp3": {
        "drift[no_reg]": 158.079,
        "drift[ov_freeze_full]": 158.079,
        "drift[ov_freeze_half]": 158.079,
        "drift[ov_freeze_quarter]": 158.079
      }
    },
    "05_latency": {
      "exp8": {
        "lat_ms[bf16]": 13.396,
        "lat_ms[fp16]": 15.34,
        "lat_ms[int4]": 35.064,
        "lat_ms[int8]": 1311.057,
        "batch_benchmark": {
          "1": {
            "latency_p50_ms": 16.02,
            "throughput_sps": 62.4,
            "peak_mem_mb": 1174.2
          },
          "8": {
            "latency_p50_ms": 18.51,
            "throughput_sps": 432.2,
            "peak_mem_mb": 923.3
          },
          "32": {
            "latency_p50_ms": 19.2,
            "throughput_sps": 1666.3,
            "peak_mem_mb": 1465.4
          },
          "64": {
            "latency_p50_ms": 19.85,
            "throughput_sps": 3224.2,
            "peak_mem_mb": 2195.8
          }
        }
      },
      "exp6": {
        "alpha_generic": 0.3852,
        "alpha_domain": 0.86,
        "ref_alpha_generic": 0.78,
        "ref_alpha_tuned": 0.86
      }
    },
    "06_robustness": {
      "exp5": {
        "taf28k": 0.6744,
        "chifraud": 0.2387,
        "advfraud": 0.6795,
        "advfraud_curated": 0.6641,
        "cross_taf->chi": 0.2474,
        "cross_chi->taf": 0.6667,
        "bf16_matched": 0.882
      },
      "exp7": {
        "speaker_id_acc": 0.0909,
        "asv_eer_pct": 43.2
      }
    }
  },
  "benchmark": {
    "best_batch_size": 32,
    "throughput_sps": 1655.04,
    "latency_p50_ms": 16.884,
    "latency_p90_ms": 17.039,
    "latency_p99_ms": 18.277,
    "peak_mem_mb": 602.3,
    "gpu_util_pct": 26.7,
    "gpu_power_w": 153.6,
    "energy_j": 297.0,
    "wall_s": 1.933,
    "cuda_graph": false,
    "device": "cuda",
    "all_batch_sizes": {
      "1": {
        "throughput_sps": 64.36,
        "latency_p50_ms": 12.971,
        "latency_p90_ms": 13.233,
        "latency_p99_ms": 14.961,
        "peak_mem_mb": 543.2,
        "gpu_util_pct": 31.8,
        "gpu_power_w": 130.6,
        "energy_j": 202.9,
        "wall_s": 1.554,
        "cuda_graph": false,
        "device": "cuda"
      },
      "8": {
        "throughput_sps": 412.34,
        "latency_p50_ms": 16.934,
        "latency_p90_ms": 17.21,
        "latency_p99_ms": 19.044,
        "peak_mem_mb": 556.5,
        "gpu_util_pct": 31.4,
        "gpu_power_w": 139.6,
        "energy_j": 270.9,
        "wall_s": 1.94,
        "cuda_graph": false,
        "device": "cuda"
      },
      "32": {
        "throughput_sps": 1655.04,
        "latency_p50_ms": 16.884,
        "latency_p90_ms": 17.039,
        "latency_p99_ms": 18.277,
        "peak_mem_mb": 602.3,
        "gpu_util_pct": 26.7,
        "gpu_power_w": 153.6,
        "energy_j": 297.0,
        "wall_s": 1.933,
        "cuda_graph": false,
        "device": "cuda"
      }
    }
  }
}
```

## Summary CSV (outputs/metrics/summary.csv)

| experiment | computation | metric | value |
|---|---|---|---|
| exp1 | h100_real_qwen | trajectory_len | 30 |
| exp1 | h100_real_qwen | f1 | 0.9987 |
| exp1 | h100_real_qwen | accuracy | 0.9988 |
| exp1 | h100_real_qwen | n_train | 2880 |
| exp1 | h100_real_qwen | n_test | 800 |
| exp1 | h100_real_qwen | best_epoch | 28 |
| exp1 | h100_real_qwen | best_val_ce | 4.4e-05 |
| exp11 | h100_real_qwen | schemes.fp32.f1 | 0.9937 |
| exp11 | h100_real_qwen | schemes.fp32.accuracy | 0.9938 |
| exp11 | h100_real_qwen | schemes.fp16.f1 | 0.9937 |
| exp11 | h100_real_qwen | schemes.fp16.accuracy | 0.9938 |
| exp11 | h100_real_qwen | schemes.bf16.f1 | 0.995 |
| exp11 | h100_real_qwen | schemes.bf16.accuracy | 0.995 |
| exp15 | h100_hybrid_audio | audio_only.f1 | 0.9695 |
| exp15 | h100_hybrid_audio | audio_only.accuracy | 0.97 |
| exp15 | h100_hybrid_audio | audio_only.latency_ms_per_sample | 0.01653 |
| exp15 | h100_hybrid_audio | audio_only.classifier | MLP(128,32)+Calibrated |
| exp15 | h100_hybrid_audio | audio_only.n_params | 0 |
| exp15 | h100_hybrid_audio | text_only.f1 | 0.6667 |
| exp15 | h100_hybrid_audio | text_only.accuracy | 0.5 |
| exp15 | h100_hybrid_audio | text_only.latency_ms_per_sample | 20.0 |
| exp15 | h100_hybrid_audio | text_only.classifier | Qwen2.5-0.5B (base, zero-shot) |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.5.f1 | 0.9695 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.5.accuracy | 0.97 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.5.coverage_pct | 100.0 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.5.n_fast | 400 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.5.n_slow | 0 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.5.avg_latency_ms | 0.0165 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.5.speedup_vs_text_only | 1210.0 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.6.f1 | 0.98 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.6.accuracy | 0.98 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.6.coverage_pct | 98.2 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.6.n_fast | 393 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.6.n_slow | 7 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.6.avg_latency_ms | 0.3665 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.6.speedup_vs_text_only | 54.6 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.7.f1 | 0.9825 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.7.accuracy | 0.9825 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.7.coverage_pct | 96.5 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.7.n_fast | 386 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.7.n_slow | 14 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.7.avg_latency_ms | 0.7165 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.7.speedup_vs_text_only | 27.9 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.75.f1 | 0.9825 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.75.accuracy | 0.9825 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.75.coverage_pct | 96.0 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.75.n_fast | 384 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.75.n_slow | 16 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.75.avg_latency_ms | 0.8165 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.75.speedup_vs_text_only | 24.5 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.8.f1 | 0.9825 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.8.accuracy | 0.9825 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.8.coverage_pct | 96.0 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.8.n_fast | 384 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.8.n_slow | 16 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.8.avg_latency_ms | 0.8165 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.8.speedup_vs_text_only | 24.5 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.85.f1 | 0.9778 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.85.accuracy | 0.9775 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.85.coverage_pct | 93.5 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.85.n_fast | 374 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.85.n_slow | 26 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.85.avg_latency_ms | 1.3165 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.85.speedup_vs_text_only | 15.2 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.9.f1 | 0.9682 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.9.accuracy | 0.9675 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.9.coverage_pct | 92.2 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.9.n_fast | 369 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.9.n_slow | 31 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.9.avg_latency_ms | 1.5665 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.9.speedup_vs_text_only | 12.8 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.95.f1 | 0.9567 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.95.accuracy | 0.955 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.95.coverage_pct | 89.2 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.95.n_fast | 357 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.95.n_slow | 43 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.95.avg_latency_ms | 2.1665 |
| exp15 | h100_hybrid_audio | hybrid_sweep.thresh_0.95.speedup_vs_text_only | 9.2 |
| exp15 | h100_hybrid_audio | optimal.threshold | thresh_0.5 |
| exp15 | h100_hybrid_audio | optimal.f1 | 0.9695 |
| exp15 | h100_hybrid_audio | optimal.avg_latency_ms | 0.0165 |
| exp15 | h100_hybrid_audio | optimal.speedup_vs_text_only | 1210.0 |
| exp15 | h100_hybrid_audio | architecture.fast_path | MLP(512→128→32→2) on audio embeddings, ~0.1ms CPU |
| exp15 | h100_hybrid_audio | architecture.slow_path | Qwen2.5-0.5B zero-shot text classification, ~20ms GPU |
| exp15 | h100_hybrid_audio | architecture.gate | Confidence threshold on audio classifier softmax output |
| exp15 | h100_hybrid_audio | architecture.production_estimate | 60-80% samples fast path → 5-13ms avg latency |
| exp16 | h100_audio_encoders | encoders.logreg.f1 | 0.9774 |
| exp16 | h100_audio_encoders | encoders.logreg.accuracy | 0.9775 |
| exp16 | h100_audio_encoders | encoders.logreg.latency_ms | 0.000587 |
| exp16 | h100_audio_encoders | encoders.logreg.n_params | 1025 |
| exp16 | h100_audio_encoders | encoders.mlp_small(64).f1 | 0.9848 |
| exp16 | h100_audio_encoders | encoders.mlp_small(64).accuracy | 0.985 |
| exp16 | h100_audio_encoders | encoders.mlp_small(64).latency_ms | 0.003751 |
| exp16 | h100_audio_encoders | encoders.mlp_medium(128,32).f1 | 0.9645 |
| exp16 | h100_audio_encoders | encoders.mlp_medium(128,32).accuracy | 0.965 |
| exp16 | h100_audio_encoders | encoders.mlp_medium(128,32).latency_ms | 0.001883 |
| exp16 | h100_audio_encoders | encoders.svm_rbf.f1 | 0.9435 |
| exp16 | h100_audio_encoders | encoders.svm_rbf.accuracy | 0.9425 |
| exp16 | h100_audio_encoders | encoders.svm_rbf.latency_ms | 0.2386 |
| exp16 | h100_audio_encoders | encoders.svm_rbf.note | trained on 2000 subsample |
| exp16 | h100_audio_encoders | pareto_best | mlp_small(64) |
| exp16 | h100_audio_encoders | n_train | 4000 |
| exp16 | h100_audio_encoders | n_test | 400 |
| exp2 | h100_real_qwen | variants.kl_only.f1 | 0.9117 |
| exp2 | h100_real_qwen | variants.kl_only.kl_final | 0.8505190670490265 |
| exp2 | h100_real_qwen | variants.mse_only.f1 | 0.9117 |
| exp2 | h100_real_qwen | variants.mse_only.kl_final | 1.644385335445404 |
| exp2 | h100_real_qwen | variants.kl_mse_combined.f1 | 0.9117 |
| exp2 | h100_real_qwen | variants.kl_mse_combined.kl_final | 2.4949043941497804 |
| exp3 | h100_real_qwen | layer_selection.early.f1 | 0.9117 |
| exp3 | h100_real_qwen | layer_selection.early.variance_drift_pct | 9.779375 |
| exp3 | h100_real_qwen | layer_selection.mid.f1 | 0.9117 |
| exp3 | h100_real_qwen | layer_selection.mid.variance_drift_pct | 6.696875 |
| exp3 | h100_real_qwen | layer_selection.late.f1 | 0.9117 |
| exp3 | h100_real_qwen | layer_selection.late.variance_drift_pct | 2.77875 |
| exp3 | h100_real_qwen | layer_selection.all.f1 | 0.9117 |
| exp3 | h100_real_qwen | layer_selection.all.variance_drift_pct | 0.3126953125 |
| exp3 | h100_real_qwen | rho_sweep.rho_0.1.f1 | 0.9117 |
| exp3 | h100_real_qwen | rho_sweep.rho_0.1.variance_drift_pct | 11.7 |
| exp3 | h100_real_qwen | rho_sweep.rho_0.1.ppl | 2.341 |
| exp3 | h100_real_qwen | rho_sweep.rho_0.3.f1 | 0.9117 |
| exp3 | h100_real_qwen | rho_sweep.rho_0.3.variance_drift_pct | 9.021875 |
| exp3 | h100_real_qwen | rho_sweep.rho_0.3.ppl | 2.341 |
| exp3 | h100_real_qwen | rho_sweep.rho_0.5.f1 | 0.9117 |
| exp3 | h100_real_qwen | rho_sweep.rho_0.5.variance_drift_pct | 6.469375 |
| exp3 | h100_real_qwen | rho_sweep.rho_0.5.ppl | 2.341 |
| exp3 | h100_real_qwen | rho_sweep.rho_0.7.f1 | 0.9117 |
| exp3 | h100_real_qwen | rho_sweep.rho_0.7.variance_drift_pct | 3.8528125 |
| exp3 | h100_real_qwen | rho_sweep.rho_0.7.ppl | 2.341 |
| exp3 | h100_real_qwen | rho_sweep.rho_0.9.f1 | 0.9117 |
| exp3 | h100_real_qwen | rho_sweep.rho_0.9.variance_drift_pct | 1.35875 |
| exp3 | h100_real_qwen | rho_sweep.rho_0.9.ppl | 2.341 |
| exp3 | h100_real_qwen | conditions.no_reg.f1 | 0.9117 |
| exp3 | h100_real_qwen | conditions.no_reg.variance_drift_pct | 13.0525 |
| exp3 | h100_real_qwen | conditions.ov_freeze_full.f1 | 0.9117 |
| exp3 | h100_real_qwen | conditions.ov_freeze_full.variance_drift_pct | 0.3126953125 |
| exp3 | h100_real_qwen | conditions.ov_freeze_half.f1 | 0.9117 |
| exp3 | h100_real_qwen | conditions.ov_freeze_half.variance_drift_pct | 6.696875 |
| exp3 | h100_real_qwen | conditions.ov_freeze_quarter.f1 | 0.9117 |
| exp3 | h100_real_qwen | conditions.ov_freeze_quarter.variance_drift_pct | 9.779375 |
| exp4 | h100_real_qwen | classifiers.logreg.f1 | 0.932 |
| exp4 | h100_real_qwen | classifiers.logreg.accuracy | 0.9313 |
| exp4 | h100_real_qwen | classifiers.xgb.f1 | 0.9017 |
| exp4 | h100_real_qwen | classifiers.xgb.accuracy | 0.8938 |
| exp4 | h100_real_qwen | classifiers.mlp.f1 | 0.9494 |
| exp4 | h100_real_qwen | classifiers.mlp.accuracy | 0.95 |
| exp4 | h100_real_qwen | classifiers.qwen_base.f1 | 0.9184 |
| exp4 | h100_real_qwen | classifiers.qwen_base.accuracy | 0.9163 |
| exp5 | smoke_sklearn | taf28k.f1 | 0.8462 |
| exp5 | smoke_sklearn | taf28k.accuracy | 0.8333 |
| exp5 | smoke_sklearn | cross_taf_on_chifraud.f1 | 0.4255 |
| exp5 | smoke_sklearn | cross_chifraud_on_taf.f1 | 0.6667 |
| exp5 | smoke_sklearn | advfraud.full_pool.f1 | 1.0 |
| exp5 | smoke_sklearn | advfraud.full_pool.accuracy | 1.0 |
| exp5 | smoke_sklearn | ldp_tradeoff.no_ldp.epsilon | inf |
| exp5 | smoke_sklearn | ldp_tradeoff.no_ldp.f1 | 0.8462 |
| exp5 | smoke_sklearn | ldp_tradeoff.eps_0.5.epsilon | 0.5 |
| exp5 | smoke_sklearn | ldp_tradeoff.eps_0.5.f1 | 0.6667 |
| exp5 | smoke_sklearn | ldp_tradeoff.eps_1.0.epsilon | 1.0 |
| exp5 | smoke_sklearn | ldp_tradeoff.eps_1.0.f1 | 0.6667 |
| exp5 | smoke_sklearn | ldp_tradeoff.eps_1.5.epsilon | 1.5 |
| exp5 | smoke_sklearn | ldp_tradeoff.eps_1.5.f1 | 0.6667 |
| exp5 | smoke_sklearn | ldp_tradeoff.eps_3.0.epsilon | 3.0 |
| exp5 | smoke_sklearn | ldp_tradeoff.eps_3.0.f1 | 0.6667 |
| exp5 | smoke_sklearn | strict_evaluation.time_split.n_test | 800 |
| exp5 | smoke_sklearn | strict_evaluation.time_split.fraud_ratio | 0.4975 |
| exp5 | smoke_sklearn | strict_evaluation.time_split.mode | index_proxy |
| exp5 | smoke_sklearn | strict_evaluation.time_split.accuracy | 0.9708 |
| exp5 | smoke_sklearn | strict_evaluation.time_split.f1 | 0.9689 |
| exp5 | smoke_sklearn | strict_evaluation.time_split.precision | 0.9561 |
| exp5 | smoke_sklearn | strict_evaluation.time_split.recall | 0.982 |
| exp5 | smoke_sklearn | strict_evaluation.time_split.fpr | 0.0388 |
| exp5 | smoke_sklearn | strict_evaluation.time_split.auc |  |
| exp5 | smoke_sklearn | strict_evaluation.source_split.n_test | 889 |
| exp5 | smoke_sklearn | strict_evaluation.source_split.fraud_ratio | 1.0 |
| exp5 | smoke_sklearn | strict_evaluation.source_split.mode | heldout_source |
| exp5 | smoke_sklearn | strict_evaluation.source_split.accuracy | 0.9963 |
| exp5 | smoke_sklearn | strict_evaluation.source_split.f1 | 0.9981 |
| exp5 | smoke_sklearn | strict_evaluation.source_split.precision | 1.0 |
| exp5 | smoke_sklearn | strict_evaluation.source_split.recall | 0.9963 |
| exp5 | smoke_sklearn | strict_evaluation.source_split.fpr | 0.0 |
| exp5 | smoke_sklearn | strict_evaluation.source_split.auc |  |
| exp5 | smoke_sklearn | strict_evaluation.source_split.heldout_source | web_link |
| exp5 | smoke_sklearn | strict_evaluation.source_split.source_counts.other | 1668 |
| exp5 | smoke_sklearn | strict_evaluation.source_split.source_counts.web_link | 889 |
| exp5 | smoke_sklearn | strict_evaluation.source_split.source_counts.finance | 44 |
| exp5 | smoke_sklearn | strict_evaluation.source_split.source_counts.benign_daily | 1088 |
| exp5 | smoke_sklearn | strict_evaluation.source_split.source_counts.social_im | 302 |
| exp5 | smoke_sklearn | strict_evaluation.source_split.source_counts.gambling | 9 |
| exp5 | smoke_sklearn | strict_evaluation.hard_set.n_test | 800 |
| exp5 | smoke_sklearn | strict_evaluation.hard_set.fraud_ratio | 0.425 |
| exp5 | smoke_sklearn | strict_evaluation.hard_set.mode | uncertainty_mined |
| exp5 | smoke_sklearn | strict_evaluation.hard_set.accuracy | 1.0 |
| exp5 | smoke_sklearn | strict_evaluation.hard_set.f1 | 1.0 |
| exp5 | smoke_sklearn | strict_evaluation.hard_set.precision | 1.0 |
| exp5 | smoke_sklearn | strict_evaluation.hard_set.recall | 1.0 |
| exp5 | smoke_sklearn | strict_evaluation.hard_set.fpr | 0.0 |
| exp5 | smoke_sklearn | strict_evaluation.hard_set.auc |  |
| exp5 | smoke_sklearn | strict_evaluation.template_hard_split.n_test | 800 |
| exp5 | smoke_sklearn | strict_evaluation.template_hard_split.fraud_ratio | 0.4163 |
| exp5 | smoke_sklearn | strict_evaluation.template_hard_split.mode | template_group_holdout |
| exp5 | smoke_sklearn | strict_evaluation.template_hard_split.accuracy | 0.9875 |
| exp5 | smoke_sklearn | strict_evaluation.template_hard_split.f1 | 0.9767 |
| exp5 | smoke_sklearn | strict_evaluation.template_hard_split.precision | 0.9545 |
| exp5 | smoke_sklearn | strict_evaluation.template_hard_split.recall | 1.0 |
| exp5 | smoke_sklearn | strict_evaluation.template_hard_split.fpr | 0.0169 |
| exp5 | smoke_sklearn | strict_evaluation.template_hard_split.auc |  |
| exp5 | smoke_sklearn | strict_evaluation.template_hard_split.n_groups | 3816 |
| exp5 | smoke_sklearn | strict_evaluation.template_hard_split.largest_group | 48 |
| exp6 | h100_real_qwen | diagnostic_B.h100_measured.generic | 0.0 |
| exp6 | h100_real_qwen | diagnostic_B.h100_tokens.generic | 1.0 |
| exp6 | h100_real_qwen | diagnostic_B.v25_table8_alpha.generic | 0.85 |
| exp6 | h100_real_qwen | diagnostic_B.v25_table8_tokens.generic | 4.15 |
| exp6 | h100_real_qwen | diagnostic_B.verdict | H100 measured generic alpha=0.0 differs from v25 paper reference 0.85 (diff=0.850); NOT MEASURED |
| exp7 | h100_real_qwen | embedding_source | real_fv |
| exp7 | h100_real_qwen | pii_report.total_texts | 4000 |
| exp7 | h100_real_qwen | pii_report.pii_matches.email | 0 |
| exp7 | h100_real_qwen | pii_report.pii_matches.phone | 101 |
| exp7 | h100_real_qwen | pii_report.pii_matches.id_card | 3 |
| exp7 | h100_real_qwen | asv_eer_pct | 43.2 |
| exp7 | h100_real_qwen | min_dcf | 0.05 |
| exp7 | h100_real_qwen | speaker_id_accuracy | 0.0909 |
| exp7 | h100_real_qwen | glo_reconstruction_corr | 0.3001 |
| exp7 | h100_real_qwen | n_speakers | 11 |
| exp8 | h100_real_qwen | latencies.fp16 | 1.481 |
| exp8 | h100_real_qwen | latencies.int8 | 3.097 |
| exp8 | h100_real_qwen | latencies.int4 | 2.276 |

## Latency CSV

| batch_size | p50_ms | p90_ms | p99_ms |
|---|---|---|---|
| 1 | 19.836 | 20.16 | 20.789 |
| 8 | 19.937 | 23.115 | 23.971 |
| 32 | 19.96 | 20.165 | 21.759 |

## Throughput CSV

| batch_size | samples_per_sec |
|---|---|
| 1 | 44.13 |
| 8 | 341.11 |
| 32 | 1411.6 |

## Memory CSV

| batch_size | peak_mem_mb |
|---|---|
| 1 | 1356.0 |
| 8 | 1362.3 |
| 32 | 1408.1 |

## Figures

- `figures\fig_latency_benchmark.pdf` (13.2 KB, 2026-07-30 16:13)
- `figures\fig_latency_benchmark.png` (21.4 KB, 2026-07-30 16:13)
