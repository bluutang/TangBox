#!/bin/bash
# Wait out Google Drive's rate limit, then finish the Xiaolin download.
#
# Files 1-32 came down fine, then 33-52 ALL failed at once with "or have had
# many accesses" - a throttle, not a permissions fault. Retrying hard makes it
# worse, so this PROBES A SINGLE FILE each cycle and only starts the real fetch
# once that probe resolves. get-xiaolin.py skips anything already on disk at the
# right size, so resuming refetches nothing.
set -uo pipefail
cd /Users/briantang/Downloads/Converted
GD=_tools/.venv/bin/gdown
PROBE=1wt3hGeBYyDVGgaAMO9W0EnW6f9DJZuwP     # file 33, first of the blocked run
INTERVAL=1200                                # 20 min between probes
MAX=36                                       # give up after ~12 h

for i in $(seq 1 $MAX); do
  echo "[$(date '+%H:%M:%S')] probe $i/$MAX"
  if python3 - <<'PY'
import subprocess, sys
GD="/Users/briantang/Downloads/Converted/_tools/.venv/bin/gdown"
try:
    r=subprocess.run([GD,"1wt3hGeBYyDVGgaAMO9W0EnW6f9DJZuwP","-O","/dev/null","--quiet"],
                     capture_output=True,text=True,timeout=30)
    sys.exit(0 if not (r.stderr or "").strip() else 1)
except subprocess.TimeoutExpired:
    sys.exit(0)          # transfer started, so the link resolved
PY
  then
    echo "[$(date '+%H:%M:%S')] limit lifted - resuming download"
    python3 _tools/get-xiaolin.py --apply
    rc=$?
    if [ $rc -eq 0 ]; then echo "[$(date '+%H:%M:%S')] ALL 52 COMPLETE"; exit 0; fi
    echo "[$(date '+%H:%M:%S')] partial - throttled again, will keep waiting"
  else
    echo "[$(date '+%H:%M:%S')] still throttled"
  fi
  sleep $INTERVAL
done
echo "gave up after $MAX probes"; exit 1
