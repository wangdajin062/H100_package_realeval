"""Quick upload key files to RunPod"""
import sys, os, time
sys.path.insert(0, r"c:\Users\wang\Projects\H100_package_realeval")
from scripts.sync_to_runpod import RunpodSync
from pathlib import Path

LOCAL_ROOT = Path(r"c:\Users\wang\Projects\H100_package_realeval")
REMOTE_ROOT = "/workspace/H100_package_realeval"

sync = RunpodSync(
    "https://40e69wcbga2q1d-8888.proxy.runpod.net",
    "vbul2cc1qmltayxrjyws",
    timeout=60
)

# Upload key files first
key_files = [
    "pyproject.toml",
    "requirements.txt",
    "README.md",
    "run.sh",
    "run_all.sh",
    "run_h100.sh",
    "setup.sh",
    "setup_workspace.sh",
    "monitor.py",
    "h100_preflight_check.py",
    "test_gpu.py",
    "scripts/sync_to_runpod.py",
]

ok = 0
fail = 0
for rel in key_files:
    local = LOCAL_ROOT / rel
    remote = f"{REMOTE_ROOT}/{rel}"
    remote_dir = os.path.dirname(remote)
    try:
        sync.ensure_directory(remote_dir)
        sync.upload_file(local, remote)
        print(f"[OK] {rel}")
        ok += 1
    except Exception as e:
        print(f"[FAIL] {rel}: {e}")
        fail += 1
    time.sleep(0.2)

print(f"\nDone: {ok} uploaded, {fail} failed")
