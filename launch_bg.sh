#!/bin/bash
cd /tmp
if command -v setsid >/dev/null 2>&1; then
  setsid bash /tmp/setup_remote.sh > /tmp/setup_launch.out 2>&1 < /dev/null &
else
  nohup bash /tmp/setup_remote.sh > /tmp/setup_launch.out 2>&1 < /dev/null &
fi
echo "BG_LAUNCHED pid=$!"
