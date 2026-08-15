"""config/schema.py — 配置 schema 定义与校验。

提供字段描述、类型约束、默认值及运行时校验函数。
"""
from __future__ import annotations

from typing import Any

from utils.exceptions import ConfigError


# 字段路径 -> (描述, 类型/取值约束, 是否必需)
CONFIG_SCHEMA: dict[str, tuple[str, type | tuple[type, ...], Any, bool]] = {
    # 模型路径
    "models.teacher":      ("BF16 教师模型", str, None, True),
    "models.student":      ("量化学生模型（同架构）", str, None, True),
    "models.draft_model":  ("推测解码草稿模型", str, None, False),
    "models.teacher_1.5b": ("1.5B 教师（exp10 消融）", str, None, False),
    "models.teacher_3b":   ("3B 教师（exp10 消融）", str, None, False),
    "models.teacher_7b":   ("7B 教师 / SAFE-QAQ 基线", str, None, False),
    "models.student_gguf": ("边缘部署 GGUF Q4_K_M 学生", str, None, False),

    # 数据配置
    "data.source":      ("数据来源模式：auto / taf28k / synthetic / chifraud", str, "auto", True),
    "data.dataset":     ("主判别语料库名称", str, "chifraud", True),
    "data.max_samples": ("最大采样数", (int, type(None)), 16000, False),

    # 训练超参
    "training.batch_size":             ("批次大小", int, 8, True),
    "training.learning_rate":          ("学习率", float, 1e-5, True),
    "training.epochs":                 ("训练轮数", int, 5, True),
    "training.apply_ov_rescaling":     ("启用 OV-Freeze", bool, True, False),
    "training.quantize":               ("量化方案：fp16 / int8 / int4 / nf4", str, "int4", True),
    "training.balance_class_weight":   ("是否按类别频率加权 CE", bool, True, False),
    "training.val_frac":               ("校准集比例", float, 0.15, False),
    "training.head_hidden":            ("分类头隐藏层维度", int, 128, False),
    "training.label_smoothing":        ("标签平滑", float, 0.1, False),
    "training.warmup_steps":           ("线性 warmup 步数", int, 100, False),
    "training.focal_gamma":            ("focal loss gamma（0=标准 CE）", float, 0.0, False),
    "training.threshold_grid_steps":   ("F1 阈值搜索网格步数", int, 19, False),
    "training.dropout":                ("分类头 dropout", float, 0.1, False),

    # 蒸馏参数
    "distillation.temperature":          ("蒸馏温度", float, 1.0, True),
    "distillation.alpha_ce":             ("CE loss 权重", float, 0.5, False),
    "distillation.alpha_kl":             ("KL loss 权重", float, 0.5, False),
    "distillation.task_weight":          ("分类头 loss 权重（head LR 系数）", float, 1e-3, False),
    "distillation.max_batch":            ("蒸馏最大批次", int, 8, False),
    "distillation.max_seq_length":       ("最大序列长度", int, 4096, False),
    "distillation.freeze_frac_default":  ("默认冻结比例", float, 1.0, False),
    "distillation.window_default":       ("默认窗口大小", float, 1.0, False),
    "distillation.total_steps":          ("概念步数空间（Fig4 对齐）", int, 2000, False),
    "distillation.ovf_activation_ratio": ("OV-Freeze 激活时机", float, 0.8, False),
    "distillation.ovf_rho":              ("OV-Freeze EMA 系数 ρ", float, 0.95, False),
    "distillation.ovf_lambda":           ("OV-Freeze 损失权重 λ", float, 0.01, False),
    "distillation.cot_max_new_tokens":   ("CoT 最大生成长度", int, 48, False),

    # 硬件
    "hardware.use_flash_attn":    ("启用 FlashAttention-2", bool, True, False),
    "hardware.use_torch_compile": ("启用 torch.compile", bool, False, False),
    "hardware.ddp":               ("多卡 DDP/NCCL", bool, False, False),

    # 可复现性
    "reproducibility.seed":                ("全局随机种子", int, 42, True),
    "reproducibility.benchmark_warmup":    ("基准测试预热轮数", int, 10, False),
    "reproducibility.benchmark_repeat":    ("基准测试重复轮数", int, 100, False),
    "reproducibility.benchmark_batch_sizes":("基准 batch 大小列表", list, [1, 8, 32, 64], False),
    "reproducibility.exp1_seeds":  ("exp1 多 seed 数", int, 5, False),
    "reproducibility.exp2_seeds":  ("exp2 多 seed 数", int, 5, False),
    "reproducibility.exp3_seeds":  ("exp3 多 seed 数", int, 5, False),
    "reproducibility.exp10_seeds": ("exp10 多 seed 数", int, 5, False),
    "reproducibility.exp11_seeds": ("exp11 多 seed 数", int, 5, False),
    "reproducibility.exp14_seeds": ("exp14 多 seed 数", int, 5, False),

    # 隐私评估
    "privacy.delta":                  ("差分隐私 δ", float, 1.0e-5, False),
    "privacy.sensitivity":            ("敏感度", float, 1.0, False),
    "privacy.noise_multiplier":       ("高斯噪声倍率", float, 1.0, False),
    "privacy.clip_bound":             ("梯度裁剪界", float, 3.0, False),
    "privacy.open_set_enroll_utt":    ("开放集注册 utterance 数", int, 3, False),
    "privacy.glo_attack_steps":       ("GLO 攻击步数", int, 150, False),
    "privacy.glo_max_targets":        ("GLO 最大目标数", int, 30, False),
    "privacy.speaker_id_hidden_layers":("说话人识别隐藏层", list, [256, 128], False),
    "privacy.speaker_id_max_iter":    ("说话人识别最大迭代", int, 300, False),
    "privacy.asv_thresholds":         ("ASV 阈值", int, 400, False),

    # 推测解码
    "speculative_decoding.gamma":      ("草稿 token 数 γ", int, 5, False),
    "speculative_decoding.n_samples":  ("采样次数", int, 20, False),
    "speculative_decoding.max_new_tokens": ("最大新 token 数", int, 40, False),

    # 分类
    "classification.n_estimators":        ("GBM 树数量", int, 100, False),
    "classification.max_iter":            ("MLP 最大迭代", int, 1000, False),
    "classification.verification_n_features": ("验证特征维度", int, 128, False),
    "classification.verification_overlap":    ("验证特征重叠度", float, 0.9, False),

    # 推理
    "inference.max_context":   ("最大上下文长度", int, 2048, False),
    "inference.max_tokens":    ("最大生成 token 数", int, 4, False),
    "inference.cot_temperature": ("CoT 采样温度", float, 0.0, False),

    # 合成数据
    "synthetic.n_default": ("默认合成样本数", int, 200, False),
    "synthetic.n_features":("合成特征维度", int, 128, False),

    # 音频
    "audio.sample_rate":      ("采样率", int, 16000, False),
    "audio.mel_bins":         ("mel 频带数", int, 64, False),
    "audio.hop_length":       ("hop 长度", int, 160, False),
    "audio.mfcc_dim":         ("MFCC 维度", int, 64, False),
    "audio.whisper_proj_dim": ("Whisper 投影维度", int, 64, False),

    # 学生模型路径
    "students":        ("LoRA/学生检查点路径表", dict, {}, False),
    "student_variant": ("要加载的学生变体", str, "qad_ovf", False),

    # 运行时覆盖（可由 REALEVAL_OUTPUT_ROOT 等环境变量注入）
    "output_root":     ("输出根目录", str, None, False),
}


def _get_path(config: dict[str, Any], dotted: str) -> Any:
    """按点号路径取值，缺失返回 ``_MISSING``。"""
    cur: Any = config
    for k in dotted.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return _MISSING
        cur = cur[k]
    return cur


_MISSING = object()


def validate_config(config: dict[str, Any]) -> list[str]:
    """校验配置并返回问题列表（空列表表示通过）。

    校验项：
      - 必需字段存在且非空；
      - 字段类型匹配；
      - 枚举字段取值合法。
    """
    issues: list[str] = []
    for path, (desc, expected, _default, required) in CONFIG_SCHEMA.items():
        value = _get_path(config, path)
        if value is _MISSING:
            if required:
                issues.append(f"缺少必需字段 {path} ({desc})")
            continue
        if value is None:
            if required:
                issues.append(f"{path} 不能为空 ({desc})")
            continue
        if not isinstance(value, expected):
            issues.append(f"{path} 类型错误：期望 {expected}，实际 {type(value).__name__}")

    # 枚举约束
    quantize = _get_path(config, "training.quantize")
    if quantize is not _MISSING and quantize not in ("fp16", "int8", "int4", "nf4", "bf16", None):
        issues.append(f"training.quantize 取值非法：{quantize}")

    data_source = _get_path(config, "data.source")
    if data_source is not _MISSING and data_source not in ("auto", "taf28k", "synthetic", "chifraud"):
        issues.append(f"data.source 取值非法：{data_source}")

    return issues


def _coerce_value(value: Any, expected: type | tuple[type, ...]) -> Any:
    """尝试将字符串数值转换为期望的数字类型。"""
    if not isinstance(value, str):
        return value
    if float in (expected if isinstance(expected, tuple) else (expected,)):
        try:
            return float(value)
        except ValueError:
            return value
    if int in (expected if isinstance(expected, tuple) else (expected,)):
        try:
            return int(value)
        except ValueError:
            return value
    return value


def coerce_config(config: dict[str, Any]) -> dict[str, Any]:
    """对配置中的数值字符串进行类型强制转换（原地修改并返回）。"""
    for path, (_desc, expected, _default, _required) in CONFIG_SCHEMA.items():
        keys = path.split(".")
        cur = config
        for k in keys[:-1]:
            if not isinstance(cur, dict) or k not in cur:
                break
            cur = cur[k]
        else:
            if isinstance(cur, dict) and keys[-1] in cur:
                cur[keys[-1]] = _coerce_value(cur[keys[-1]], expected)
    return config


def ensure_valid_config(config: dict[str, Any]) -> dict[str, Any]:
    """校验配置，失败时抛出 ConfigError。

    Returns:
        传入的配置字典（通过校验）。
    """
    coerce_config(config)
    issues = validate_config(config)
    if issues:
        raise ConfigError("配置校验失败：\n  - " + "\n  - ".join(issues))
    return config
