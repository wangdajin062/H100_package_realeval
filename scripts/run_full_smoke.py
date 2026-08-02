import os
import sys
import subprocess

# Run full smoke suite and capture stdout/stderr to full_smoke_run.txt
repo_root = os.path.dirname(os.path.dirname(__file__))
os.chdir(repo_root)
cmd = [sys.executable, '-u', '-m', 'experiments.runner', '--smoke', '--no-archive']
proc = subprocess.run(cmd, capture_output=True, text=True)
out = proc.stdout + "\n\nSTDERR:\n" + proc.stderr
open('full_smoke_run.txt', 'w', encoding='utf-8').write(out)
print('EXIT', proc.returncode)
