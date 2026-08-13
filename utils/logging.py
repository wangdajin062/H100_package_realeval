"""utils/logging.py — 统一日志工厂。

提供一次性的根日志配置与带实验上下文的 logger 工厂。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import ClassVar

from realeval.io.paths import LOGS


class _LoggingConfig:
    """内部单例，确保根日志只被配置一次。"""

    _configured: ClassVar[bool] = False
    _log_dir: ClassVar[Path | None] = None

    @classmethod
    def configure(cls, level: int = logging.INFO, log_dir: Path | None = None) -> None:
        """配置根 logger：控制台 + 文件双路输出。"""
        if cls._configured:
            return
        root = logging.getLogger()
        if root.handlers:
            # 如果外部已配置，则不再覆盖
            cls._configured = True
            return

        log_dir = log_dir or LOGS
        log_dir.mkdir(parents=True, exist_ok=True)
        cls._log_dir = log_dir

        formatter = logging.Formatter(
            "%(asctime)s [%(name)s] %(levelname)s %(message)s"
        )

        console = logging.StreamHandler()
        console.setFormatter(formatter)

        file_handler = logging.FileHandler(
            log_dir / "experiments.log", encoding="utf-8", mode="a"
        )
        file_handler.setFormatter(formatter)

        root.setLevel(level)
        root.addHandler(console)
        root.addHandler(file_handler)
        cls._configured = True


def configure_logging(level: int = logging.INFO, log_dir: Path | None = None) -> None:
    """一次性配置控制台 + 文件双路日志。"""
    _LoggingConfig.configure(level=level, log_dir=log_dir)


def get_logger(name: str, experiment_id: str | None = None) -> logging.Logger:
    """获取带可选实验前缀的 logger。

    Args:
        name: logger 名称（建议使用模块名）。
        experiment_id: 实验短 ID，如 "exp1"；提供时 logger 名称为 ``exp1:<name>``。
    """
    full_name = f"{experiment_id}:{name}" if experiment_id else name
    return logging.getLogger(full_name)
