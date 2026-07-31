"""config — 统一配置入口

提供全局唯一的配置加载、合并与访问接口。
其他模块应通过此包获取配置，而非直接操作 YAML 文件。

用法：
    from config import get_config, load_config

    # 使用默认路径（config/experiments.yaml）
    cfg = get_config()

    # 使用叠加配置（如 H100 硬件覆盖）
    cfg = get_config("config/h100.yaml")

    # 直接加载并返回（不缓存）
    cfg = load_config("config/h100.yaml")
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

# 配置根目录
_CONFIG_DIR = Path(__file__).resolve().parent

# 默认配置文件
DEFAULT_CONFIG   = _CONFIG_DIR / "experiments.yaml"
H100_CONFIG      = _CONFIG_DIR / "h100.yaml"
RUNPOD_CONFIG    = _CONFIG_DIR / "runpod_h100.yaml"

# ── 全局缓存（单进程内复用，避免重复 IO）────────────────────────────────────
_cache: dict[str, dict[str, Any]] = {}


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """加载并返回配置字典（不使用缓存，每次重新读取）。

    - 始终以 config/experiments.yaml 为基础配置；
    - 若 path 不同则深度合并覆盖层（仅需声明变更字段）；
    - 支持 REALEVAL_* 环境变量覆盖。
    """
    from realeval.io import load_config as _io_load
    return _io_load(str(path) if path is not None else None)


def get_config(path: str | Path | None = None) -> dict[str, Any]:
    """加载并返回配置字典（进程内缓存，重复调用直接返回）。

    缓存键为规范化后的文件路径字符串。
    """
    key = str(Path(path).resolve()) if path else "__default__"
    if key not in _cache:
        _cache[key] = load_config(path)
    return _cache[key]


def clear_cache() -> None:
    """清除配置缓存（测试时或配置文件变更后使用）。"""
    _cache.clear()


# ── 配置 Schema（字段名 → 描述，供文档与验证使用）────────────────────────────
CONFIG_SCHEMA: dict[str, str] = {
    # 模型路径
    "models.teacher":       "BF16 教师模型（Qwen2.5-0.5B-Instruct）",
    "models.student":       "量化学生模型（同构，同架构）",
    "models.draft_model":   "推测解码草稿模型（exp6）",
    "models.teacher_1.5b":  "1.5B 教师（exp10 消融）",
    "models.teacher_3b":    "3B 教师（exp10 消融）",
    "models.teacher_7b":    "7B 教师（exp10 消融 / SAFE-QAQ 基线）",
    "models.student_gguf":  "边缘部署 GGUF Q4_K_M 学生",
    # 数据配置
    "data.source":          "数据来源模式：auto / taf28k / synthetic",
    "data.dataset":         "主判别语料库名称",
    "data.max_samples":     "最大采样数（None = 全量）",
    # 训练超参
    "training.batch_size":        "批次大小",
    "training.learning_rate":     "学习率",
    "training.epochs":            "训练轮数",
    "training.apply_ov_rescaling":"启用 OV-Freeze 方差重缩放",
    "training.quantize":          "量化方案：fp16 / int8 / int4 / nf4",
    # 蒸馏参数
    "distillation.temperature":         "蒸馏温度（KL softmax 缩放）",
    "distillation.alpha_ce":            "CE loss 权重",
    "distillation.alpha_kl":            "KL loss 权重",
    "distillation.total_steps":         "概念步数空间（Fig4 对齐用，默认 2000）",
    "distillation.ovf_activation_ratio":"OV-Freeze 激活时机（默认 0.7，即后 30%）",
    # 硬件
    "hardware.use_flash_attn":    "启用 FlashAttention-2",
    "hardware.use_torch_compile": "启用 torch.compile",
    "hardware.ddp":               "多卡 DDP/NCCL",
    # 可复现性
    "reproducibility.seed":              "全局随机种子",
    "reproducibility.benchmark_warmup":  "基准测试预热轮数",
    "reproducibility.benchmark_repeat":  "基准测试重复轮数",
    # 隐私评估
    "privacy.delta":              "差分隐私 δ",
    "privacy.noise_multiplier":   "高斯噪声倍率",
    # 推测解码
    "speculative_decoding.gamma":     "草稿 token 数 γ（默认 5）",
    "speculative_decoding.n_samples": "采样次数",
}
