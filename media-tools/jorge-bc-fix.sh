#!/bin/bash
# Re-cut Jorge groups B and C at the title card the fade detector missed.
#
# Measured 2026-08-29 by _tools/find-title-cards.py. Every one of these 45-min
# files holds FOUR ~11-minute stories - Curious George is made as two stories per
# 22-minute episode - so the correct two-way cut is the MIDDLE title card. Across
# all six files that card falls between 1341.3 and 1343.3 s, and the existing cut
# missed it by anywhere from 6 s to 250 s.
#
# Two of these times were confirmed independently: Brian's eyeball measurement of
# the leftover on 011 (4:17 vs 4:10 computed) and 026 (3:05 vs 3:01).
set -u
cd "/Users/briantang/Downloads/Converted/Jorge el Curioso" || exit 1
LOG="../_jorge-bc.log"
say(){ echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }
avg(){ ffmpeg -hide_banner -loglevel error -i "$1" -ss "$2" -frames:v 1 \
         -vf scale=1:1 -f rawvideo -pix_fmt rgb24 - 2>/dev/null \
       | od -An -tu1 | awk '{print $1, $2, $3}'; }

# file : middle title card, seconds
CUTS="007:1342.30 010:1341.80 011:1341.80 012:1341.80 013:1341.30 026:1343.30"

say "=== re-cutting groups B and C at the measured title card ==="
ok=0; bad=0
for pair in $CUTS; do
  n=${pair%%:*}; t=${pair##*:}
  src=$(ls _staging/${n}-*.mp4 2>/dev/null | head -1)
  [ -z "$src" ] && { say "!! $n missing"; continue; }
  say "--- $n  cutting at ${t}s"
  python3 ../_tools/cut-at.py "$src" --at "$t" --outdir _reenc >> "$LOG" 2>&1 \
    || { say "!! $n FAILED"; continue; }
  for f in _reenc/${n}-*\ -\ pt02.mp4; do
    read -r r g b <<< "$(avg "$f" 0.5)"
    lo=$r; [ "$g" -lt "$lo" ] && lo=$g; [ "$b" -lt "$lo" ] && lo=$b
    if [ "$lo" -gt 180 ]; then say "   PASS  $(basename "$f")  RGB $r,$g,$b (title card)"; ok=$((ok+1))
    else say "   FAIL  $(basename "$f")  RGB $r,$g,$b (review)"; bad=$((bad+1)); fi
  done
done
say "=== B/C re-cut done: $ok passed, $bad failed ==="
