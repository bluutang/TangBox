#!/bin/bash
# The 5 late Jorge arrivals (the geo-blocked ones, fetched 2026-08-29 on a
# Romanian exit). They are 66 MINUTES, not the 45 of the other 29 - six ~11-min
# stories, so THREE episodes and TWO cuts each, not one.
#
# Scan first, cut second. Tonight proved these files use three different
# boundary markers (white title card, black gap, yellow bumper), so guessing the
# structure is how the last batch went wrong.
set -u
cd "/Users/briantang/Downloads/Converted/Jorge el Curioso" || exit 1
LOG="../_jorge-new5.log"
say(){ echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }
say "=== scanning the 5 new 66-minute Jorge files for episode starts ==="
for f in _staging/NA-*.mp4; do
  d=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f")
  say "--- $(basename "$f" .mp4)  ${d}s"
  python3 ../_tools/find-title-cards.py "$f" --fps 1 >> "$LOG" 2>&1
done
say "=== scan done ==="
