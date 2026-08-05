"""cli — 命令行参数解析。

为 ``experiments.runner`` 与 ``experiments.paper_pipeline`` 提供统一的 argparse
构造器，避免参数定义分散在多个入口文件。
"""
from __future__ import annotations

from cli.parser import build_pipeline_parser, build_runner_parser

__all__ = ["build_runner_parser", "build_pipeline_parser"]
