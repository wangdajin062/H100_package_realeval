"""Upload with time budget - maximizes files uploaded within time limit"""
import sys, os, time, json
sys.path.insert(0, r"c:\Users\wang\Projects\H100_package_realeval")
from scripts.sync_to_runpod import RunpodSync, gather_files, DEFAULT_EXCLUDE_DIRS, DEFAULT_EXCLUDE_SUFFIX
from pathlib import Path

LOCAL_ROOT = Path(r"c:\Users\wang\Projects\H100_package_realeval")
REMOTE = "/workspace/H100_package_realeval"
STATE_FILE = LOCAL_ROOT / ".upload_state.json"
TIME_BUDGET = 22  # seconds - leave margin for 30s timeout

sync = RunpodSync(
    "https://40e69wcbga2q1d-8888.proxy.runpod.net",
    "vbul2cc1qmltayxrjyws",
    timeout=60
)

# Gather files
EXCLUDE_DIRS = DEFAULT_EXCLUDE_DIRS | {".claude"}
SKIP_PREFIXES = ["services/", "template/services/"]  # Jupyter protects these
files = gather_files(LOCAL_ROOT, EXCLUDE_DIRS, DEFAULT_EXCLUDE_SUFFIX, max_mb=20)
files = [f for f in files if not f.name.startswith(".")]
files = [f for f in files if not any(f.relative_to(LOCAL_ROOT).as_posix().startswith(p) for p in SKIP_PREFIXES)]
total = len(files)

# Load progress
done_set = set()
if STATE_FILE.exists():
    done_set = set(json.loads(STATE_FILE.read_text()).get("done", []))

remaining = [(f, f.relative_to(LOCAL_ROOT).as_posix()) for f in files if f.relative_to(LOCAL_ROOT).as_posix() not in done_set]

print(f"Total: {total}, Done: {len(done_set)}, Remaining: {len(remaining)}", flush=True)

if not remaining:
    print("ALL DONE!")
    STATE_FILE.unlink(missing_ok=True)
    sys.exit(0)

start = time.time()
ok = fail = 0
last_report = 0

for local_f, rel in remaining:
    elapsed = time.time() - start
    if elapsed > TIME_BUDGET:
        break
    
    if time.time() - last_report > 2:
        print(f"  [{ok+1}] uploading {rel}... ({elapsed:.0f}s elapsed)", flush=True)
        last_report = time.time()
    
    remote_file = f"{REMOTE}/{rel}"
    remote_dir = os.path.dirname(remote_file)
    try:
        sync.ensure_directory(remote_dir)
        sync.upload_file(local_f, remote_file)
        done_set.add(rel)
        ok += 1
    except Exception as e:
        fail += 1
        print(f"  FAIL: {rel}: {e}", flush=True)

# Save state
STATE_FILE.write_text(json.dumps({"done": list(done_set)}, indent=2))
elapsed = time.time() - start
print(f"\nDone in {elapsed:.1f}s: {ok} uploaded, {fail} failed. Progress: {len(done_set)}/{total}", flush=True)
if len(done_set) < total:
    print("Run again to continue!", flush=True)
else:
    print("ALL DONE!")
    STATE_FILE.unlink(missing_ok=True)
