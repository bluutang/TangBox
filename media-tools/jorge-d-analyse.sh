#!/bin/bash
# Group D: 028 and 029, the two Jorge files left after A, B and C were repaired.
#
# 028: its pt02 opens on PURE BLACK (RGB 0,0,0) - the cut landed in a black gap
#      rather than on a title card, and its cut sits 20.7 s off the ~1342 s grid.
# 029: never split at all - one 2672 s piece, the whole file.
#
# Brian's note said these "may be geo-blocked sources". They are not: both files
# downloaded fine. The 5 geo-blocked Jorge videos are a separate, still-missing
# set that needs a Mexico/Spain/UK exit.
set -u
cd "/Users/briantang/Downloads/Converted/Jorge el Curioso" || exit 1
LOG="../_jorge-d.log"
say(){ echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }
say "=== group D: where are the real episode starts? ==="
for n in 028 029; do
  src=$(ls _staging/${n}-*.mp4 2>/dev/null | head -1)
  [ -z "$src" ] && { say "!! $n missing"; continue; }
  d=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$src")
  say "--- $n  source length ${d}s"
  python3 ../_tools/find-title-cards.py "$src" --fps 1 >> "$LOG" 2>&1
done
say "=== group D analysis done ==="
