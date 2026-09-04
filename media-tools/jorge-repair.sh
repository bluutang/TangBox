#!/bin/bash
# Repair the 11 "group A" Jorge splits: pt02 opens with 4-7 s of the PREVIOUS
# episode's yellow credits. Cause is the seek, not the detection - `-c copy`
# can only start on a keyframe and rounds BACKWARDS, up to ~5 s. --reencode
# seeks with -ss AFTER -i, which is frame-accurate.
#
# Writes to _reenc/ only. _split/ is left alone, so this is reversible.
#
# Each file is verified automatically. Measured on 006, whose right answer was
# already known: the head of a correct pt02 is the near-white title card
# (RGB ~236,236,237); a broken one is yellow credits (~159,153,62). The blue
# channel separates them with an enormous margin, so "all three channels > 180"
# is the test.
set -u
cd "/Users/briantang/Downloads/Converted/Jorge el Curioso" || exit 1
GROUP_A="006 008 014 016 018 020 021 023 024 025 027"
LOG="../_jorge-repair.log"
say(){ echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

# average colour of one frame, as three decimal numbers
avg(){ ffmpeg -hide_banner -loglevel error -i "$1" -ss "$2" -frames:v 1 \
         -vf scale=1:1 -f rawvideo -pix_fmt rgb24 - 2>/dev/null \
       | od -An -tu1 | awk '{print $1, $2, $3}'; }

say "=== Jorge group A repair: 11 files, re-encoded at 800k ==="
mkdir -p _reenc
ok=0; bad=0; err=0
for n in $GROUP_A; do
  src=$(ls _staging/${n}-*.mp4 2>/dev/null | head -1)
  if [ -z "$src" ]; then say "!! $n  no source file"; err=$((err+1)); continue; fi
  say "--- $n  $(basename "$src")"
  if ! python3 ../_tools/detect-breaks.py "$src" \
        --black-d 0.05 --pix-th 0.35 --black-only --past-credits \
        --split --reencode --outdir _reenc >> "$LOG" 2>&1; then
    say "!! $n  detect-breaks FAILED"; err=$((err+1)); continue
  fi
  # verify every piece after the first: its head must be the title card
  for f in _reenc/${n}-*\ -\ pt0[2-9].mp4; do
    [ -e "$f" ] || continue
    read -r r g b <<< "$(avg "$f" 0.5)"
    lo=$r; [ "$g" -lt "$lo" ] && lo=$g; [ "$b" -lt "$lo" ] && lo=$b
    if [ "$lo" -gt 180 ]; then
      say "   PASS  $(basename "$f")  RGB $r,$g,$b (title card)"; ok=$((ok+1))
    else
      say "   FAIL  $(basename "$f")  RGB $r,$g,$b (not a title card - review)"; bad=$((bad+1))
    fi
  done
done
say "=== done: $ok passed, $bad failed, $err errored ==="
say "sizes: _split $(du -sh _split | cut -f1)   _reenc $(du -sh _reenc | cut -f1)"
