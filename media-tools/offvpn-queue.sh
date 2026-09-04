#!/bin/bash
# Everything that does NOT need the VPN, held until the VPN comes off.
#
# Measured tonight: archive.org gave 12.4 MB/s with the VPN off and 98 KB/s
# through a Romanian exit - 125x. tokyvideo's CDN measured 107 KB/s through the
# same exit. At those rates this queue is ten days of work through the tunnel and
# a few hours without it, so it waits rather than crawls.
#
# Cantonés is the ONLY thing that still needs the VPN (YouTube bot-checked the
# home IP); it runs on the other queue meanwhile.
set -u
cd "/Users/briantang/Downloads/Converted" || exit 1
LOG="_offvpn.log"
say(){ echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }
vpnup(){ scutil --nc status "ProtonVPN" 2>/dev/null | head -1 | grep -q Connected; }

say "=== waiting for the VPN to come off ==="
while vpnup; do sleep 30; done
say "VPN is down - starting"
# CREATE EVERY FOLDER FIRST. A redirect into "$show/_download.log" fails if the
# folder does not exist, so get-archive.py never runs, the pass reports 0 and the
# queue moves on - silently. This exact bug cost seven shows a full run earlier,
# and was reintroduced here for Rocket Power and Digimon Adventure.
for d in "Journey to the West" "Rocket Power" "Digimon Adventure"; do
  mkdir -p "$d/_staging"
done
say "throughput check: $(curl -sS -m 60 -o /dev/null -w '%{speed_download}' -r 0-4000000 -L \
  'https://archive.org/download/1998-journey.to.the.west-s2/02.mp4' 2>/dev/null) B/s from archive.org"

say ">>> 1/4 Journey to the West (42 eps, 24 GB)"
python3 _tools/get-archive.py "Journey to the West" 1998-journey.to.the.west-s2 \
  >> "Journey to the West/_download.log" 2>&1
say "    $(ls 'Journey to the West/_staging' 2>/dev/null | wc -l | tr -d ' ')/42"

say ">>> 2/4 Rocket Power (62 eps, 10.8 GB)"
python3 _tools/get-archive.py "Rocket Power" Rocket-Power-Latino \
  >> "Rocket Power/_download.log" 2>&1
say "    $(find 'Rocket Power/_staging' -name '*.mp4' 2>/dev/null | wc -l | tr -d ' ')/62"

say ">>> 3/4 Digimon Adventure - season 1 then season 2 (105 eps, 7.6 GB)"
python3 _tools/get-archive.py "Digimon Adventure" digimon-adventure-espanol-latino-1999 \
  >> "Digimon Adventure/_download.log" 2>&1
python3 _tools/digimon-file.py 1 >> "$LOG" 2>&1
python3 _tools/get-archive.py "Digimon Adventure" digimon-adventure-02-espanol-latino-etc-tv-rip-2017 \
  >> "Digimon Adventure/_download.log" 2>&1
python3 _tools/digimon-file.py 2 >> "$LOG" 2>&1
say "    $(find 'Digimon Adventure' -name '*.mp4' 2>/dev/null | wc -l | tr -d ' ')/105"

say ">>> 4/4 tokyvideo - 368 episodes across 5 shows (~95 GB)"
python3 _tools/tokyvideo-get.py >> "$LOG" 2>&1
say "=== OFF-VPN QUEUE COMPLETE ==="
