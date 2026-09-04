#!/bin/bash
# One show at a time, and each show is retried until it stops making progress.
#
# The old queue advanced as soon as yt-dlp walked the playlist once - but a pass
# that skips 31 geo-blocked videos still "finishes", so Franklin was abandoned at
# 45/78 and Barney started. Each show now gets up to MAX passes and only moves on
# when it is complete, or when a whole pass adds no videos AND no bytes.
cd "/Users/briantang/Downloads/Converted" || exit 1
MAX=4
say(){ echo "[$(date '+%H:%M:%S')] $*"; }
target(){ python3 -c "import json;print(json.load(open('_tools/shows.json'))['$1']['videos'])" 2>/dev/null || echo 9999; }
count(){ local n; n=$(wc -l < "$1/_archive.txt" 2>/dev/null | tr -d ' '); echo "${n:-0}"; }
bytes(){ local n; n=$(du -sk "$1/_staging" 2>/dev/null | awk '{print $1}'); echo "${n:-0}"; }

run_show(){
  local name="$1"; shift
  local tgt; tgt=$(target "$name")
  for i in $(seq 1 $MAX); do
    local c0 b0 c1 b1
    c0=$(count "$name"); b0=$(bytes "$name")
    if [ "$c0" -ge "$tgt" ]; then say "$name already complete ($c0/$tgt)"; return; fi
    say "=== $name pass $i/$MAX (have $c0/$tgt)"
    for u in "$@"; do "./_tools/get-playlist.sh" "$name" "$u" >> "$name/_download.log" 2>&1; done
    c1=$(count "$name"); b1=$(bytes "$name")
    say "--- $name pass $i: $c0 -> $c1 videos, ${b0}KB -> ${b1}KB"
    if [ "$c1" -ge "$tgt" ]; then say "$name COMPLETE ($c1/$tgt)"; return; fi
    if [ "$c1" -eq "$c0" ] && [ "$b1" -le "$b0" ]; then
      say "$name made no progress this pass - moving on at $c1/$tgt"; return
    fi
  done
  say "$name stopped after $MAX passes at $(count "$name")/$tgt"
}

# Wait for whatever is downloading right now (Franklin) to finish its current pass.
if pgrep -f "get-playlist.sh" >/dev/null; then
  say "waiting for the in-flight download to finish..."
  while pgrep -f "get-playlist.sh" >/dev/null; do sleep 20; done
fi

# ORDER: shows with MEASURED geo-block exposure go first, because that content is
# only reachable while the VPN holds. Franklin lost 31 of 78 with the VPN off and
# Jorge 14 of 36; Barney and Blue's Clues have never been measured without it, so
# they go last - if the VPN drops, they are the cheapest to lose and re-run.
run_show "Franklin"             "https://www.youtube.com/playlist?list=PLjXyTw1_uY7NQbTvTWChxk9Qax1_1cYbV"
run_show "Jorge el Curioso"     "https://www.youtube.com/playlist?list=PL08EcHdANEaXYGEyezJCK4Lhtrhci_8oy"
run_show "Barney el Dinosaurio" "https://www.youtube.com/playlist?list=PLo-9TxilbtVEZ74l01fUbpZaK1N0omMpx" \
                                "https://www.youtube.com/playlist?list=PLo-9TxilbtVHm4DiE9hOGiZJ0QTb6JNkh"
run_show "Pistas de Blue y tú"  "https://www.youtube.com/playlist?list=PLaOguQAAiJUgdKXQXiWXml9XR7pEAmGCU"
say "QUEUE COMPLETE"
