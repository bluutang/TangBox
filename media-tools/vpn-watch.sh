#!/bin/bash
# Unattended: turn the VPN off once the geo-blocked Sailor Moon content is done,
# then report any geo-block that turns up afterwards.
#
# The queue prints ">>> BLOCKED SAILOR MOON CONTENT COMPLETE" when it is finished
# with seasons 1/R/S. NOTE it prints that even if the show gave up short of its
# 127 target, so the real count is recorded here too - short of 127 means the
# blocked seasons need another pass WITH the VPN back on.
#
# The VPN is stopped through the macOS network service, not by quitting the app:
# quitting it could leave a kill switch holding the network down, which would
# strand every remaining download.
set -u
cd "/Users/briantang/Downloads/Converted" || exit 1
LOG="_vpn-watch.log"
MARK=">>> BLOCKED SAILOR MOON CONTENT COMPLETE"
say(){ echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

smcount(){ wc -l < "Sailor Moon/_archive.txt" 2>/dev/null | tr -d ' '; }
vpnup(){ scutil --nc status "ProtonVPN" 2>/dev/null | head -1 | grep -q Connected; }
online(){ curl -s -m 15 -o /dev/null -w '%{http_code}' https://www.youtube.com/ 2>/dev/null; }

say "=== watching for the Sailor Moon marker ==="
say "baseline: Sailor Moon $(smcount)/200, VPN $(scutil --nc status ProtonVPN | head -1)"

# Baseline of what is already known to be blocked, so anything NEW stands out.
python3 _tools/blocked.py > _blocked-before.txt 2>&1
say "baseline geo-block report -> _blocked-before.txt"

# 1. wait for the marker (or for the queue to end without ever printing it)
while true; do
  grep -qF "$MARK" _queue.log && { say "MARKER SEEN"; break; }
  if ! pgrep -f 'run-[q]ueue15' > /dev/null; then
    say "!! the queue exited before the marker appeared"; break
  fi
  sleep 60
done

n=$(smcount)
say "Sailor Moon finished at ${n}/200 (blocked seasons target 127)"
if [ "${n:-0}" -lt 127 ]; then
  say "!! SHORT OF 127 - the blocked seasons did NOT all download."
  say "!! Those episodes need the VPN back ON (Canada) and:"
  say "!!   cd ~/Downloads/Converted && python3 _tools/blocked.py --retry"
fi

# 2. stop the VPN, and hold it down if the app reconnects
say "stopping the VPN..."
for try in 1 2 3; do
  scutil --nc stop "ProtonVPN" 2>&1 | tee -a "$LOG"
  sleep 20
  if vpnup; then say "  attempt $try: still connected, retrying"; else say "  VPN is DOWN"; break; fi
done
vpnup && say "!! COULD NOT STOP THE VPN - it keeps reconnecting. Turn it off by hand."

code=$(online)
if [ "$code" = "200" ]; then say "internet OK without the VPN (youtube.com -> 200)"
else say "!! NO INTERNET after stopping the VPN (got '$code') - possible kill switch."
     say "!! Downloads will stall until the ProtonVPN app is dealt with by hand."; fi

# 3. let the rest of the queue run, then report anything newly blocked
say "waiting for the queue to finish, then auditing geo-blocks..."
while pgrep -f 'run-[q]ueue15' > /dev/null; do
  if vpnup; then say "note: the VPN came back up on its own"; scutil --nc stop "ProtonVPN"; fi
  sleep 120
done
say "queue finished"
python3 _tools/blocked.py > _blocked-after.txt 2>&1
say "--- NEW geo-blocks since the VPN came off (nothing below = none) ---"
diff _blocked-before.txt _blocked-after.txt | grep '^>' | tee -a "$LOG"
say "--- end of report (full detail in _blocked-after.txt) ---"
