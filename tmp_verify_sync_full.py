import json
import urllib.parse
import urllib.request
from pathlib import Path
import posixpath

from scripts.sync_to_runpod import (
    DEFAULT_EXCLUDE_DIRS,
    DEFAULT_EXCLUDE_SUFFIX,
    gather_files,
)

BASE = "https://tkrpgy6mqloa3d-8888.proxy.runpod.net"
TOKEN = "c2shxchdiaetpi4jjlsy"
LOCAL_ROOT = Path(r"d:/Projects/H100_package_realeval").resolve()
REMOTE_ROOT = "/workspace/H100_package_realeval"
OUT = LOCAL_ROOT / "tmp_verify_sync_result.json"

headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json,text/plain,*/*",
    "Referer": f"{BASE}/lab",
}

files = gather_files(
    LOCAL_ROOT,
    exclude_dirs=set(DEFAULT_EXCLUDE_DIRS),
    exclude_suffix=set(DEFAULT_EXCLUDE_SUFFIX),
    max_mb=20,
)

missing = []
ok = 0
for i, f in enumerate(files, 1):
    rel = f.relative_to(LOCAL_ROOT).as_posix()
    rp = posixpath.join(REMOTE_ROOT, rel)
    u = BASE + "/api/contents" + urllib.parse.quote(rp, safe="/") + "?" + urllib.parse.urlencode({"token": TOKEN, "content": 0})
    req = urllib.request.Request(u, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            _ = json.loads(r.read().decode("utf-8"))
        ok += 1
    except Exception as e:
        missing.append({"path": rel, "error": str(e)})
    if i % 30 == 0 or i == len(files):
        print(f"[verify] {i}/{len(files)} ok={ok} missing={len(missing)}")

result = {
    "total": len(files),
    "ok": ok,
    "missing": len(missing),
    "missing_items": missing,
}
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

print("=" * 72)
print(f"VERIFY total={result['total']} ok={result['ok']} missing={result['missing']}")
print(f"WROTE {OUT}")
