#!/bin/bash
# Work through the remaining shows one at a time, after whatever is already
# running has finished. Sequential on purpose: bandwidth is the bottleneck, so
# parallel downloads just divide the same pipe and make everything land later.
#
# Safe to kill and re-run at any point - every show has its own _archive.txt,
# so finished videos are skipped instantly and nothing is fetched twice.
#   start:  nohup .../run-queue.sh >> .../Converted/_queue.log 2>&1 &
#   stop:   pkill -f run-queue.sh   (then also pkill -f get-playlist.sh)
cd "/Users/briantang/Downloads/Converted" || exit 1
TOOL="./_tools/get-playlist.sh"
say() { echo "[$(date '+%H:%M:%S')] $*"; }

# Wait for the in-flight download (Daniel Tigre) to finish first.
if pgrep -f "get-playlist.sh" >/dev/null; then
  say "waiting for the current download to finish..."
  while pgrep -f "get-playlist.sh" >/dev/null; do sleep 30; done
fi
say "queue starting"

run() {  # run SHOW URL
  say "=== $1"
  "$TOOL" "$1" "$2" >> "$1/_download.log" 2>&1
  say "--- $1 done ($(wc -l < "$1/_archive.txt" 2>/dev/null | tr -d ' ') videos in archive)"
}

run "Franklin"             "https://www.youtube.com/playlist?list=PLjXyTw1_uY7NQbTvTWChxk9Qax1_1cYbV"
# Barney is two playlists into ONE folder; the shared archive drops the 11 they have in common.
run "Barney el Dinosaurio" "https://www.youtube.com/playlist?list=PLo-9TxilbtVEZ74l01fUbpZaK1N0omMpx"
run "Barney el Dinosaurio" "https://www.youtube.com/playlist?list=PLo-9TxilbtVHm4DiE9hOGiZJ0QTb6JNkh"
run "Jorge el Curioso"     "https://www.youtube.com/playlist?list=PL08EcHdANEaXYGEyezJCK4Lhtrhci_8oy"
run "Pistas de Blue y tú"  "https://www.youtube.com/playlist?list=PLaOguQAAiJUgdKXQXiWXml9XR7pEAmGCU"

say "QUEUE COMPLETE - all five shows downloaded"
