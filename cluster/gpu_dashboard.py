#!/usr/bin/env python3
"""H100 GPU Dashboard — embedded in Jupyter Lab (port 8888)"""
import json, subprocess, os, socket
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

HOSTNAME = socket.gethostname()

PAGE = """<!DOCTYPE html>
<html>
<head>
    <title>H100 GPU Dashboard</title>
    <meta charset="utf-8">
    <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0a0a1a 0%, #1a1a3e 50%, #0d0d2b 100%);
            color: #e0e0e0; min-height: 100vh; padding: 20px;
        }
        .header { display:flex; align-items:center; gap:15px; margin-bottom:24px; padding-bottom:16px; border-bottom:1px solid rgba(255,255,255,0.06); }
        .header h1 { font-size:22px; background:linear-gradient(90deg,#00d4ff,#7b2ff7); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
        .status-dot { width:10px; height:10px; border-radius:50%; display:inline-block; }
        .dot-green { background:#4ecca3; box-shadow:0 0 8px rgba(78,204,163,0.5); }
        .dot-red { background:#ff4757; box-shadow:0 0 8px rgba(255,71,87,0.5); }
        .header-right { margin-left:auto; text-align:right; font-size:12px; color:#666; }
        .header-right .time { color:#00d4ff; font-size:14px; font-weight:600; }
        
        .summary { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px; margin-bottom:20px; }
        .summary-card {
            background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.05);
            border-radius:12px; padding:14px 18px; text-align:center;
        }
        .summary-card .s-label { font-size:10px; color:#666; text-transform:uppercase; letter-spacing:1px; }
        .summary-card .s-value { font-size:24px; font-weight:700; margin-top:4px; }
        
        .grid { display:grid; gap:16px; }
        .card {
            background:rgba(255,255,255,0.03); backdrop-filter:blur(10px);
            border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:20px;
        }
        .gpu-title { display:flex; align-items:center; gap:10px; margin-bottom:16px; }
        .gpu-title h2 { font-size:16px; font-weight:600; }
        .gpu-badge { background:rgba(0,212,255,0.12); color:#00d4ff; padding:2px 10px; border-radius:12px; font-size:11px; font-weight:600; }
        
        .metrics { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
        .m-label { font-size:11px; color:#888; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:2px; }
        .m-value { font-size:26px; font-weight:700; }
        .m-value .u { font-size:13px; font-weight:400; color:#888; margin-left:2px; }
        .bar { height:5px; background:rgba(255,255,255,0.06); border-radius:3px; margin-top:4px; overflow:hidden; }
        .bar-fill { height:100%; border-radius:3px; transition:width 0.5s; }
        
        .c-green { color:#4ecca3; } .c-yellow { color:#ffc107; } .c-red { color:#ff4757; }
        .c-blue { color:#00d4ff; } .c-purple { color:#7b2ff7; }
        .bg-green { background:linear-gradient(90deg,#4ecca3,#2ecc71); }
        .bg-yellow { background:linear-gradient(90deg,#ffc107,#ff9800); }
        .bg-red { background:linear-gradient(90deg,#ff4757,#e74c3c); }
        .bg-blue { background:linear-gradient(90deg,#00d4ff,#0984e3); }
        
        .procs { margin-top:16px; }
        .procs h3 { font-size:12px; color:#ffc107; margin-bottom:8px; display:flex; align-items:center; gap:6px; }
        .ptable { width:100%; border-collapse:collapse; font-size:12px; }
        .ptable th { text-align:left; padding:6px 4px; color:#666; font-weight:500; border-bottom:1px solid rgba(255,255,255,0.05); font-size:10px; text-transform:uppercase; }
        .ptable td { padding:4px; border-bottom:1px solid rgba(255,255,255,0.02); }
        .ptable tr:hover td { background:rgba(255,255,255,0.02); }
        
        .footer { text-align:center; color:#333; font-size:11px; margin-top:20px; padding-top:16px; border-top:1px solid rgba(255,255,255,0.03); }
        @media(max-width:600px) { .metrics { grid-template-columns:1fr; } }
    </style>
</head>
<body>
    <div class="header">
        <span class="status-dot dot-green" id="dot"></span>
        <h1>⚡ H100 GPU Dashboard</h1>
        <div class="header-right">
            <div class="time" id="time">--</div>
            <div id="host">{{host}}</div>
        </div>
    </div>
    
    <div class="summary" id="summary"></div>
    <div class="grid" id="cards"></div>
    <div class="footer">H100 Package RealEval · Auto-refresh every 2s</div>
    
    <script>
    async function fetchData(){
        try {
            const r = await fetch('/gpu-api');
            const d = await r.json();
            document.getElementById('dot').className = 'status-dot dot-green';
            document.getElementById('time').textContent = d.timestamp;
            render(d);
        } catch(e) {
            document.getElementById('dot').className = 'status-dot dot-red';
        }
    }
    function render(d){
        const gpus = d.gpus || [];
        // Summary
        let utilAvg = 0, memSum=0, memTotal=0, pwrSum=0;
        gpus.forEach(g => { utilAvg+=g.util; memSum+=g.mem_used; memTotal+=g.mem_total; pwrSum+=g.power; });
        utilAvg = gpus.length ? (utilAvg/gpus.length).toFixed(1) : 0;
        document.getElementById('summary').innerHTML = `
            <div class="summary-card"><div class="s-label">GPU Utilization</div><div class="s-value ${utilAvg<50?'c-green':utilAvg<80?'c-yellow':'c-red'}">${utilAvg}%</div></div>
            <div class="summary-card"><div class="s-label">GPU Memory</div><div class="s-value c-blue">${memSum.toFixed(1)}<span style="font-size:14px;color:#888"> / ${memTotal.toFixed(1)} GB</span></div></div>
            <div class="summary-card"><div class="s-label">Power Draw</div><div class="s-value c-yellow">${pwrSum.toFixed(0)}<span style="font-size:14px;color:#888"> W</span></div></div>
            <div class="summary-card"><div class="s-label">GPUs</div><div class="s-value c-purple">${gpus.length}</div></div>
        `;
        // Cards
        document.getElementById('cards').innerHTML = gpus.map(g => {
            const uc = g.util<50?'c-green':g.util<80?'c-yellow':'c-red';
            const bg = g.util<50?'bg-green':g.util<80?'bg-yellow':'bg-red';
            const tc = g.temp<60?'c-green':g.temp<80?'c-yellow':'c-red';
            const procs = (g.processes||[]);
            const procRows = procs.length ? procs.slice(0,20).map(p =>
                `<tr><td>${p.pid||'-'}</td><td>${p.user||'-'}</td><td>${p.mem||'?'}MB</td><td style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${(p.cmd||'').replace(/"/g,'&quot;')}">${(p.cmd||'').substring(0,40)}</td></tr>`
            ).join('') : '<tr><td colspan="4" style="color:#555;text-align:center;padding:8px">No running processes</td></tr>';
            return `<div class="card">
                <div class="gpu-title"><h2>🎮 ${g.name}</h2><span class="gpu-badge">GPU ${g.index}</span></div>
                <div class="metrics">
                    <div><div class="m-label">Utilization</div><div class="m-value ${uc}">${g.util}<span class="u">%</span></div><div class="bar"><div class="bar-fill ${bg}" style="width:${g.util}%"></div></div></div>
                    <div><div class="m-label">Memory</div><div class="m-value c-blue">${g.mem_used}<span class="u"> / ${g.mem_total} GB</span></div><div class="bar"><div class="bar-fill bg-blue" style="width:${g.mem_pct}%"></div></div></div>
                    <div><div class="m-label">Temperature</div><div class="m-value ${tc}">${g.temp}<span class="u">°C</span></div></div>
                    <div><div class="m-label">Power</div><div class="m-value c-yellow">${g.power}<span class="u"> W</span></div></div>
                </div>
                <div class="procs"><h3>⎔ Processes (${procs.length})</h3><table class="ptable"><tr><th>PID</th><th>User</th><th>Mem</th><th>Command</th></tr>${procRows}</table></div>
            </div>`;
        }).join('');
    }
    fetchData();
    setInterval(fetchData, 2000);
    </script>
</body>
</html>"""

def get_gpu_data():
    try:
        out = subprocess.check_output("nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,fan.speed --format=csv,noheader,nounits", shell=True, text=True, timeout=5)
        proc_out = subprocess.check_output("nvidia-smi --query-compute-apps=pid,used_memory,gpu_name --format=csv,noheader,nounits", shell=True, text=True, timeout=5)
        processes = {}
        for line in proc_out.strip().split('\n'):
            if not line.strip(): continue
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 2 and parts[0].isdigit():
                gn = parts[2] if len(parts) > 2 else '0'
                processes.setdefault(gn, []).append({'pid': parts[0], 'mem': parts[1]})
        try:
            ps_out = subprocess.check_output("ps aux --no-headers 2>/dev/null | awk '{print $2,$11}'", shell=True, text=True, timeout=3)
            pid_cmd = {}
            for line in ps_out.strip().split('\n'):
                sp = line.strip().split(None, 1)
                if len(sp) >= 2: pid_cmd[sp[0]] = sp[1]
            for g in processes:
                for p in processes[g]:
                    p['cmd'] = pid_cmd.get(p['pid'], '...')
                    p['user'] = 'root'
        except: pass
        gpus = []
        for line in out.strip().split('\n'):
            if not line.strip(): continue
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 8:
                mu = float(parts[3].replace(' MiB','').replace(' MB',''))
                mt = float(parts[4].replace(' MiB','').replace(' MB',''))
                gi = parts[0]
                gpus.append({
                    'index': gi, 'name': parts[1],
                    'util': float(parts[2].replace(' %','')),
                    'mem_used': round(mu/1024, 1), 'mem_total': round(mt/1024, 1),
                    'mem_pct': round(mu/mt*100, 1) if mt > 0 else 0,
                    'temp': int(parts[5]), 'power': round(float(parts[6]), 1), 'fan': parts[7],
                    'processes': processes.get(gi, []) + processes.get(parts[1], [])
                })
        return gpus
    except:
        return []

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/gpu-api':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                'gpus': get_gpu_data(),
                'timestamp': datetime.now().strftime('%H:%M:%S')
            }).encode())
            return
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(PAGE.replace('{{host}}', HOSTNAME).encode())

if __name__ == '__main__':
    port = 6006
    print(f'🚀 GPU Dashboard API running on port {port}')
    print(f'📊 Access via: http://localhost:{port} (or proxy port 6006 on RunPod)')
    HTTPServer(('0.0.0.0', port), Handler).serve_forever()
