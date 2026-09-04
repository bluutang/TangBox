#!/bin/bash
# Watch the rest of the queue with the VPN OFF and report anything newly
# geo-blocked. This is the window that matters: everything downloaded before now
# went through a Canadian exit, and everything from here goes out on the home
# connection.
#
# Baseline was taken the moment the VPN dropped (_blocked-vpnoff.txt): 5 Jorge
# videos, all long known. Anything the diff shows is new.
set -u
cd "/Users/briantang/Downloads/Converted" || exit 1
LOG="_geoblock-audit.log"
say(){ echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }
say "=== watching the rest of the queue for new geo-blocks (VPN off) ==="
while pgrep -f 'run-queue-[r]est' > /dev/null; do sleep 120; done
say "queue finished"
python3 _tools/blocked.py > _blocked-final.txt 2>&1
say "--- NEW geo-blocks since the VPN came off ---"
if diff -q _blocked-vpnoff.txt _blocked-final.txt > /dev/null; then
  say "NONE - nothing new was blocked"
else
  diff _blocked-vpnoff.txt _blocked-final.txt | grep '^>' | tee -a "$LOG"
fi
say "--- per-show totals ---"
python3 _tools/status.py >> "$LOG" 2>&1 || say "(status.py unavailable)"
say "=== audit done ==="
