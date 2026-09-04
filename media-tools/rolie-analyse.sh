#!/bin/bash
# Find Rolie Polie Olie's segment boundaries in the 8 compilations.
#
# The show is built from ~7.5-minute shorts. Each compilation fades to black
# constantly (29 times in 46 minutes) but MOST of those are scene transitions of
# about 0.9s; the SEGMENT boundaries are noticeably longer, 1.5-2.6s. On Vol 1
# the long gaps land at 1.00, 8.51, 16.02, 23.55, 31.07 and 38.58 minutes -
# spacing 7.51, 7.51, 7.53, 7.52, 7.51. That regularity is the signal.
#
# This only REPORTS. Brian assesses the split points before anything is cut.
set -u
cd "/Users/briantang/Downloads/Converted/Rolie Polie Olie/_staging" || exit 1
LOG="../../_rolie.log"
say(){ echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }
say "=== Rolie Polie Olie: long black gaps (>=1.5s) per compilation ==="
for f in *.mp4; do
  vol=$(echo "$f" | grep -oE 'Vol [0-9]+')
  dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f")
  say "--- $vol   $(python3 -c "print(f'{$dur/60:.1f}')") min"
  ffmpeg -hide_banner -nostats -i "$f" -vf "blackdetect=d=0.1:pix_th=0.35" -an -f null - 2>&1 \
  | grep blackdetect | sed -E 's/.*black_start:([0-9.]+) black_end:([0-9.]+) black_duration:([0-9.]+).*/\1 \2 \3/' \
  | python3 -c "
import sys
rows=[tuple(map(float,l.split())) for l in sys.stdin if l.strip()]
long=[r for r in rows if r[2]>=1.5]
print(f'    {len(rows)} gaps total, {len(long)} are >=1.5s')
prev=None; starts=[]
for a,b,d in long:
    sp=f'{(a-prev)/60:5.2f}' if prev is not None else '  -  '
    print(f'      {a/60:6.2f} min  ({d:.2f}s)   spacing {sp} min')
    starts.append(b); prev=a
if len(long)>2:
    import statistics
    sp=[ (long[i][0]-long[i-1][0])/60 for i in range(1,len(long)) ]
    print(f'    spacing: median {statistics.median(sp):.2f} min, range {min(sp):.2f}-{max(sp):.2f}')
" >> "$LOG" 2>&1
  tail -n +1 /dev/null
done
say "=== analysis done ==="
