"""utils/typing.py — 项目级类型别名。

集中管理跨模块常用的复合类型，减少重复 import。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, TypeAlias

Config: TypeAlias = dict[str, Any]
ResultDict: TypeAlias = dict[str, Any]
ExperimentID: TypeAlias = str
PathLike: TypeAlias = str | Path
