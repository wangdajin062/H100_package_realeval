"""runner/registry.py — 实验注册表。

集中维护 15 个实验的模块名、短 ID 与描述，避免在 runner / paper_pipeline
/ CLI 中重复硬编码。
"""
from __future__ import annotations

from typing import NamedTuple


class ExperimentEntry(NamedTuple):
    module: str
    short: str
    description: str


EXPERIMENTS: list[ExperimentEntry] = [
    ExperimentEntry("exp1_qad_production", "exp1", "QAD Production (teacher->student KL distillation with OV-Freeze)"),
    ExperimentEntry("exp2_qad_loss_ablation", "exp2", "Loss Ablation (pure-KL / three-term / logits-MSE)"),
    ExperimentEntry("exp3_ov_freeze_control", "exp3", "OV-Freeze Control (4-condition + rho sweep)"),
    ExperimentEntry("exp4_baseline_comparison", "exp4", "Baseline Comparison (GBM / MLP / Logistic Regression)"),
    ExperimentEntry("exp5_cross_dataset", "exp5", "Cross-Dataset (TAF-28k / ChiFraud / AdvFraud-3k / LDP)"),
    ExperimentEntry("exp6_speculative_decoding", "exp6", "Speculative Decoding (alpha + diagnostic B)"),
    ExperimentEntry("exp7_privacy_verification", "exp7", "Privacy Verification (ASV-EER + GLO attack)"),
    ExperimentEntry("exp8_latency_benchmark", "exp8", "Latency Benchmark (end-to-end wall-clock)"),
    ExperimentEntry("exp9_cot_ablation", "exp9", "CoT Ablation (chain-of-thought vs direct)"),
    ExperimentEntry("exp10_teacher_scale", "exp10", "Teacher Scale (0.5B/1.5B/3B/7B)"),
    ExperimentEntry("exp11_quantization_scheme", "exp11", "Quantization Scheme (bf16 / fp16 / int8 / int4 / nf4 / nvfp4)"),
    ExperimentEntry("exp12_fraudfusion_baseline", "exp12", "FraudFusion Baseline (quantized competitor + storage decomposition)"),
    ExperimentEntry("exp13_fusion_strategy", "exp13", "Fusion Strategy (multimodal fusion ablation)"),
    ExperimentEntry("exp14_gguf_comparison", "exp14", "Multi-model same-data comparison (BF16 transformers vs Q4_K_M GGUF llama.cpp)"),
    ExperimentEntry("exp15_modality_ablation", "exp15", "Modality Ablation (text-only / audio-only / fused F1)"),
]

SHORT_TO_FULL: dict[str, str] = {e.short: e.module for e in EXPERIMENTS}
FULL_TO_SHORT: dict[str, str] = {e.module: e.short for e in EXPERIMENTS}
