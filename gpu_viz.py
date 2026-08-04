#!/usr/bin/env python3
"""gpu_viz.py -- RunPod dual-mode monitor
  python gpu_viz.py                  SSH GPU dashboard
  python gpu_viz.py --results        Results poller (Jupyter API, 30s)
  python gpu_viz.py --results --once Results snapshot
"""
import json, os, re, subprocess, sys, time, urllib.request

try:
    from rich.align import Align; from rich.console import Console
    from rich.live import Live; from rich.panel import Panel
    from rich.table import Table; from rich.text import Text
except ImportError: sys.exit("pip install rich")

POD = "mhypfkvge474n8-64411fb1@ssh.runpod.io"
KEY = os.path.expanduser("~/.ssh/id_ed25519")
BASE = "https://mhypfkvge474n8-8888.proxy.runpod.net"
TOKEN = "uv9gowwjyzzqerlwfg58"

def api(p, content=False):
    q = "?content=1&format=text&token=" if content else "?token="
    h = {"User-Agent": "runpod-sync/1.0", "Referer": BASE + "/lab"}
    return json.loads(urllib.request.urlopen(
        urllib.request.Request(BASE + "/api/contents" + p + q + TOKEN, headers=h), timeout=15).read())

# ── Results mode ──
def results_monitor(once=False):
    c = Console()
    def render():
        ps = []
        r = api("/workspace/H100_package_realeval/outputs/results")
        fs = sorted(r.get("content", []), key=lambda x: x.get("last_modified", ""))
        t = Table(title="Results", box=None, header_style="bold cyan")
        t.add_column("File", width=42); t.add_column("Time", width=20)
        for f in fs: t.add_row(f["name"], f["last_modified"][:19])
        ps.append(t)
        try:
            ae = api("/workspace/H100_package_realeval/outputs/results/all_experiments.json", True)
            d = json.loads(ae.get("content", "{}"))
            ft = Table(title="F1", box=None, header_style="bold green")
            ft.add_column("Exp", width=8); ft.add_column("F1", justify="right")
            for k, v in d.items():
                if isinstance(v, dict) and v.get("f1") is not None:
                    ft.add_row(k, str(round(v["f1"], 4)))
            if ft.row_count: ps.append(ft)
        except: pass
        try:
            pt = api("/workspace/H100_package_realeval/outputs/results/paper_table.md")
            ps.append(Text(f"\n[green]paper_table: {pt['size']} bytes[/green]"))
        except: ps.append(Text("\n[dim]paper_table: not yet[/dim]"))
        g = Table.grid(expand=True)
        for p in ps: g.add_row(Align.center(p) if not isinstance(p, str) else p)
        return Panel(g, title="RunPod Pipeline", subtitle=time.strftime("%H:%M:%S"), border_style="cyan")
    if once: c.print(render()); return
    with Live(console=c, refresh_per_second=0.5, screen=True) as live:
        while True:
            try: live.update(render())
            except: pass
            time.sleep(30)

# ── SSH GPU mode ──
REMOTE = (
    'while true; do echo "=F="; '
    'nvidia-smi --query-gpu=index,name,utilization.gpu,utilization.memory,memory.used,memory.total,power.draw,power.limit,temperature.gpu,clocks.sm,clocks.mem --format=csv,noheader,nounits; '
    'echo "=P="; nvidia-smi --query-compute-apps=pid,used_memory,process_name --format=csv,noheader; sleep 1; done')

def bar(frac, w):
    n = max(0, min(w, int(round(frac * w))))
    col = "bright_red" if frac >= 0.95 else ("yellow" if frac >= 0.8 else "green")
    return Text("█" * n, style=col) + Text("░" * (w - n), style="dim")

def gpu_monitor(once=False):
    c = Console(); c.print("[cyan]Connecting RunPod GPU...[/cyan]")
    bw = 20
    proc = subprocess.Popen(["ssh", "-tt", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20",
        "-o", "StrictHostKeyChecking=accept-new", "-i", KEY, POD],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try: proc.stdin.write((REMOTE + "\n").encode()); proc.stdin.flush()
    except: c.print("[red]SSH failed. Try: python gpu_viz.py --results[/red]"); return
    def _render(g, procs):
        if not g or len(g) < 11: return None
        try:
            gu = float(g[2]) / 100 if g[2] != "[N/A]" else 0
            mu = float(g[4]) * 1024 if g[4] != "[N/A]" else 0
            mt = float(g[5]) * 1024 if g[5] != "[N/A]" else 80000
            pw = float(g[6]) if g[6] != "[N/A]" else 0
            pl = float(g[7]) if g[7] != "[N/A]" else 700
        except: return None
        mtr, mur = mt / 1024, mu / 1024
        hdr = Panel(f"[bold]GPU {g[0]}: {g[1]}[/bold]  {g[9]}MHz  {pl:.0f}W",
                     title="H100", border_style="cyan", subtitle=time.strftime("%H:%M:%S"))
        gt = Table(box=None); gt.add_column("", width=10); gt.add_column("", width=14); gt.add_column("", width=bw+2)
        gt.add_row("GPU", f"{gu*100:.0f}%", bar(gu, bw))
        gt.add_row("VRAM", f"{mur:.0f}/{mtr:.0f}GB", bar(mur/max(mtr,1), bw))
        gt.add_row("Power", f"{pw:.0f}/{pl:.0f}W", bar(pw/max(pl,1), bw))
        gt.add_row("Temp", f"{g[8]}C", bar(float(g[8])/100 if g[8]!="[N/A]" else 0, bw))
        pt = Table(title="Processes", box=None, header_style="bold cyan")
        pt.add_column("PID", width=8); pt.add_column("VRAM", width=10); pt.add_column("Name")
        for pid, mem, nm in (procs or [])[:8]: pt.add_row(pid, mem, nm)
        if not procs: pt.add_row("-", "-", "none")
        gd = Table.grid(expand=True)
        for p in [hdr, Align.center(Panel(gt)), pt]: gd.add_row(p)
        return gd
    def _parse(fr):
        g, ps = None, []
        for ln in fr:
            if g is None and "," in ln and re.match(r"^\d+,", ln):
                pp = [x.strip() for x in ln.split(",")]
                if len(pp) >= 11: g = pp
            m = re.match(r"^(\d+),\s*(\d+)\s*MiB,\s*(.*)$", ln)
            if m: ps.append((m.group(1), m.group(2), m.group(3)))
        return g, ps
    def _loop():
        fr = []
        while proc.poll() is None:
            l = proc.stdout.readline()
            if not l: break
            t = l.decode(errors="replace").strip()
            if t == "=F=":
                if fr:
                    g, ps = _parse(fr)
                    if g:
                        r = _render(g, ps)
                        if r:
                            if once: c.print(r); return
                            live.update(r)
                fr = []
            elif t: fr.append(t)
    try:
        if once: _loop()
        else:
            with Live(console=c, refresh_per_second=2, screen=True) as live: _loop()
    except KeyboardInterrupt: pass
    finally:
        try: proc.terminate()
        except: pass
        c.print("[dim]Exit[/dim]")

if __name__ == "__main__":
    if "--results" in sys.argv:
        results_monitor(once="--once" in sys.argv)
    else:
        gpu_monitor(once="--once" in sys.argv)