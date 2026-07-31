#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gpu_viz.py — RunPod H100 GPU 实时可视化监控（rich 仪表盘）

通过一条 SSH 长连接拉取远端 nvidia-smi 数据流，本地渲染：
  - GPU 利用率 / 显存 / 功耗 / 温度 条形图
  - 历史趋势曲线（最近 ~90 帧）
  - GPU 计算进程表

用法: python gpu_viz.py    (Ctrl+C 退出)
依赖: pip install rich
"""
import os
import re
import subprocess
import sys
import time
from collections import deque

try:
    from rich.align import Align
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
except ImportError:
    sys.exit("需要 rich 库，先执行: pip install rich")

POD = "mhypfkvge474n8-64411fb1@ssh.runpod.io"
KEY = os.path.expanduser("~/.ssh/id_ed25519")
REFRESH = 1.0

# RunPod 代理忽略 ssh 命令参数，须经 stdin 管道喂命令。
# 远端循环每秒输出一帧（=F= 分隔），本地解析渲染。
REMOTE = (
    'while true; do echo "=F="; '
    'nvidia-smi --query-gpu=index,name,utilization.gpu,utilization.memory,memory.used,memory.total,power.draw,power.limit,temperature.gpu,clocks.sm,clocks.mem --format=csv,noheader,nounits; '
    'echo "=P="; '
    'nvidia-smi --query-compute-apps=pid,used_memory,process_name --format=csv,noheader; '
    'sleep %g; done' % REFRESH
)


def spark(values, width=60, lo=None, hi=None):
    """把最近值序列画成 ASCII 阶梯曲线"""
    if not values:
        return ""
    lo = lo if lo is not None else min(values)
    hi = hi if hi is not None else max(values)
    rng = (hi - lo) or 1.0
    glyphs = " _.-=+*#%@"
    step = max(1, len(values) // width)
    sampled = list(values)[::step][:width]
    return "".join(glyphs[min(9, max(0, int(round((v - lo) / rng * 9))))] for v in sampled)


def bar(frac, w=26):
    n = max(0, min(w, int(frac * w)))
    return "[" + "#" * n + "-" * (w - n) + "]"


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    once = "--once" in sys.argv
    console = Console()
    console.print("[cyan]连接 RunPod 拉取 GPU 数据…[/cyan]" + ("（快照模式）" if once else ""))
    proc = subprocess.Popen(
        ["ssh", "-tt", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20",
         "-o", "StrictHostKeyChecking=accept-new", "-o", "ServerAliveInterval=15",
         "-i", KEY, POD],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    try:
        proc.stdin.write((REMOTE + "\n").encode())
        proc.stdin.flush()
        proc.stdin.close()  # RunPod 代理需 stdin EOF 才开始转发执行
    except Exception as e:
        sys.exit("SSH 写入失败: %s" % e)

    hu, hv, hp, ht = deque(maxlen=90), deque(maxlen=90), deque(maxlen=90), deque(maxlen=90)

    def render(g, procs):
        try:
            idx, name, ug, _um, mu, mt, pw, pl, temp, smc, memc = [x.strip() for x in g]
            u = float(ug)
            mur = float(mu)
            mtr = float(mt)
            p = float(pw)
            plr = float(pl)
            t = float(temp)
        except Exception:
            return None
        hu.append(u)
        hv.append(mur)
        hp.append(p)
        ht.append(t)

        stats = Table.grid(padding=(0, 2))
        stats.add_column(justify="left", width=8)
        stats.add_column(justify="left", width=30)
        stats.add_column(justify="right", width=22)
        stats.add_row("Util", Text(bar(u / 100)), "%5.1f %%" % u)
        stats.add_row("VRAM", Text(bar(mur / mtr)), "%5.2f / %5.2f GB" % (mur / 1024, mtr / 1024))
        stats.add_row("Power", Text(bar(p / plr)), "%6.1f / %5.0f W" % (p, plr))
        stats.add_row("Temp", "", "%5.0f C" % t)
        stats.add_row("Clock", "", "SM %s / Mem %s MHz" % (smc, memc))
        gpu_panel = Panel(stats, title="[bold]%s[/bold]   [cyan]GPU %s[/cyan]" % (name, idx),
                          subtitle=time.strftime("%Y-%m-%d %H:%M:%S"))

        lines = []
        for label, d, lo, hi in (("Util % ", hu, 0, 100), ("VRAM GB", hv, 0, mtr / 1024),
                                 ("Power W ", hp, 0, plr), ("Temp C  ", ht, 20, 100)):
            lines.append(Text.from_markup("[bold]%s[/bold]  [cyan]%s[/cyan]" % (label, spark(d, 60, lo, hi))))
        curve_panel = Panel("\n".join(str(x) for x in lines), title="历史趋势（最近 %d 帧）" % len(hu))

        pt = Table(title="GPU 计算进程", box=None, header_style="bold cyan")
        pt.add_column("PID", justify="right", width=8, no_wrap=True)
        pt.add_column("显存 MiB", justify="right", width=10, no_wrap=True)
        pt.add_column("进程", overflow="fold")
        if not procs:
            pt.add_row("—", "—", "（无）")
        for pid, mem, pname in procs[:8]:
            pt.add_row(pid, mem, pname)

        grid = Table.grid(expand=True)
        grid.add_row(Align.center(gpu_panel))
        grid.add_row(Align.center(curve_panel))
        grid.add_row(pt)
        return grid

    def parse_and_render(frame):
        """解析一帧并更新界面；once 模式返回 True 表示已完成"""
        g = None
        procs = []
        for ln in frame:
            if g is None and "," in ln and re.match(r"^\d+,", ln):
                parts = [x.strip() for x in ln.split(",")]
                if len(parts) >= 11 and not parts[1].replace(" ", "").isdigit():
                    g = parts
                    continue
            m = re.match(r"^(\d+),\s*(\d+)\s*MiB,\s*(.*)$", ln)
            if m:
                procs.append((m.group(1), m.group(2), m.group(3)))
        if g and len(g) >= 11:
            r = render(g, procs)
            if r is not None:
                if once:
                    console.print(r)
                    return True
                live.update(r)
        return False

    def frame_loop(handle_frame):
        """逐行累积帧，遇到 =F= 分隔符交给 handle_frame"""
        frame = []
        while proc.poll() is None:
            line = proc.stdout.readline()
            if not line:
                break
            text = line.decode(errors="replace").strip()
            if text == "=F=":
                if frame and handle_frame(frame):
                    return
                frame = []
            elif text:
                frame.append(text)
        if frame:
            handle_frame(frame)

    try:
        if once:
            frame_loop(parse_and_render)
        else:
            with Live(console=console, refresh_per_second=2, screen=True) as live:
                frame_loop(parse_and_render)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            proc.terminate()
        except Exception:
            pass
        console.print("[dim]已退出[/dim]")


if __name__ == "__main__":
    main()
