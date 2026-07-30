import json, urllib.request, urllib.parse, hashlib
from pathlib import Path

BASE = "https://40e69wcbga2q1d-8888.proxy.runpod.net"
TOKEN = "vbul2cc1qmltayxrjyws"
HDR = {"User-Agent": "Mozilla/5.0", "Accept": "application/json", "Referer": BASE + "/lab"}
LOCAL_ROOT = Path("c:/Users/wang/Projects/H100_package_realeval")
REMOTE_ROOT = "/workspace/H100_package_realeval"

def get(path):
    u = BASE + "/api/contents" + urllib.parse.quote(path, safe="/") + "?" + urllib.parse.urlencode({"token": TOKEN, "content": 1})
    return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=HDR), timeout=40).read().decode())

checks = [
    "config/experiments.yaml",
    "realeval/real_backend.py",
    "cluster/train_lora_manual.py",
    "scripts/train_and_run_paper.sh",
    "data/ChiFraud/chifraud.jsonl",
]
all_ok = True
for rel in checks:
    local = LOCAL_ROOT / rel
    local_sha = hashlib.sha256(local.read_bytes()).hexdigest()
    try:
        d = get(f"{REMOTE_ROOT}/{rel}")
        fmt = d.get("format")
        if fmt == "base64":
            import base64
            remote = base64.b64decode(d.get("content", ""))
        else:
            remote = d.get("content", "").encode("utf-8")
        remote_sha = hashlib.sha256(remote).hexdigest()
        ok = local_sha == remote_sha
        print("OK" if ok else "DIFF", rel, "size", len(remote))
        if not ok:
            all_ok = False
    except Exception as e:
        print("MISS", rel, type(e).__name__)
        all_ok = False
print("ALL MATCH" if all_ok else "SOME MISMATCH")
