"""config/defaults.py — 默认配置常量。

默认值与 ``config/experiments.yaml`` 保持一致，供 schema 校验与程序内回退使用。
"""
from __future__ import annotations

from typing import Any

DEFAULT_CONFIG_PATH = "config/experiments.yaml"

# 顶层配置默认值（与 experiments.yaml 同步）
DEFAULTS: dict[str, Any] = {
    "models": {
        "teacher": "Qwen/Qwen2.5-0.5B-Instruct",
        "student": "Qwen/Qwen2.5-0.5B-Instruct",
        "draft_model": "Qwen/Qwen2-0.5B",
        "teacher_1.5b": "Qwen/Qwen2.5-1.5B-Instruct",
        "teacher_3b": "Qwen/Qwen2.5-3B-Instruct",
        "teacher_7b": "Qwen/Qwen2.5-7B-Instruct",
        "student_gguf": "Qwen/Qwen2.5-0.5B-Instruct-GGUF",
    },
    "data": {
        "source": "auto",
        "dataset": "chifraud",
        "max_samples": 16000,
    },
    "training": {
        "batch_size": 64,
        "learning_rate": 5e-5,
        "epochs": 5,
        "apply_ov_rescaling": True,
        "quantize": "int4",
        "balance_class_weight": True,
        "val_frac": 0.15,
        "head_hidden": 128,
        "label_smoothing": 0.1,
        "warmup_steps": 100,
        "focal_gamma": 0.0,
        "threshold_grid_steps": 19,
        "dropout": 0.1,
    },
    "distillation": {
        "temperature": 2.0,
        "alpha_ce": 0.5,
        "alpha_kl": 0.5,
        "task_weight": 1e-3,
        "max_batch": 64,
        "max_seq_length": 256,
        "freeze_frac_default": 1.0,
        "window_default": 1.0,
        "total_steps": 2000,
        "ovf_activation_ratio": 0.7,
        "cot_max_new_tokens": 48,
    },
    "hardware": {
        "use_flash_attn": True,
        "use_torch_compile": False,
        "ddp": False,
    },
    "reproducibility": {
        "seed": 42,
        "benchmark_warmup": 10,
        "benchmark_repeat": 100,
        "benchmark_batch_sizes": [1, 8, 32, 64],
        "exp1_seeds": 5,
        "exp2_seeds": 5,
        "exp3_seeds": 5,
        "exp10_seeds": 5,
        "exp11_seeds": 5,
        "exp14_seeds": 5,
    },
    "privacy": {
        "delta": 1.0e-5,
        "sensitivity": 1.0,
        "noise_multiplier": 1.0,
        "clip_bound": 3.0,
        "open_set_enroll_utt": 3,
        "glo_attack_steps": 150,
        "glo_max_targets": 30,
        "speaker_id_hidden_layers": [256, 128],
        "speaker_id_max_iter": 300,
        "asv_thresholds": 400,
    },
    "speculative_decoding": {
        "gamma": 5,
        "n_samples": 20,
        "max_new_tokens": 40,
    },
    "classification": {
        "n_estimators": 100,
        "max_iter": 1000,
        "verification_n_features": 128,
        "verification_overlap": 0.9,
    },
    "inference": {
        "max_context": 2048,
        "max_tokens": 4,
        "cot_temperature": 0.0,
    },
    "synthetic": {
        "n_default": 200,
        "n_features": 128,
    },
    "audio": {
        "sample_rate": 16000,
        "mel_bins": 64,
        "hop_length": 160,
        "mfcc_dim": 64,
        "whisper_proj_dim": 64,
    },
    "students": {
        "qad_ovf": "/workspace/outputs/lora_manual/best",
    },
    "student_variant": "qad_ovf",
}
