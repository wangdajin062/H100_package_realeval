"""Incremental upload - resumes where left off, prints progress to file"""
import sys, os, time, json
sys.path.insert(0, r"c:\Users\wang\Projects\H100_package_realeval")
from scripts.sync_to_runpod import RunpodSync, gather_files, DEFAULT_EXCLUDE_DIRS, DEFAULT_EXCLUDE_SUFFIX
from pathlib import Path

LOCAL_ROOT = Path(r"c:\Users\wang\Projects\H100_package_realeval")
REMOTE_ROOT = "/workspace/H100_package_realeval"
STATE_FILE = LOCAL_ROOT / ".upload_state.json"

# Also exclude dotfiles (Jupyter API rejects them with HTTP 400)
EXCLUDE_DIRS = DEFAULT_EXCLUDE_DIRS | {".claude"}
EXCLUDE_SUFFIX = DEFAULT_EXCLUDE_SUFFIX

sync = RunpodSync(
    "https://40e69wcbga2q1d-8888.proxy.runpod.net",
    "vbul2cc1qmltayxrjyws",
    timeout=120
)

# Load or initialize state
if STATE_FILE.exists():
    state = json.loads(STATE_FILE.read_text())
    done_set = set(state.get("done", []))
else:
    done_set = set()

files = gather_files(LOCAL_ROOT, EXCLUDE_DIRS, EXCLUDE_SUFFIX, max_mb=20)
# Filter out dotfiles (Jupyter API returns 400 for them)
files = [f for f in files if not f.name.startswith(".")]
total = len(files)
remaining = [f for f in files if f.relative_to(LOCAL_ROOT).as_posix() not in done_set]

print(f"Total files: {total}, Already done: {len(done_set)}, Remaining: {len(remaining)}", flush=True)

if not remaining:
    print("All files already uploaded!")
    sys.exit(0)

ok = 0
fail = 0
skip = 0
MAX_UPLOADS = 25  # limit per run to avoid timeout

for i, local_f in enumerate(remaining[:MAX_UPLOADS]):
    rel = local_f.relative_to(LOCAL_ROOT).as_posix()
    remote_file = f"{REMOTE_ROOT}/{rel}"
    remote_dir = os.path.dirname(remote_file)
    
    try:
        sync.ensure_directory(remote_dir)
        sync.upload_file(local_f, remote_file)
        done_set.add(rel)
        ok += 1
        if ok % 5 == 0 or ok == min(len(remaining), MAX_UPLOADS):
            print(f"[{ok}/{min(len(remaining), MAX_UPLOADS)}] {rel}", flush=True)
    except Exception as e:
        fail += 1
        print(f"[FAIL] {rel}: {e}", flush=True)

# Save state
STATE_FILE.write_text(json.dumps({"done": list(done_set)}, indent=2))
print(f"\nBatch complete: {ok} uploaded, {fail} failed", flush=True)
print(f"Total progress: {len(done_set)}/{total}", flush=True)
if len(done_set) < total:
    print(f"Run again to continue (state saved to {STATE_FILE})", flush=True)
else:
    print("ALL DONE!")
    STATE_FILE.unlink(missing_ok=True)
