#!/bin/bash
# Keep _status.html current. Safe to leave running; safe to kill at any time.
#   start:  nohup /Users/briantang/Downloads/Converted/_tools/watch-status.sh >/dev/null 2>&1 &
#   stop:   pkill -f watch-status.sh
while true; do
  python3 "/Users/briantang/Downloads/Converted/_tools/status.py" >/dev/null 2>&1
  sleep 15
done
