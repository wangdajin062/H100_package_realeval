#!/usr/bin/env python3
"""GPU Monitor Daemon v2 — multi-metric breakdown."""
import subprocess, json, time, os
STATS_FILE = "/workspace/gpu_stats.json"

def query_smi(query):
    try:
        r = subprocess.run(["nvidia-smi", f"--query-gpu={query}", "--format=csv,noheader"],
                           capture_output=True, text=True, timeout=5)
        return [l.strip() for l in r.stdout.strip().split("\n") if l.strip()]
    except:
        return []

def query_procs():
    try:
        r = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory",
                            "--format=csv,noheader"], capture_output=True, text=True, timeout=3)
        return [l.strip() for l in r.stdout.strip().split("\n") if l.strip()]
    except:
        return []

while True:
    raw = query_smi("index,name,utilization.gpu,utilization.memory,"
                    "memory.total,memory.used,memory.free,temperature.gpu,"
                    "power.draw,power.limit,clocks.current.graphics,"
                    "clocks.current.memory,pcie.link.gen.current,pcie.link.width.current")
    gpus = []
    for line in raw:
        parts = [p.strip() for p in line.split(", ")]
        if len(parts) < 14:
            continue
        def f(v, default=0):
            try: return float(v.replace("%","").replace(" MiB","").replace(" W","").replace(" C","").replace(" MHz",""))
            except: return default
        gpus.append({
            "idx": parts[0], "name": parts[1].replace("NVIDIA ",""),
            "util_gpu": parts[2], "util_mem": parts[3],
            "mem_total": parts[4], "mem_used": parts[5], "mem_free": parts[6],
            "temp": parts[7], "power_draw": parts[8], "power_limit": parts[9],
            "clock_gpu": parts[10], "clock_mem": parts[11],
            "pcie_gen": parts[12], "pcie_width": parts[13],
            # Parsed values
            "util_gpu_pct": f(parts[2]),
            "temp_c": f(parts[7]),
            "power_w": f(parts[8]),
            "power_limit_w": f(parts[9]),
            "mem_used_mib": f(parts[5]),
            "mem_total_mib": f(parts[4]),
        })
    
    procs = query_procs()
    pid_info = []
    for p in procs:
        pi = [x.strip() for x in p.split(", ")]
        if len(pi) >= 3:
            pid_info.append({"pid": pi[0], "name": pi[1], "mem": pi[2]})

    with open(STATS_FILE, "w") as f:
        json.dump({
            "gpus": gpus,
            "procs": pid_info,
            "ts": time.strftime("%H:%M:%S")
        }, f)
    time.sleep(3)
