# QAD-MultiGuard — H100 RealEval Suite

> **Last updated: 2026-07-26**  
> Package version: **4.2.0** · Python ≥ 3.10 · Tested on NVIDIA H100 80 GB HBM3

Real-computation evaluation suite for the **QAD-MultiGuard** paper.  
All 14 experiments produce paper-grade numbers from real Qwen weights on H100;
a smoke mode runs the complete code path on any CPU-only machine for rapid validation.

---

## Architecture

```
H100_package_realeval/
│
├── realeval/              # Core library (v4.2)
│   ├── data.py            # Dataset loaders: TAF-28k · ChiFraud · AdvFraud-3k · HF bucket
│   ├── real_backend.py    # H100 inference paths: distillation · classification · fusion
│   ├── models.py          # Qwen load + quant (BF16 / FP16 / INT4 / INT8 / NF4)
│   ├── specdec.py         # Speculative-decoding acceptance-rate diagnostics
│   ├── privacy.py         # ASV-EER · GLO attack · Gaussian LDP
│   ├── metrics.py         # F1 · accuracy · FPR · KL
│   ├── benchmark.py       # Forward-pass latency / throughput / GPU power
│   ├── report.py          # Export: summary CSV · LaTeX tables · PNG/PDF figures
│   ├── runner.py          # GPU benchmark runner (CUDA Graph · nvidia-smi sampling)
│   ├── student_loader.py  # LoRA adapter resolver & attach
│   ├── io.py              # Config loading (YAML + env override) · result persistence
│   ├── runlog.py          # Provenance recording (git SHA · config hash · seed)
│   ├── audit.py           # Audit log (GPU · CUDA · driver · dataset · model · seed)
│   ├── validation.py      # Whitelist-based input validation
│   ├── hwenv.py           # CUDA / BF16 / FlashAttn environment detection
│   ├── envreport.py       # Environment snapshot (JSON + Markdown)
│   ├── limits.py          # GPU memory fraction · concurrency lock
│   ├── paths.py           # Persistent-volume-aware path resolution (RunPod /workspace)
│   ├── distill.py         # KL-divergence utility
│   ├── statistics.py      # Bootstrap CI · t-test · effect size
│   └── distributed.py     # NCCL / DDP helpers
│
├── experiments/           # 14 paper experiments + orchestration
│   ├── framework.py       # Shared runtime: mode dispatch · data fallback · schema check
│   ├── runner.py          # CLI orchestrator (--smoke / --paper / --exp / --report)
│   ├── paper_pipeline.py  # One-command H100 pipeline (7-step)
│   ├── contract.py        # Paper-figure field-contract validator
│   ├── claim_engine.py    # YAML-claim → experiment → evidence → verdict engine
│   ├── exp1_qad_production.py     # QAD distillation (KL teacher→student + OV-Freeze)
│   ├── exp2_qad_loss_ablation.py  # Loss ablation: pure-KL / MSE / 3-term hybrid
│   ├── exp3_ov_freeze_control.py  # OV-Freeze: layer selection · rho sweep · conditions
│   ├── exp4_baseline_comparison.py# Classical baselines: LogReg · XGBoost · MLP
│   ├── exp5_cross_dataset.py      # Cross-dataset: TAF-28k · ChiFraud · AdvFraud-3k · LDP
│   ├── exp6_speculative_decoding.py# Speculative decoding: alpha measurement (H100)
│   ├── exp7_privacy_verification.py# Privacy: ASV-EER · speaker-ID · GLO attack
│   ├── exp8_latency_benchmark.py  # Latency: BF16 · FP16 · INT4 · INT8 (p50/p90/p99)
│   ├── exp9_cot_ablation.py       # Chain-of-thought vs direct classification
│   ├── exp10_teacher_scale.py     # Teacher scale: 0.5B · 1.5B · 7B
│   ├── exp11_quantization_scheme.py# Quant scheme: FP16 · INT8 · INT4 · NF4
│   ├── exp12_fraudfusion_baseline.py# FraudFusion competitor + storage decomposition
│   ├── exp13_fusion_strategy.py   # Multimodal fusion: early · late · hybrid
│   └── exp14_gguf_comparison.py   # BF16 transformers vs Q4_K_M GGUF (llama.cpp)
│
├── config/
│   ├── experiments.yaml   # Base config (models · data · training · distillation · hardware)
│   ├── h100.yaml          # H100 overlay (BF16 · FlashAttn2 · DDP)
│   └── runpod_h100.yaml   # RunPod deployment config
│
├── data/
│   ├── TAF28k/            # TeleAntiFraud-28k (JSONL + NPZ audio embeddings)
│   ├── ChiFraud/          # ChiFraud text classification corpus
│   ├── AdvFraud3k/        # 3 k adversarial fraud samples (8 perturbation strategies)
│   ├── balanced4k/        # Balanced train set (2 k fraud + 2 k normal)
│   └── spam11358/         # 11 k+ Chinese fraud SMS
│
├── outputs/
│   ├── results/           # Per-experiment JSON result files (timestamped)
│   ├── figures/           # PNG + PDF figures (report.py output)
│   ├── tables/            # tables.md · Table2.tex
│   ├── metrics/           # summary.csv · benchmark.csv
│   └── logs/              # runlog.jsonl · audit.log · experiments.log
│
├── cluster/               # Deployment: SLURM · RunPod · DDP launch scripts
├── tests/                 # pytest suite (unit + integration)
├── docs/
│   └── figure_scripts/    # Paper figure scripts (read-only; fed by paper_data.py bridge)
└── scripts/               # Sync and utility scripts
```

---

## Quick Start

```bash
# 1. Install (editable)
pip install -e ".[paper]"      # H100 / paper-grade dependencies
pip install -e ".[test]"       # test dependencies

# 2. Smoke test — any CPU machine, no weights needed
python -m experiments.runner --smoke

# 3. Hardware check
python -m experiments.runner --check

# 4. Validate field contract against existing results
python -m experiments.runner --validate-contract

# 5. Run specific experiments (smoke mode)
python -m experiments.runner --smoke --exp 1,3,6

# 6. Generate paper tables & figures from existing results
python -m experiments.runner --report
```

---

## H100 Paper Pipeline (one command)

```bash
bash run_h100.sh                          # paper-grade: real Qwen + H100
bash run_h100.sh --smoke                  # sandbox verification
python -m experiments.paper_pipeline --paper --config config/h100.yaml
```

**7-step pipeline:** CUDA check → GPU detect → env report → model load →
benchmark → metrics aggregate → save deliverables.

**Deliverables** in `outputs/results/`:

| File | Content |
|------|---------|
| `metrics.json` | Aggregated metrics for all experiment groups |
| `paper_table.md` | Ready-to-review paper table (Markdown) |
| `paper_tables/table1_main.tex` | Main result table (LaTeX) |
| `paper_tables/table2_ablation.tex` | OV-Freeze ablation table (LaTeX) |
| `paper_tables/table3_efficiency.tex` | Efficiency table (LaTeX) |

---

## Experiment Reference

| Exp | Name | Paper Figure / Table | Data |
|-----|------|---------------------|------|
| exp1 | QAD Production Distillation | Fig 4, Table 4 | balanced4k |
| exp2 | Loss Ablation (KL / MSE / hybrid) | Fig 5(a) | balanced4k |
| exp3 | OV-Freeze Control (layer · rho) | Fig 6 | balanced4k |
| exp4 | Baseline Comparison | Table 4 | balanced4k |
| exp5 | Cross-Dataset + LDP Trade-off | Table 5, Fig 8(c) | TAF-28k · ChiFraud · AdvFraud-3k |
| exp6 | Speculative Decoding α | Fig 7, Table 8 | balanced4k |
| exp7 | Privacy (ASV-EER · GLO) | Table 6 | ChiFraud NPZ |
| exp8 | Latency Benchmark (BF16/FP16/INT4/INT8) | Table 7 | balanced4k |
| exp9 | CoT Ablation | Appendix | balanced4k |
| exp10 | Teacher Scale (0.5B / 1.5B / 7B) | Fig 5(b) | balanced4k |
| exp11 | Quantization Scheme | Table 4 (QAT row) | balanced4k |
| exp12 | FraudFusion Baseline + Storage | Table 9 | balanced4k |
| exp13 | Fusion Strategy | Table 10 | TAF-28k multimodal |
| exp14 | BF16 vs Q4_K_M GGUF | Table 11 | balanced4k |

### Output Field Contract

Each experiment result JSON must expose the fields consumed by
`docs/figure_scripts/paper_data.py`. Validate with:

```bash
python -m experiments.runner --validate-contract
```

See [`docs/experiment_result_contract.md`](docs/experiment_result_contract.md) for the
full field specification.

---

## Configuration

Base config: `config/experiments.yaml` · H100 overlay: `config/h100.yaml`

### Key Sections

```yaml
models:
  teacher: Qwen/Qwen2.5-0.5B-Instruct    # BF16 teacher
  student: Qwen/Qwen2.5-0.5B-Instruct    # student to distil
  draft_model: Qwen/Qwen2-0.5B           # speculative decoding draft
  teacher_1.5b: Qwen/Qwen2.5-1.5B-Instruct
  teacher_7b: Qwen/Qwen2.5-7B-Instruct

data:
  source: auto          # auto | taf28k | synthetic
  max_samples: 4000

training:
  batch_size: 64
  learning_rate: 5e-5
  epochs: 5
  quantize: int4

distillation:
  temperature: 2.0
  alpha_kl: 0.5
  max_seq_length: 256
```

### Environment Variable Overrides

| Variable | Default | Description |
|----------|---------|-------------|
| `REALEVAL_DATA_ROOT` | `./data/` | Dataset root (auto-detects RunPod `/workspace/data`) |
| `REALEVAL_MODELS_ROOT` | `./models/` | Model weight root |
| `REALEVAL_ADAPTER_ROOT` | `/workspace/outputs/sft_checkpoints` | LoRA adapter path |
| `REALEVAL_OUTPUT_ROOT` | `./outputs/` | Output directory |
| `HF_HOME` | `.hf_cache/` | HuggingFace cache directory |

---

## Data Sources

| Dataset | Samples | Format | Purpose |
|---------|---------|--------|---------|
| **TAF-28k** | 28 k | JSONL + NPZ | Primary training & evaluation |
| **ChiFraud** | ~2 k | JSONL + NPZ | Cross-dataset transfer · privacy eval |
| **AdvFraud-3k** | 3 k | JSONL | Adversarial robustness (8 perturbation strategies) |
| **balanced4k** | 4 k | JSONL | Balanced train set (2 k fraud + 2 k normal) |
| **spam11358** | 11 k+ | JSONL | Fraud SMS diversity pool |

Data loading priority: local JSONL → local NPZ → HuggingFace bucket
(`wangdajin062/TeleAntiFraud-bucket`) → synthetic fallback.

---

## Cluster Deployment

```bash
# RunPod H100
bash cluster/setup_runpod.sh
bash cluster/launch_runpod_h100.sh

# SLURM
sbatch cluster/slurm_h100.sbatch

# Multi-GPU DDP (8× H100)
bash cluster/launch_ddp.sh
```

---

## Testing

```bash
pytest tests/ -v                        # full suite
pytest tests/test_hf_data.py -v        # HF dataset integration
pytest tests/test_realeval.py -v       # core library
pytest tests/test_integration.py -v   # end-to-end smoke
```

---

## Reproducibility

Every experiment run records:

- Git commit SHA + dirty flag
- Config SHA-256 hash
- Random seed
- Python / Torch / CUDA / driver versions
- GPU model

Records appended to `outputs/logs/runlog.jsonl` and `outputs/logs/audit.log`.

---

## License

MIT — see [LICENSE](LICENSE).
