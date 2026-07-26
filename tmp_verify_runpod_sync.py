import json
import urllib.parse
import urllib.request

base = "https://tkrpgy6mqloa3d-8888.proxy.runpod.net"
token = "c2shxchdiaetpi4jjlsy"
headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json,text/plain,*/*",
    "Referer": f"{base}/lab",
}
paths = [
    "/workspace/H100_package_realeval/run_h100.sh",
    "/workspace/H100_package_realeval/experiments/exp8_latency_benchmark.py",
    "/workspace/H100_package_realeval/scripts/sync_to_runpod.py",
]
for p in paths:
    u = base + "/api/contents" + urllib.parse.quote(p, safe="/") + "?" + urllib.parse.urlencode({"token": token, "content": 0})
    try:
        d = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=headers), timeout=30).read().decode())
        print("OK", p, d.get("last_modified", ""), d.get("size", ""))
    except Exception as e:
        print("FAIL", p, e)
