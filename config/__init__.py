"""config — 统一配置入口

提供全局唯一的配置加载、合并、校验与访问接口。
其他模块应通过此包获取配置，而非直接操作 YAML 文件。

用法：
    from config import get_config, load_config, validate_config

    # 使用默认路径（config/experiments.yaml）
    cfg = get_config()

    # 使用叠加配置（如 H100 硬件覆盖）
    cfg = get_config("config/h100.yaml")

    # 直接加载并返回（不缓存）
    cfg = load_config("config/h100.yaml")

    # 校验
    issues = validate_config(cfg)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from config.loader import (
    DEFAULT_CONFIG,
    H100_CONFIG,
    RUNPOD_CONFIG,
    clear_cache,
    get_config,
    load_config,
)
from config.schema import CONFIG_SCHEMA, ensure_valid_config, validate_config

__all__ = [
    "DEFAULT_CONFIG",
    "H100_CONFIG",
    "RUNPOD_CONFIG",
    "CONFIG_SCHEMA",
    "load_config",
    "get_config",
    "validate_config",
    "ensure_valid_config",
    "clear_cache",
]


# 保留旧位置常量以保持兼容
_CONFIG_DIR = Path(__file__).resolve().parent
