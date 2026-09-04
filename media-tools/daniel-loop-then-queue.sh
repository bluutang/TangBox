#!/bin/bash
# Retry Daniel Tigre repeatedly, then hand back to the normal queue.
#
# Why looping helps: yt-dlp keeps the partial fragment as a .part file, so each
# pass resumes where the last one died rather than starting over. The four that
# remain are large files (40+ min) that cannot hold a connection long enough on
# the throttled VPN link - but they get closer every attempt.
#
# Stops early on any of: all present, or a pass that added no videos AND grew
# the staging folder by nothing (i.e. genuinely getting nowhere).
cd "/Users/briantang/Downloads/Converted" || exit 1
SHOW="Daniel Tigre"
URL="https://www.youtube.com/playlist?list=PLpX4BrBayzzpPvu58ut-HfqfFlpaMVXGE"
TARGET=61
MAX=5
say(){ echo "[$(date '+%H:%M:%S')] $*"; }
count(){ local n; n=$(wc -l < "$SHOW/_archive.txt" 2>/dev/null | tr -d ' '); echo "${n:-0}"; }
bytes(){ local n; n=$(du -sk "$SHOW/_staging" 2>/dev/null | awk '{print $1}'); echo "${n:-0}"; }

for i in $(seq 1 $MAX); do
  c0=$(count); b0=$(bytes)
  if [ "$c0" -ge "$TARGET" ]; then say "all $TARGET present already"; break; fi
  say "=== Daniel retry pass $i of $MAX (have $c0/$TARGET)"
  ./_tools/get-playlist.sh "$SHOW" "$URL" >> "$SHOW/_download.log" 2>&1
  c1=$(count); b1=$(bytes)
  say "--- pass $i: videos $c0 -> $c1, staged ${b0}KB -> ${b1}KB"
  if [ "$c1" -ge "$TARGET" ]; then say "COMPLETE - all $TARGET downloaded"; break; fi
  if [ "$c1" -eq "$c0" ] && [ "$b1" -le "$b0" ]; then
    say "pass $i made no progress at all - stopping retries early"; break
  fi
done
say "=== Daniel Tigre final: $(count)/$TARGET - handing back to the queue (Franklin next)"
exec ./_tools/run-queue.sh
