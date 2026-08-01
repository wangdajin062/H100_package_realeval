#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gpu_viz.py — RunPod H100 GPU 实时可视化监控（rich 仪表盘）

通过一条 SSH 长连接拉取远端 nvidia-smi 数据流，本地渲染：
  - GPU 利用率 / 显存 / 功耗 / 温度 状态色条（绿=正常 黄=警戒 红=危险）
  - 历史趋势曲线（最近 ~90 帧，每指标独立强调色）
  - GPU 计算进程表

用法: python gpu_viz.py    (Ctrl+C 退出)
      python gpu_viz.py --once   (快照模式，打印一帧后退出)
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

# 状态阈值（占比 0~1）：< warn 正常 / warn~crit 警戒 / >= crit 危险
WARN, CRIT = 0.80, 0.95
# 温度阈值（°C），H100 满载典型 70~85°C
T_WARN, T_CRIT = 75.0, 85.0

# RunPod 代理忽略 ssh 命令参数，须经 stdin 管道喂命令。
# 远端循环每秒输出一帧（=F= 分隔），本地解析渲染。
REMOTE = (
    'while true; do echo "=F="; '
    'nvidia-smi --query-gpu=index,name,utilization.gpu,utilization.memory,memory.used,memory.total,power.draw,power.limit,temperature.gpu,clocks.sm,clocks.mem --format=csv,noheader,nounits; '
    'echo "=P="; '
    'nvidia-smi --query-compute-apps=pid,used_memory,process_name --format=csv,noheader; '
    'sleep %g; done' % REFRESH
)


def state_color(frac, warn=WARN, crit=CRIT):
    """占比 0~1 → 状态色：green(正常)/yellow(警戒)/bright_red(危险)"""
    if frac >= crit:
        return "bright_red"
    if frac >= warn:
        return "yellow"
    return "green"


def temp_color(t, warn=T_WARN, crit=T_CRIT):
    """温度 °C → 状态色（阈值见模块常量）"""
    if t >= crit:
        return "bright_red"
    if t >= warn:
        return "yellow"
    return "green"


def bar(frac, w, color_fn=state_color):
    """状态色区块条：█ 填充 / ░ 空。颜色 + 填充比例双重编码信息。"""
    n = max(0, min(w, int(round(frac * w))))
    fill = Text("█" * n, style=color_fn(frac))
    empty = Text("░" * (w - n), style="dim")
    return fill + empty


def spark(values, width=60, lo=None, hi=None, color="cyan"):
    """把最近值序列画成 ASCII 阶梯曲线，整线着色（配合左侧文字标签辨识）。"""
    if not values:
        return Text("")
    lo = lo if lo is not None else min(values)
    hi = hi if hi is not None else max(values)
    rng = (hi - lo) or 1.0
    glyphs = " _.-=+*#%@"
    step = max(1, len(values) // width)
    sampled = list(values)[::step][:width]
    s = "".join(glyphs[min(9, max(0, int(round((v - lo) / rng * 9))))] for v in sampled)
    return Text(s, style=color)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    once = "--once" in sys.argv
    console = Console()
    console.print("[cyan]连接 RunPod 拉取 GPU 数据…[/cyan]" + ("（快照模式）" if once else ""))

    # 按终端宽度自适应条长 / 曲线宽，避免窄终端溢出
    term_w = console.width or 100
    bar_w = max(12, min(30, (term_w - 45) // 2))
    spark_w = max(40, min(100, term_w - 20))

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

    def render(g, procs, start):
        try:
            idx, name, ug, _um, mu, mt, pw, pl, temp, smc, memc = [x.strip() for x in g]
            u = float(ug)
            mur = float(mu)
            mtr = float(mt) or 1.0   # 防护显存总量为 0 导致的除零
            p = float(pw)
            plr = float(pl) or 1.0
            t = float(temp)
        except Exception:
            return None
        hu.append(u)
        hv.append(mur)
        hp.append(p)
        ht.append(t)

        elapsed = int(time.time() - start)

        # ---- 整体状态（取各指标最差者；温度按 T_CRIT 等比例映射到 CRIT，保证
        #      85°C 时状态恰为"危险"，与 temp_color 色阶一致）----
        worst = max(u / 100, mur / mtr, p / plr, t / T_CRIT * CRIT)
        if worst >= CRIT:
            overall, ocolor = "危险", "bright_red"
        elif worst >= WARN:
            overall, ocolor = "警戒", "yellow"
        else:
            overall, ocolor = "正常", "green"

        # ---- 告警（文字 + 颜色，避免仅靠颜色传达信息）----
        alerts = []
        if t >= T_CRIT:
            alerts.append("高温 %.0f°C" % t)
        if u / 100 >= CRIT:
            alerts.append("利用率 %.0f%%" % u)
        if mur / mtr >= CRIT:
            alerts.append("显存 %.1f/%.1f GB" % (mur / 1024, mtr / 1024))
        if p / plr >= CRIT:
            alerts.append("功率 %.0f/%.0f W" % (p, plr))

        # ---- 状态头行（GPU 名去 "NVIDIA " 前缀、POD 取 id 前缀，保证窄终端不换行）----
        gpu_short = name.replace("NVIDIA ", "") or name
        pod_id = POD.split("@")[0].split("-")[0]
        header = Text.from_markup(
            "[bold]%s[/bold] GPU %s  POD [cyan]%s[/cyan]  刷新 %.1fs  运行 %d:%02d  状态 [%s]%s[/%s]"
            % (gpu_short, idx, pod_id, REFRESH, elapsed // 60, elapsed % 60, ocolor, overall, ocolor)
        )

        # ---- GPU 面板 ----
        stats = Table.grid(padding=(0, 2))
        stats.add_column(justify="left", width=8)
        stats.add_column(justify="left", width=bar_w + 2)
        stats.add_column(justify="right", width=22)
        stats.add_row("Util", bar(u / 100, bar_w), "%5.1f %%" % u)
        stats.add_row("VRAM", bar(mur / mtr, bar_w), "%5.2f / %5.2f GB" % (mur / 1024, mtr / 1024))
        stats.add_row("Power", bar(p / plr, bar_w), "%6.1f / %5.0f W" % (p, plr))
        stats.add_row("Temp", bar(t / 100.0, bar_w, temp_color), "%5.0f C" % t)
        stats.add_row("Clock", "", "SM %s / Mem %s MHz" % (smc, memc))
        gpu_panel = Panel(stats, title="[bold]实时状态[/bold]",
                          subtitle=time.strftime("%Y-%m-%d %H:%M:%S"))

        # ---- 历史趋势（每指标独立强调色；单 Text 多行保留各段样式）----
        curve = Text()
        for i, (label, d, lo, hi, color) in enumerate((
                ("Util %", hu, 0, 100, "cyan"),
                ("VRAM GB", hv, 0, mtr / 1024, "bright_blue"),
                ("Power W", hp, 0, plr, "yellow"),
                ("Temp C", ht, 20, 100, "bright_red"))):
            if i:
                curve.append("\n")
            curve.append_text(Text.from_markup("[bold]%s[/bold] " % label))
            curve.append_text(spark(d, spark_w, lo, hi, color))
        curve_panel = Panel(curve, title="历史趋势（最近 %d 帧）" % len(hu))

        # ---- 计算进程表 ----
        pt = Table(title="GPU 计算进程", box=None, header_style="bold cyan")
        pt.add_column("PID", justify="right", width=8, no_wrap=True)
        pt.add_column("显存 MiB", justify="right", width=10, no_wrap=True)
        pt.add_column("进程", overflow="fold")
        if not procs:
            pt.add_row("—", "—", "（无）")
        for pid, mem, pname in procs[:8]:
            pt.add_row(pid, mem, pname)

        # ---- 组装 ----
        parts = [header]
        if alerts:
            banner = Text("  ".join("!! " + a for a in alerts), style="bright_red bold")
            parts.append(Panel(banner, title="[bright_red]告警[/bright_red]",
                               border_style="bright_red"))
        parts.extend([Align.center(gpu_panel), Align.center(curve_panel), pt])
        grid = Table.grid(expand=True)
        for part in parts:
            grid.add_row(part)
        return grid

    def parse_and_render(frame, start):
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
            r = render(g, procs, start)
            if r is not None:
                if once:
                    console.print(r)
                    return True
                live.update(r)
        return False

    def frame_loop(handle_frame, start):
        """逐行累积帧，遇到 =F= 分隔符交给 handle_frame"""
        frame = []
        while proc.poll() is None:
            line = proc.stdout.readline()
            if not line:
                break
            text = line.decode(errors="replace").strip()
            if text == "=F=":
                if frame and handle_frame(frame, start):
                    return
                frame = []
            elif text:
                frame.append(text)
        if frame:
            handle_frame(frame, start)

    start = time.time()
    try:
        if once:
            frame_loop(parse_and_render, start)
        else:
            with Live(console=console, refresh_per_second=2, screen=True) as live:
                frame_loop(parse_and_render, start)
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
