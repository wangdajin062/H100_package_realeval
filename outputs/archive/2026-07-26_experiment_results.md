# Experiment Results Archive

**Generated:** 2026-07-26 20:14:52  
**Experiments archived:** ['exp1', 'exp10', 'exp11', 'exp2', 'exp3', 'exp4', 'exp5', 'exp6', 'exp7', 'exp8']  
**Total result files:** 22  

---

## Summary (latest result per experiment)

| Experiment | Computation | F1 (headline) |
|------------|-------------|---------------|
| exp1 | h100_real_qwen | 0.9988 |
| exp10 | smoke_sklearn | 1.0000 |
| exp11 | h100_real_qwen | 0.9988 |
| exp2 | smoke_sklearn | — |
| exp3 | smoke_sklearn | 1.0000 |
| exp4 | h100_real_qwen | 0.9342 |
| exp5 | smoke_sklearn | — |
| exp6 | h100_real_qwen | — |
| exp7 | h100_real_qwen | — |
| exp8 | smoke_cpu | — |

---

## Full Experiment Data

### exp1 — `exp1_20260723_085301.json`

```json
{
  "experiment": "exp1",
  "computation": "h100_real_qwen",
  "trajectory": [
    {
      "epoch": 0,
      "ce": 1.116292
    },
    {
      "epoch": 1,
      "ce": 0.010086
    },
    {
      "epoch": 2,
      "ce": 0.000929
    },
    {
      "epoch": 3,
      "ce": 0.004466
    },
    {
      "epoch": 4,
      "ce": 0.000692
    }
  ],
  "f1": 0.9988,
  "accuracy": 0.9988,
  "n_train": 3200,
  "n_test": 800,
  "is_synthetic": false
}
```

### exp10 — `exp10_20260726_172912.json`

```json
{
  "experiment": "exp10",
  "computation": "smoke_sklearn",
  "scales": {
    "teacher": {
      "f1": 1.0,
      "accuracy": 1.0
    },
    "teacher_1.5b": {
      "f1": 1.0,
      "accuracy": 1.0
    },
    "teacher_7b": {
      "f1": 1.0,
      "accuracy": 1.0
    }
  }
}
```

### exp11 — `exp11_20260723_085410.json`

```json
{
  "experiment": "exp11",
  "computation": "h100_real_qwen",
  "schemes": {
    "fp32": {
      "f1": 0.9988,
      "accuracy": 0.9988
    },
    "fp16": {
      "f1": 0.9988,
      "accuracy": 0.9988
    },
    "bf16": {
      "f1": 0.9988,
      "accuracy": 0.9988
    }
  }
}
```

### exp2 — `exp2_20260726_171854.json`

```json
{
  "experiment": "exp2",
  "computation": "smoke_sklearn",
  "variants": {
    "kl_only": {
      "f1": 1.0,
      "kl_final": 0.00082
    },
    "mse_only": {
      "f1": 1.0,
      "kl_final": 0.00135
    },
    "kl_mse_combined": {
      "f1": 1.0,
      "kl_final": 0.00058
    }
  }
}
```

### exp3 — `exp3_20260726_190912.json`

```json
{
  "experiment": "exp3",
  "computation": "smoke_sklearn",
  "layer_selection": {
    "none": {
      "f1": 1.0,
      "variance_drift_pct": 31.314
    },
    "early": {
      "f1": 1.0,
      "variance_drift_pct": 20.601
    },
    "mid": {
      "f1": 1.0,
      "variance_drift_pct": 24.545
    },
    "late": {
      "f1": 1.0,
      "variance_drift_pct": 4.816
    },
    "all": {
      "f1": 1.0,
      "variance_drift_pct": 3.978
    }
  },
  "rho_sweep": {
    "rho_0.0": {
      "f1": 1.0,
      "variance_drift_pct": 31.314,
      "ppl": 1.001
    },
    "rho_0.1": {
      "f1": 1.0,
      "variance_drift_pct": 7.335,
      "ppl": 1.005
    },
    "rho_0.2": {
      "f1": 1.0,
      "variance_drift_pct": 9.764,
      "ppl": 1.002
    },
    "rho_0.3": {
      "f1": 1.0,
      "variance_drift_pct": 4.689,
      "ppl": 1.002
    },
    "rho_0.4": {
      "f1": 1.0,
      "variance_drift_pct": 5.568,
      "ppl": 1.001
    },
    "rho_0.5": {
      "f1": 1.0,
      "variance_drift_pct": 3.978,
      "ppl": 1.001
    }
  },
  "conditions": {
    "no_reg": {
      "f1": 1.0,
      "variance_drift_pct": 31.314
    },
    "ov_freeze_full": {
      "f1": 1.0,
      "variance_drift_pct": 3.978
    },
    "ov_freeze_half": {
      "f1": 1.0,
      "variance_drift_pct": 15.564
    },
    "ov_freeze_quarter": {
      "f1": 1.0,
      "variance_drift_pct": 89.737
    }
  }
}
```

### exp4 — `exp4_20260723_085352.json`

```json
{
  "experiment": "exp4",
  "computation": "h100_real_qwen",
  "classifiers": {
    "logreg": {
      "f1": 0.9342,
      "accuracy": 0.9337
    },
    "xgb": {
      "f1": 0.8989,
      "accuracy": 0.89
    },
    "mlp": {
      "f1": 0.9488,
      "accuracy": 0.9487
    },
    "qwen_base": {
      "f1": 0.9175,
      "accuracy": 0.915
    }
  }
}
```

### exp5 — `exp5_20260726_172159.json`

```json
{
  "experiment": "exp5",
  "computation": "smoke_sklearn",
  "taf28k": {
    "f1": 0.9962,
    "accuracy": 0.9962
  },
  "balanced4k": {
    "f1": 0.9962,
    "accuracy": 0.9962
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
      "f1": 0.9962
    },
    "eps_0.5": {
      "epsilon": 0.5,
      "f1": 0.0
    },
    "eps_1.0": {
      "epsilon": 1.0,
      "f1": 0.0
    },
    "eps_1.5": {
      "epsilon": 1.5,
      "f1": 0.8412
    },
    "eps_3.0": {
      "epsilon": 3.0,
      "f1": 0.9602
    }
  }
}
```

### exp6 — `exp6_20260726_192104.json`

```json
{
  "experiment": "exp6",
  "computation": "h100_real_qwen",
  "diagnostic_B": {
    "h100_measured": {
      "generic": 0.4034,
      "domain": 0.4034
    },
    "h100_tokens": {
      "generic": 1.67
    },
    "v25_table8_alpha": {
      "generic": 0.85
    },
    "v25_table8_tokens": {
      "generic": 4.15
    },
    "verdict": "H100 measured generic alpha=0.4034 differs from v25 paper reference 0.85 (diff=0.447); NOT MEASURED"
  }
}
```

### exp7 — `exp7_20260723_085658.json`

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

### exp8 — `exp8_20260726_191818.json`

```json
{
  "experiment": "exp8",
  "computation": "smoke_cpu",
  "latencies": {
    "bf16": 3.0621,
    "fp16": 3.1074,
    "int8": 0.2193,
    "int4": 0.4373
  },
  "latency_detail": {
    "bf16": {
      "p50_ms": 3.0621,
      "p90_ms": 7.3169,
      "p99_ms": 7.8716
    },
    "fp16": {
      "p50_ms": 3.1074,
      "p90_ms": 5.6864,
      "p99_ms": 8.2868
    },
    "int8": {
      "p50_ms": 0.2193,
      "p90_ms": 0.3279,
      "p99_ms": 0.4252
    },
    "int4": {
      "p50_ms": 0.4373,
      "p90_ms": 1.6214,
      "p99_ms": 4.6966
    }
  }
}
```

## Result File Index

| File | Size (KB) | Modified |
|------|-----------|----------|
| exp10_20260726_172912.json | 0.3 | 2026-07-26 17:29:12 |
| exp11_20260723_085410.json | 0.3 | 2026-07-23 20:49:38 |
| exp1_20260723_085301.json | 0.4 | 2026-07-23 20:49:40 |
| exp2_20260723_085434.json | 0.3 | 2026-07-23 20:49:37 |
| exp2_20260726_171854.json | 0.3 | 2026-07-26 17:18:54 |
| exp3_20260723_085624.json | 1.3 | 2026-07-23 20:49:36 |
| exp3_20260726_171949.json | 1.4 | 2026-07-26 17:19:49 |
| exp3_20260726_190912.json | 1.4 | 2026-07-26 19:09:12 |
| exp4_20260723_085352.json | 0.3 | 2026-07-23 20:49:39 |
| exp5_20260723_085655.json | 0.3 | 2026-07-23 20:49:34 |
| exp5_20260726_172159.json | 0.7 | 2026-07-26 17:21:59 |
| exp6_20260723_085646.json | 0.4 | 2026-07-23 20:49:35 |
| exp6_20260723_091902.json | 0.4 | 2026-07-23 20:49:28 |
| exp6_20260723_092141.json | 0.4 | 2026-07-23 20:49:27 |
| exp6_20260723_101108.json | 0.4 | 2026-07-23 20:49:26 |
| exp6_20260723_101344.json | 0.4 | 2026-07-23 20:49:25 |
| exp6_20260726_172818.json | 0.4 | 2026-07-26 17:28:18 |
| exp6_20260726_192104.json | 0.5 | 2026-07-26 19:21:04 |
| exp7_20260723_085658.json | 0.3 | 2026-07-23 20:49:33 |
| exp8_20260723_085632.json | 0.1 | 2026-07-23 20:49:35 |
| exp8_20260726_172825.json | 0.5 | 2026-07-26 17:28:25 |
| exp8_20260726_191818.json | 0.6 | 2026-07-26 19:18:18 |

---

## Aggregated metrics.json

```json
{
  "env": {
    "timestamp": "2026-07-26T18:05:30",
    "source": "local_refresh_from_existing_results"
  },
  "groups": {
    "00_train": {
      "exp1": {
        "F1": 0.9988
      }
    },
    "01_baseline": {
      "exp4": {
        "F1[logreg]": 0.9342,
        "F1[xgb]": 0.8989,
        "F1[mlp]": 0.9488,
        "F1[qwen_base]": 0.9175
      }
    },
    "02_quantization": {
      "exp11": {
        "F1[fp32]": 0.9988,
        "F1[fp16]": 0.9988,
        "F1[bf16]": 0.9988,
        "F1[int4]": 0.9988
      }
    },
    "03_QAD": {
      "exp2": {
        "kl_final[kl_only]": 0.00082,
        "kl_final[mse_only]": 0.00135,
        "kl_final[kl_mse_combined]": 0.00058
      }
    },
    "04_OV-Freeze": {
      "exp3": {
        "drift[no_reg]": 31.314,
        "drift[ov_freeze_full]": 3.978,
        "drift[ov_freeze_half]": 15.564,
        "drift[ov_freeze_quarter]": 89.737
      }
    },
    "05_latency": {
      "exp8": {
        "lat_ms[int4]": 0.1613,
        "lat_ms[fp16]": 1.6263,
        "lat_ms[bf16]": 1.6654
      },
      "exp6": {
        "alpha_generic": 0.4034,
        "alpha_domain": 0.4034
      }
    },
    "06_robustness": {
      "exp5": {
        "taf28k": 0.9962,
        "advfraud": 1.0,
        "cross_taf->chi": 0.4255,
        "cross_chi->taf": 0.6667
      },
      "exp7": {
        "speaker_id_acc": 0.0909,
        "asv_eer_pct": 43.2
      }
    }
  }
}
```

## Summary CSV (outputs/metrics/summary.csv)

| experiment | computation | metric | value |
|---|---|---|---|
| exp1 | h100_real_qwen | f1 | 0.9988 |
| exp1 | h100_real_qwen | accuracy | 0.9988 |
| exp1 | h100_real_qwen | n_train | 3200 |
| exp1 | h100_real_qwen | n_test | 800 |
| exp10 | smoke_sklearn | scales.teacher.f1 | 1.0 |
| exp10 | smoke_sklearn | scales.teacher.accuracy | 1.0 |
| exp10 | smoke_sklearn | scales.teacher_1.5b.f1 | 1.0 |
| exp10 | smoke_sklearn | scales.teacher_1.5b.accuracy | 1.0 |
| exp10 | smoke_sklearn | scales.teacher_7b.f1 | 1.0 |
| exp10 | smoke_sklearn | scales.teacher_7b.accuracy | 1.0 |
| exp11 | h100_real_qwen | schemes.fp32.f1 | 0.9988 |
| exp11 | h100_real_qwen | schemes.fp32.accuracy | 0.9988 |
| exp11 | h100_real_qwen | schemes.fp16.f1 | 0.9988 |
| exp11 | h100_real_qwen | schemes.fp16.accuracy | 0.9988 |
| exp11 | h100_real_qwen | schemes.bf16.f1 | 0.9988 |
| exp11 | h100_real_qwen | schemes.bf16.accuracy | 0.9988 |
| exp2 | smoke_sklearn | variants.kl_only.f1 | 1.0 |
| exp2 | smoke_sklearn | variants.kl_only.kl_final | 0.00082 |
| exp2 | smoke_sklearn | variants.mse_only.f1 | 1.0 |
| exp2 | smoke_sklearn | variants.mse_only.kl_final | 0.00135 |
| exp2 | smoke_sklearn | variants.kl_mse_combined.f1 | 1.0 |
| exp2 | smoke_sklearn | variants.kl_mse_combined.kl_final | 0.00058 |
| exp3 | smoke_sklearn | layer_selection.none.f1 | 1.0 |
| exp3 | smoke_sklearn | layer_selection.none.variance_drift_pct | 31.314 |
| exp3 | smoke_sklearn | layer_selection.early.f1 | 1.0 |
| exp3 | smoke_sklearn | layer_selection.early.variance_drift_pct | 20.601 |
| exp3 | smoke_sklearn | layer_selection.mid.f1 | 1.0 |
| exp3 | smoke_sklearn | layer_selection.mid.variance_drift_pct | 24.545 |
| exp3 | smoke_sklearn | layer_selection.all.f1 | 1.0 |
| exp3 | smoke_sklearn | layer_selection.all.variance_drift_pct | 3.978 |
| exp3 | smoke_sklearn | rho_sweep.rho_0.0.f1 | 1.0 |
| exp3 | smoke_sklearn | rho_sweep.rho_0.0.variance_drift_pct | 31.314 |
| exp3 | smoke_sklearn | rho_sweep.rho_0.0.ppl | 1.001 |
| exp3 | smoke_sklearn | rho_sweep.rho_0.1.f1 | 1.0 |
| exp3 | smoke_sklearn | rho_sweep.rho_0.1.variance_drift_pct | 7.335 |
| exp3 | smoke_sklearn | rho_sweep.rho_0.1.ppl | 1.005 |
| exp3 | smoke_sklearn | rho_sweep.rho_0.2.f1 | 1.0 |
| exp3 | smoke_sklearn | rho_sweep.rho_0.2.variance_drift_pct | 9.764 |
| exp3 | smoke_sklearn | rho_sweep.rho_0.2.ppl | 1.002 |
| exp3 | smoke_sklearn | rho_sweep.rho_0.3.f1 | 1.0 |
| exp3 | smoke_sklearn | rho_sweep.rho_0.3.variance_drift_pct | 4.689 |
| exp3 | smoke_sklearn | rho_sweep.rho_0.3.ppl | 1.002 |
| exp3 | smoke_sklearn | rho_sweep.rho_0.4.f1 | 1.0 |
| exp3 | smoke_sklearn | rho_sweep.rho_0.4.variance_drift_pct | 5.568 |
| exp3 | smoke_sklearn | rho_sweep.rho_0.4.ppl | 1.001 |
| exp3 | smoke_sklearn | rho_sweep.rho_0.5.f1 | 1.0 |
| exp3 | smoke_sklearn | rho_sweep.rho_0.5.variance_drift_pct | 3.978 |
| exp3 | smoke_sklearn | rho_sweep.rho_0.5.ppl | 1.001 |
| exp3 | smoke_sklearn | conditions.no_reg.f1 | 1.0 |
| exp3 | smoke_sklearn | conditions.no_reg.variance_drift_pct | 31.314 |
| exp3 | smoke_sklearn | conditions.ov_freeze_full.f1 | 1.0 |
| exp3 | smoke_sklearn | conditions.ov_freeze_full.variance_drift_pct | 3.978 |
| exp3 | smoke_sklearn | conditions.ov_freeze_half.f1 | 1.0 |
| exp3 | smoke_sklearn | conditions.ov_freeze_half.variance_drift_pct | 15.564 |
| exp3 | smoke_sklearn | conditions.ov_freeze_quarter.f1 | 1.0 |
| exp3 | smoke_sklearn | conditions.ov_freeze_quarter.variance_drift_pct | 89.737 |
| exp4 | h100_real_qwen | classifiers.logreg.f1 | 0.9342 |
| exp4 | h100_real_qwen | classifiers.logreg.accuracy | 0.9337 |
| exp4 | h100_real_qwen | classifiers.xgb.f1 | 0.8989 |
| exp4 | h100_real_qwen | classifiers.xgb.accuracy | 0.89 |
| exp4 | h100_real_qwen | classifiers.mlp.f1 | 0.9488 |
| exp4 | h100_real_qwen | classifiers.mlp.accuracy | 0.9487 |
| exp4 | h100_real_qwen | classifiers.qwen_base.f1 | 0.9175 |
| exp4 | h100_real_qwen | classifiers.qwen_base.accuracy | 0.915 |
| exp5 | smoke_sklearn | taf28k.f1 | 0.9962 |
| exp5 | smoke_sklearn | taf28k.accuracy | 0.9962 |
| exp5 | smoke_sklearn | balanced4k.f1 | 0.9962 |
| exp5 | smoke_sklearn | balanced4k.accuracy | 0.9962 |
| exp5 | smoke_sklearn | cross_taf_on_chifraud.f1 | 0.4255 |
| exp5 | smoke_sklearn | cross_chifraud_on_taf.f1 | 0.6667 |
| exp5 | smoke_sklearn | advfraud.full_pool.f1 | 1.0 |
| exp5 | smoke_sklearn | advfraud.full_pool.accuracy | 1.0 |
| exp5 | smoke_sklearn | ldp_tradeoff.no_ldp.epsilon | inf |
| exp5 | smoke_sklearn | ldp_tradeoff.no_ldp.f1 | 0.9962 |
| exp5 | smoke_sklearn | ldp_tradeoff.eps_0.5.epsilon | 0.5 |
| exp5 | smoke_sklearn | ldp_tradeoff.eps_0.5.f1 | 0.0 |
| exp5 | smoke_sklearn | ldp_tradeoff.eps_1.0.epsilon | 1.0 |
| exp5 | smoke_sklearn | ldp_tradeoff.eps_1.0.f1 | 0.0 |
| exp5 | smoke_sklearn | ldp_tradeoff.eps_1.5.epsilon | 1.5 |
| exp5 | smoke_sklearn | ldp_tradeoff.eps_1.5.f1 | 0.8412 |
| exp5 | smoke_sklearn | ldp_tradeoff.eps_3.0.epsilon | 3.0 |
| exp5 | smoke_sklearn | ldp_tradeoff.eps_3.0.f1 | 0.9602 |
| exp6 | h100_real_qwen | diagnostic_B.h100_measured.generic | 0.4034 |
| exp6 | h100_real_qwen | diagnostic_B.h100_tokens.generic | 1.67 |
| exp6 | h100_real_qwen | diagnostic_B.v25_table8_alpha.generic | 0.85 |
| exp6 | h100_real_qwen | diagnostic_B.v25_table8_tokens.generic | 4.15 |
| exp6 | h100_real_qwen | diagnostic_B.verdict | H100 measured generic alpha=0.4034 differs from v25 paper reference 0.85 (diff=0.447); NOT MEASURED |
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
| exp8 | smoke_cpu | latencies.int4 | 0.1613 |
| exp8 | smoke_cpu | latencies.fp16 | 1.6263 |
| exp8 | smoke_cpu | latencies.bf16 | 1.6654 |
| exp8 | smoke_cpu | latency_detail.int4.p50_ms | 0.1613 |
| exp8 | smoke_cpu | latency_detail.int4.p90_ms | 0.3669 |
| exp8 | smoke_cpu | latency_detail.int4.p99_ms | 0.7839 |
| exp8 | smoke_cpu | latency_detail.fp16.p50_ms | 1.6263 |
| exp8 | smoke_cpu | latency_detail.fp16.p90_ms | 1.854 |
| exp8 | smoke_cpu | latency_detail.fp16.p99_ms | 2.1738 |
| exp8 | smoke_cpu | latency_detail.bf16.p50_ms | 1.6654 |
| exp8 | smoke_cpu | latency_detail.bf16.p90_ms | 2.2287 |
| exp8 | smoke_cpu | latency_detail.bf16.p99_ms | 2.7796 |
| metrics | ? | env.timestamp | 2026-07-23T08:48:25 |
| metrics | ? | env.python.version | 3.12.3 |
| metrics | ? | env.python.executable | /workspace/venv/bin/python |
| metrics | ? | env.os.system | Linux |
| metrics | ? | env.os.release | 6.8.0-90-generic |
| metrics | ? | env.os.machine | x86_64 |
| metrics | ? | env.os.platform | Linux-6.8.0-90-generic-x86_64-with-glibc2.39 |
| metrics | ? | env.cpu.processor | x86_64 |
| metrics | ? | env.cpu.count | 208 |
| metrics | ? | env.torch.version | 2.13.0+cu130 |
| metrics | ? | env.torch.cuda_version | 13.0 |
| metrics | ? | env.torch.cudnn_version | 92000 |
| metrics | ? | env.gpu.cuda_available | True |
| metrics | ? | env.gpu.n_gpus | 1 |
| metrics | ? | env.gpu.names[0] | NVIDIA H100 80GB HBM3 |
| metrics | ? | env.gpu.is_h100 | True |
| metrics | ? | env.gpu.driver_version | 580.126.09 |
| metrics | ? | env.gpu.nvidia_smi | NVIDIA H100 80GB HBM3, 81559 MiB, 4 MiB, 0 % |
| metrics | ? | env.distributed.nccl_available | True |
| metrics | ? | env.distributed.nccl_version |  |
| metrics | ? | env.optimizations.bf16_supported | True |
| metrics | ? | env.optimizations.torch_compile_available | True |
| metrics | ? | env.optimizations.flash_attn_available | False |
| metrics | ? | env.key_packages.transformers | 5.14.1 |
| metrics | ? | env.key_packages.accelerate | 1.14.0 |
| metrics | ? | env.key_packages.bitsandbytes | 0.49.2 |
| metrics | ? | env.key_packages.scikit-learn | 1.9.0 |
| metrics | ? | env.key_packages.numpy | 2.5.1 |
| metrics | ? | env.key_packages.matplotlib | 3.11.0 |
| metrics | ? | groups.00_train.exp1.F1 | 0.9988 |
| metrics | ? | groups.01_baseline.exp4.F1[logreg] | 0.9342 |
| metrics | ? | groups.01_baseline.exp4.F1[xgb] | 0.8989 |
| metrics | ? | groups.01_baseline.exp4.F1[mlp] | 0.9488 |
| metrics | ? | groups.01_baseline.exp4.F1[qwen_base] | 0.9175 |
| metrics | ? | groups.02_quantization.exp11.F1[fp32] | 0.9988 |
| metrics | ? | groups.02_quantization.exp11.F1[fp16] | 0.9988 |
| metrics | ? | groups.02_quantization.exp11.F1[bf16] | 0.9988 |
| metrics | ? | groups.03_QAD.exp2.kl_final[kl_only] | 0.8433875656127929 |
| metrics | ? | groups.03_QAD.exp2.kl_final[mse_only] | 1.6350166749954225 |
| metrics | ? | groups.03_QAD.exp2.kl_final[kl_mse_combined] | 2.478404235839844 |
| metrics | ? | groups.04_OV-Freeze.exp3.drift[no_reg] | 13.005 |
| metrics | ? | groups.04_OV-Freeze.exp3.drift[ov_freeze_full] | 0.311875 |
| metrics | ? | groups.04_OV-Freeze.exp3.drift[ov_freeze_half] | 6.660625 |
| metrics | ? | groups.04_OV-Freeze.exp3.drift[ov_freeze_quarter] | 9.7425 |
| metrics | ? | groups.05_latency.exp8.lat_ms[fp16] | 2.037 |
| metrics | ? | groups.05_latency.exp8.lat_ms[int8] | 3.727 |
| metrics | ? | groups.05_latency.exp8.lat_ms[int4] | 1.777 |
| metrics | ? | groups.05_latency.exp6.alpha_generic | 0.5508 |
| metrics | ? | groups.06_robustness.exp5.chifraud | 0.3546 |
| metrics | ? | groups.06_robustness.exp5.advfraud | 0.926 |
| metrics | ? | groups.06_robustness.exp7.speaker_id_acc | 0.0909 |
| metrics | ? | groups.06_robustness.exp7.asv_eer_pct | 43.2 |
| metrics | ? | benchmark.best_batch_size | 32 |
| metrics | ? | benchmark.throughput_sps | 1221.58 |
| metrics | ? | benchmark.latency_p50_ms | 23.556 |
| metrics | ? | benchmark.latency_p90_ms | 23.865 |
| metrics | ? | benchmark.latency_p99_ms | 24.159 |
| metrics | ? | benchmark.peak_mem_mb | 1005.2 |
| metrics | ? | benchmark.gpu_util_pct | 25.1 |
| metrics | ? | benchmark.gpu_power_w | 119.6 |
| metrics | ? | benchmark.energy_j | 313.3 |
| metrics | ? | benchmark.wall_s | 2.62 |
| metrics | ? | benchmark.cuda_graph | False |
| metrics | ? | benchmark.device | cuda |
| metrics | ? | benchmark.all_batch_sizes.1.throughput_sps | 37.8 |
| metrics | ? | benchmark.all_batch_sizes.1.latency_p50_ms | 23.729 |
| metrics | ? | benchmark.all_batch_sizes.1.latency_p90_ms | 24.036 |
| metrics | ? | benchmark.all_batch_sizes.1.latency_p99_ms | 24.248 |
| metrics | ? | benchmark.all_batch_sizes.1.peak_mem_mb | 953.1 |
| metrics | ? | benchmark.all_batch_sizes.1.gpu_util_pct | 21.1 |
| metrics | ? | benchmark.all_batch_sizes.1.gpu_power_w | 109.4 |
| metrics | ? | benchmark.all_batch_sizes.1.energy_j | 289.4 |
| metrics | ? | benchmark.all_batch_sizes.1.wall_s | 2.645 |
| metrics | ? | benchmark.all_batch_sizes.1.cuda_graph | False |
| metrics | ? | benchmark.all_batch_sizes.1.device | cuda |
| metrics | ? | benchmark.all_batch_sizes.8.throughput_sps | 303.11 |
| metrics | ? | benchmark.all_batch_sizes.8.latency_p50_ms | 23.637 |
| metrics | ? | benchmark.all_batch_sizes.8.latency_p90_ms | 23.917 |
| metrics | ? | benchmark.all_batch_sizes.8.latency_p99_ms | 26.1 |
| metrics | ? | benchmark.all_batch_sizes.8.peak_mem_mb | 959.5 |
| metrics | ? | benchmark.all_batch_sizes.8.gpu_util_pct | 23.0 |
| metrics | ? | benchmark.all_batch_sizes.8.gpu_power_w | 113.0 |
| metrics | ? | benchmark.all_batch_sizes.8.energy_j | 298.3 |
| metrics | ? | benchmark.all_batch_sizes.8.wall_s | 2.639 |
| metrics | ? | benchmark.all_batch_sizes.8.cuda_graph | False |
| metrics | ? | benchmark.all_batch_sizes.8.device | cuda |
| metrics | ? | benchmark.all_batch_sizes.32.throughput_sps | 1221.58 |
| metrics | ? | benchmark.all_batch_sizes.32.latency_p50_ms | 23.556 |
| metrics | ? | benchmark.all_batch_sizes.32.latency_p90_ms | 23.865 |
| metrics | ? | benchmark.all_batch_sizes.32.latency_p99_ms | 24.159 |
| metrics | ? | benchmark.all_batch_sizes.32.peak_mem_mb | 1005.2 |
| metrics | ? | benchmark.all_batch_sizes.32.gpu_util_pct | 25.1 |
| metrics | ? | benchmark.all_batch_sizes.32.gpu_power_w | 119.6 |
| metrics | ? | benchmark.all_batch_sizes.32.energy_j | 313.3 |
| metrics | ? | benchmark.all_batch_sizes.32.wall_s | 2.62 |
| metrics | ? | benchmark.all_batch_sizes.32.cuda_graph | False |
| metrics | ? | benchmark.all_batch_sizes.32.device | cuda |

## Latency CSV

| batch_size | p50_ms | p90_ms | p99_ms |
|---|---|---|---|
| 1 | 23.729 | 24.036 | 24.248 |
| 8 | 23.637 | 23.917 | 26.1 |
| 32 | 23.556 | 23.865 | 24.159 |

## Throughput CSV

| batch_size | samples_per_sec |
|---|---|
| 1 | 37.8 |
| 8 | 303.11 |
| 32 | 1221.58 |

## Memory CSV

| batch_size | peak_mem_mb |
|---|---|
| 1 | 953.1 |
| 8 | 959.5 |
| 32 | 1005.2 |

## Benchmark CSV

| batch_size | throughput_sps | latency_p50_ms | latency_p90_ms | latency_p99_ms | peak_mem_mb | gpu_util_pct | gpu_power_w | energy_j | wall_s | cuda_graph | device |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 37.8 | 23.729 | 24.036 | 24.248 | 953.1 | 21.1 | 109.4 | 289.4 | 2.645 | False | cuda |
| 8 | 303.11 | 23.637 | 23.917 | 26.1 | 959.5 | 23.0 | 113.0 | 298.3 | 2.639 | False | cuda |
| 32 | 1221.58 | 23.556 | 23.865 | 24.159 | 1005.2 | 25.1 | 119.6 | 313.3 | 2.62 | False | cuda |

## Figures

- `figures\fig_latency_benchmark.pdf` (12.2 KB, 2026-07-26 18:01)
- `figures\fig_latency_benchmark.png` (22.8 KB, 2026-07-26 18:01)
