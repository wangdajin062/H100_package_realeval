#!/usr/bin/env python3
"""scripts/run_full_smoke.py — 运行完整冒烟套件并实时流式输出。

用法：
    python scripts/run_full_smoke.py
    python scripts/run_full_smoke.py --log-path outputs/logs/full_smoke_run.txt
    python scripts/run_full_smoke.py --no-log          # 仅终端，不写日志

日志默认写入 outputs/logs/full_smoke_run.txt（保持工作区根目录干净），
并在终端实时回显。退出码透传 runner 的返回码。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    default_log = repo_root / "outputs" / "logs" / "full_smoke_run.txt"

    ap = argparse.ArgumentParser(description="运行完整冒烟套件并实时流式输出")
    ap.add_argument("--log-path", type=Path, default=default_log,
                    help="日志输出路径（默认 outputs/logs/full_smoke_run.txt）")
    ap.add_argument("--no-log", action="store_true", help="仅终端输出，不写日志文件")
    args = ap.parse_args()

    os.chdir(repo_root)
    args.log_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [sys.executable, "-u", "-m", "experiments.runner", "--smoke", "--no-archive"]
    print(f"运行完整冒烟：{' '.join(cmd)}")
    print(f"日志写入：{args.log_path}\n", flush=True)

    if args.no_log:
        return subprocess.run(cmd).returncode

    with open(args.log_path, "w", encoding="utf-8") as log:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line, end="", flush=True)
            log.write(line)
            log.flush()
        return proc.wait()


if __name__ == "__main__":
    sys.exit(main())
