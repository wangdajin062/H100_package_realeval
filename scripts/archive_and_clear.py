"""scripts/archive_and_clear.py — 归档实验结果并清理输出目录。

用法：
    python scripts/archive_and_clear.py              # 归档 + 清理
    python scripts/archive_and_clear.py --dry-run    # 仅预览，不写文件
    python scripts/archive_and_clear.py --archive-only  # 仅写 Markdown，不清理

实际实现已迁移至 ``io.archive``；本文件保留为命令行封装。
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

# 确保项目根目录在路径中，支持直接运行本脚本
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from realeval.io.archive import archive_if_needed, build_archive_markdown, clear_outputs

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("archive_and_clear")


def main() -> int:
    ap = argparse.ArgumentParser(description="归档实验结果 → Markdown，然后清理输出目录。")
    ap.add_argument("--dry-run", action="store_true", help="仅预览，不写入文件")
    ap.add_argument("--archive-only", action="store_true", help="仅写 Markdown，跳过清理")
    ap.add_argument("--force", action="store_true", help="即使无结果也强制执行")
    args = ap.parse_args()

    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date_tag = datetime.now().strftime("%Y-%m-%d_%H%M%S")

    # 步骤 1：构建并保存归档 Markdown
    log.info("正在构建归档 Markdown …")
    md = build_archive_markdown(date_str)

    from realeval.io.paths import ARCHIVE

    archive_path = ARCHIVE / f"{date_tag}_experiment_results.md"
    if not args.dry_run:
        ARCHIVE.mkdir(parents=True, exist_ok=True)
        archive_path.write_text(md, encoding="utf-8")
        log.info("归档已写入 → %s  (%d KB)", archive_path, len(md) // 1024)
    else:
        log.info("[dry-run] 将写入 → %s  (%d KB)", archive_path, len(md) // 1024)

    if args.archive_only:
        log.info("--archive-only：跳过清理步骤")
        return 0

    # 步骤 2：清理
    log.info("正在清理实验输出目录 …")
    deleted = clear_outputs(dry_run=args.dry_run)

    for p in deleted:
        mode = "[dry-run] 将删除" if args.dry_run else "已删除"
        log.info("  %s %s", mode, p)

    log.info("%s %d 个输出文件。",
             "[dry-run] 将删除" if args.dry_run else "已清理", len(deleted))

    if not args.dry_run:
        # 重建空占位目录
        from realeval.io.paths import FIGURES, METRICS_DIR, PREDICTIONS, RESULTS, TABLES_DIR
        for d in [RESULTS, PREDICTIONS, FIGURES, METRICS_DIR, TABLES_DIR]:
            d.mkdir(parents=True, exist_ok=True)
        log.info("输出目录已重置，可进行下一轮流水线运行。")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
