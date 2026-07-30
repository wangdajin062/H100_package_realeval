"""Verify files uploaded to RunPod"""
import sys
sys.path.insert(0, r"c:\Users\wang\Projects\H100_package_realeval")
from scripts.sync_to_runpod import RunpodSync

sync = RunpodSync(
    "https://40e69wcbga2q1d-8888.proxy.runpod.net",
    "vbul2cc1qmltayxrjyws",
    timeout=30
)

# Check key files
files_to_check = [
    "/workspace/H100_package_realeval/pyproject.toml",
    "/workspace/H100_package_realeval/requirements.txt",
    "/workspace/H100_package_realeval/README.md",
    "/workspace/H100_package_realeval/run.sh",
    "/workspace/H100_package_realeval/scripts/sync_to_runpod.py",
    "/workspace/H100_package_realeval/realeval",
]

ok = 0
fail = 0
for f in files_to_check:
    try:
        result = sync._request("GET", f)
        ftype = result.get("type", "?")
        print(f"[OK] {f} ({ftype})")
        ok += 1
    except Exception as e:
        print(f"[MISS] {f}")
        fail += 1

print(f"\nTotal: {ok} found, {fail} missing")
