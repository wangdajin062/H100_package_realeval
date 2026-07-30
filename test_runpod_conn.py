"""Test RunPod connectivity"""
import sys
sys.path.insert(0, r"c:\Users\wang\Projects\H100_package_realeval")
from scripts.sync_to_runpod import RunpodSync

sync = RunpodSync(
    "https://40e69wcbga2q1d-8888.proxy.runpod.net",
    "vbul2cc1qmltayxrjyws",
    timeout=30
)

# Test connectivity
try:
    result = sync._request("GET", "/workspace")
    print("SUCCESS: Connected to RunPod!")
    print(f"Remote /workspace type: {result.get('type', 'unknown')}")
except Exception as e:
    print(f"FAILED: {e}")
