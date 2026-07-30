import sys
sys.path.insert(0, r"c:\Users\wang\Projects\H100_package_realeval")
from scripts.sync_to_runpod import RunpodSync
from pathlib import Path

sync = RunpodSync(
    "https://40e69wcbga2q1d-8888.proxy.runpod.net",
    "vbul2cc1qmltayxrjyws",
    timeout=60
)
sync.ensure_directory("/workspace/H100_package_realeval")
p = Path(r"c:\Users\wang\Projects\H100_package_realeval\requirements.txt")
sync.upload_file(p, "/workspace/H100_package_realeval/requirements.txt")
print("OK: requirements.txt uploaded")
