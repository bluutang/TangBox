#!/bin/bash
# Diagnose Jorge groups B and C - AFTER the group A re-encode has finished, so
# the two jobs do not fight for CPU.
#
# B (007, 010, 012, 013): pt01 runs long, carrying the next episode.
# C (011, 026):           pt02 opens with MINUTES of the previous episode.
#
# Both are DETECTION failures - the cut is at the wrong boundary - so re-encoding
# cannot help; it would only place a wrong cut precisely. The fix needs the RIGHT
# boundary, and the way to get it is to measure, not to reason (reasoning was
# wrong twice on 2026-08-28).
#
# Every episode opens on a near-white title card, so a full-file sweep for title
# cards shows where the episodes ACTUALLY start - and how many there are, which
# is the open question for B: three of its four files cut at ~1348s, the same
# place as the healthy files, so their real boundary must be somewhere else.
set -u
cd "/Users/briantang/Downloads/Converted/Jorge el Curioso" || exit 1
LOG="../_jorge-bc.log"
say(){ echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

# NO WAIT LOOP. The first version polled `pgrep -f 'jorge-[r]epair'`, which
# matched the MONITOR tailing _jorge-repair.log rather than the repair itself,
# so it waited forever. Same family as the pkill-matches-your-own-shell trap.
# This is launched by hand once the repair has actually finished.
say "=== group A finished; analysing B and C ==="

for n in 007 010 011 012 013 026; do
  src=$(ls _staging/${n}-*.mp4 2>/dev/null | head -1)
  [ -z "$src" ] && { say "!! $n missing"; continue; }
  cur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 \
        "$(ls _split/${n}-*\ -\ pt01.mp4 | head -1)" 2>/dev/null)
  say "--- $n   currently cut at ${cur}s"
  python3 ../_tools/find-title-cards.py "$src" --fps 1 >> "$LOG" 2>&1
done
say "=== done - every title card above is a real episode start ==="
