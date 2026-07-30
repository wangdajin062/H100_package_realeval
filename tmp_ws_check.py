import websocket, json, time, urllib.request, urllib.parse

BASE = "https://40e69wcbga2q1d-8888.proxy.runpod.net"
TOKEN = "vbul2cc1qmltayxrjyws"

def post(path, body=None):
    data = json.dumps(body).encode() if body else None
    url = f"{BASE}/api{path}?" + urllib.parse.urlencode({"token": TOKEN})
    req = urllib.request.Request(
        url, data=data,
        headers={"User-Agent":"Mozilla/5.0","Accept":"application/json","Content-Type":"application/json","Referer":BASE+"/lab"},
        method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        return json.loads(raw.decode()) if raw else {}

t = post("/terminals", {})
name = t["name"]
print(f"terminal name={name}")
ws = websocket.create_connection(
    f"{BASE.replace('https','wss')}/terminals/websocket/{name}?token={TOKEN}",
    header=["User-Agent: Mozilla/5.0"])

def send(cmd):
    ws.send(f'["stdin",{json.dumps(cmd)}]')

ws.settimeout(2)
try:
    while ws.recv():
        pass
except Exception:
    pass

send("")
time.sleep(0.3)
send("cd /workspace/H100_package_realeval && find . -maxdepth 2 -type d | sort | head -50\r")
time.sleep(2)

buf = ""
ws.settimeout(3)
try:
    while True:
        msg = ws.recv()
        if msg.startswith('["stdout"') or msg.startswith('["stderr"'):
            txt = json.loads(msg)[1]
            buf += txt
            print(txt, end="", flush=True)
except Exception:
    pass

ws.close()
print("\n[ws done]")
