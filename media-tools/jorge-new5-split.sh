#!/bin/bash
# Split the 3 of 5 new Jorge files whose structure is confirmed.
#
# These 5 are 66 minutes, not 45: SIX ~11-minute stories = THREE episodes, so
# two cuts each, not one. They also do NOT use the bright white title card the
# other 29 use - their brightest frames are dim (184-220) and last 1-2s, which is
# scenery, not a card. The boundaries are BLACK GAPS on a ~660 s grid.
#
# Cut at the END of the gap, not its middle: re-encoding has no keyframe
# constraint, so the piece can start on the first real frame. (The old
# "cut at the middle of the fade" rule existed only because -c copy snapped
# backwards; it does not apply here.)
#
# NA-NLwb5-r5Stw and NA-XBSF8xSNt2g are NOT here: their gaps do not sit on the
# grid (NLwb5 has no 2638 or 3298; XBSF8x has almost nothing). Guessing a cut
# for them would repeat the mistake that produced groups B and C.
set -u
cd "/Users/briantang/Downloads/Converted/Jorge el Curioso" || exit 1
LOG="../_jorge-new5.log"
say(){ echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }
avg(){ ffmpeg -hide_banner -loglevel error -i "$1" -ss "$2" -frames:v 1 -vf scale=1:1 \
        -f rawvideo -pix_fmt rgb24 - 2>/dev/null | od -An -tu1 | awk '{print $1","$2","$3}'; }

# d=0.1, not 0.3: NA-vbPMfjlzBNw's second boundary is a 0.28s gap and
# NA-NLwb5-r5Stw's is 0.28s too - a 0.3s floor hid both and made two
# perfectly ordinary files look structurally broken.
# find the end of the black gap nearest a target time, so the cut is measured
# per file rather than transcribed
gapend(){ ffmpeg -hide_banner -nostats -i "$1" -vf "blackdetect=d=0.1:pix_th=0.35" -an -f null - 2>&1 \
  | grep blackdetect | sed -E 's/.*black_start:([0-9.]+) black_end:([0-9.]+).*/\1 \2/' \
  | python3 -c "
import sys
t=float(sys.argv[1]); rows=[tuple(map(float,l.split())) for l in sys.stdin if l.strip()]
near=[r for r in rows if abs(r[0]-t)<60]
print(f'{near[0][1]:.2f}' if near else '')
" "$2"; }

say "=== splitting the 3 new files with a confirmed 660s grid ==="
for n in NA-9-tPXFhKG4s NA-hw1cCXHibEM NA-vbPMfjlzBNw; do
  f="_staging/$n.mp4"
  c1=$(gapend "$f" 1319); c2=$(gapend "$f" 2638)
  if [ -z "$c1" ] || [ -z "$c2" ]; then say "!! $n: could not measure both cuts (got '$c1' '$c2') - SKIPPED"; continue; fi
  say "--- $n  cuts at ${c1}s and ${c2}s"
  python3 ../_tools/cut-at.py "$f" --at "$c1" "$c2" --outdir _reenc >> "$LOG" 2>&1 \
    || { say "!! $n FAILED"; continue; }
  for p in pt02 pt03; do
    say "   $n $p head RGB $(avg "_reenc/$n - $p.mp4" 0.5)  (0,0,0 would mean it opens on black)"
  done
done
say "=== new-5 split done (2 files still need review) ==="
