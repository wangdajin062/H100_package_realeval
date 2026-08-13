"""cli/parser.py — 统一的命令行参数解析器。
"""
from __future__ import annotations

import argparse


def build_runner_parser() -> argparse.ArgumentParser:
    """构造 ``python -m experiments.runner`` 的参数解析器。"""
    parser = argparse.ArgumentParser(
        description="QAD-MultiGuard 实验运行器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python -m experiments.runner --paper          # 论文级运行（真实 Qwen + H100）
  python -m experiments.runner --exp 1,3,6      # 指定实验
  python -m experiments.runner --no-archive     # 跳过运行前归档
  python -m experiments.runner --check          # 硬件检查
  python -m experiments.runner --validate-contract  # 验证字段合约
        """,
    )
    parser.add_argument("experiments", nargs="?", default=None,
                        help="逗号分隔的实验名（如 exp1,exp4）或 'all'")
    parser.add_argument("--paper", action="store_true",
                        help="论文级运行（真实 Qwen + H100）")
    parser.add_argument("--exp", type=str, default=None,
                        help="逗号分隔的实验编号（如 1,3,6）")
    parser.add_argument("--config", type=str, default=None,
                        help="配置 YAML 路径")
    parser.add_argument("--check", action="store_true",
                        help="硬件检查")
    parser.add_argument("--storage-check", action="store_true",
                        help="存储挂载检查")
    parser.add_argument("--benchmark", action="store_true",
                        help="仅运行基准测试")
    parser.add_argument("--resume", action="store_true",
                        help="跳过已完成的实验")
    parser.add_argument("--no-archive", action="store_true",
                        help="跳过运行前的自动归档步骤")
    parser.add_argument("--report", action="store_true",
                        help="从已有结果生成论文表格/图像（不运行实验）")
    parser.add_argument("--validate-contract", action="store_true",
                        help="验证最新结果是否符合图像脚本字段合约")
    parser.add_argument("--align", action="store_true",
                        help="校验实验字段与图像脚本的对齐情况")
    return parser


def build_pipeline_parser() -> argparse.ArgumentParser:
    """构造 ``python -m experiments.paper_pipeline`` 的参数解析器。"""
    parser = argparse.ArgumentParser(description="一键式 H100 论文验证流水线")
    parser.add_argument("--paper", action="store_true",
                        help="论文级运行（真实 Qwen + H100）")
    parser.add_argument("--no-archive", action="store_true",
                        help="跳过运行前的自动归档步骤")
    parser.add_argument("--config", type=str, default=None,
                        help="配置 YAML 路径")
    return parser
