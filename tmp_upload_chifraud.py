import sys, os
sys.path.insert(0, "c:/Users/wang/Projects/H100_package_realeval")
from scripts.sync_to_runpod import RunpodSync

sync = RunpodSync("https://40e69wcbga2q1d-8888.proxy.runpod.net", "vbul2cc1qmltayxrjyws", timeout=120)
local = "c:/Users/wang/Projects/H100_package_realeval/data/ChiFraud/chifraud.jsonl"
remote = "/workspace/H100_package_realeval/data/ChiFraud/chifraud.jsonl"
sync.ensure_directory("/workspace/H100_package_realeval/data/ChiFraud")
sync.upload_file(__import__("pathlib").Path(local), remote)
print("UPLOADED", local, "->", remote, os.path.getsize(local), "bytes")
