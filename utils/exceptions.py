"""utils/exceptions.py — 结构化异常体系。

所有项目内部异常均继承自 RealEvalError，便于 runner 统一捕获并生成
`{"computation": "failed", "error": ...}` 结果字典。
"""
from __future__ import annotations


class RealEvalError(RuntimeError):
    """项目根异常。"""


class ConfigError(RealEvalError):
    """配置加载、合并或校验失败。"""


class AssetError(RealEvalError):
    """模型、数据等真实资产不可用（H100 路径）。"""


class ContractError(RealEvalError):
    """实验结果不满足图像脚本字段合约。"""


class ExperimentRuntimeError(RealEvalError):
    """实验运行时失败（schema、显存、模型加载等）。"""
