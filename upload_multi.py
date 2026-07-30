"""Run upload_batch.py multiple times"""
import subprocess, sys
runs = int(sys.argv[1]) if len(sys.argv) > 1 else 2
for i in range(runs):
    print(f"\n=== Run {i+1}/{runs} ===", flush=True)
    subprocess.run([sys.executable, 
        r"c:\Users\wang\Projects\H100_package_realeval\upload_batch.py"], 
        check=False)
