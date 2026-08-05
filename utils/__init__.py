"""utils — 跨包通用工具与横切关注点。

包含：
  - exceptions: 结构化异常体系
  - typing:     项目级类型别名
  - logging:    统一日志工厂
"""
from __future__ import annotations

from utils.exceptions import (
    AssetError,
    ConfigError,
    ContractError,
    RealEvalError,
)
from utils.logging import configure_logging, get_logger
from utils.typing import Config, ExperimentID, ResultDict

__all__ = [
    "RealEvalError",
    "ConfigError",
    "AssetError",
    "ContractError",
    "configure_logging",
    "get_logger",
    "Config",
    "ExperimentID",
    "ResultDict",
]
