#!/bin/bash
# Poll setup progress on the pod
echo "=== setup_launch.out ==="
tail -20 /tmp/setup_launch.out 2>/dev/null
echo "=== pip_install.log tail ==="
tail -6 /tmp/pip_install.log 2>/dev/null
echo "=== setup procs ==="
ps aux | grep -E "pip|setup_remote" | grep -v grep | head -5 || echo none
echo "=== done ==="
