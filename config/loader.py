"""config/loader.py — 统一配置加载与合并。

所有模块应通过 ``from config import get_config`` 获取配置，而非直接读取 YAML。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from config.schema import ensure_valid_config
from realeval.io.serialization import load_config as _io_load_config


# 常用配置文件快捷路径
DEFAULT_CONFIG = Path(__file__).resolve().parent / "experiments.yaml"
H100_CONFIG = Path(__file__).resolve().parent / "h100.yaml"
RUNPOD_CONFIG = Path(__file__).resolve().parent / "runpod_h100.yaml"

# 进程内缓存
_cache: dict[str, dict[str, Any]] = {}


def load_config(path: str | Path | None = None, validate: bool = True) -> dict[str, Any]:
    """加载配置（不缓存），可选校验。

    Args:
        path: 覆盖层 YAML 路径；None 表示仅加载 ``experiments.yaml``。
        validate: 是否调用 schema 校验。

    Returns:
        合并后的配置字典。
    """
    cfg = _io_load_config(path)
    if validate:
        ensure_valid_config(cfg)
    return cfg


def get_config(path: str | Path | None = None, validate: bool = True) -> dict[str, Any]:
    """加载配置并缓存；重复调用返回同一对象。

    Args:
        path: 覆盖层 YAML 路径；None 表示默认基础配置。
        validate: 是否校验（仅首次加载时生效）。
    """
    key = str(Path(path).resolve()) if path else "__default__"
    if key not in _cache:
        _cache[key] = load_config(path, validate=validate)
    return _cache[key]


def clear_cache() -> None:
    """清除配置缓存（测试或配置文件变更后使用）。"""
    _cache.clear()
