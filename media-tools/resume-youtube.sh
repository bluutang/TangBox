#!/bin/bash
# Resume the YouTube shows ONE AT A TIME, after Sailor Moon's two geo-restricted
# episodes have finished. Brian's instruction: Sailor Moon first, then the rest
# sequentially - not in parallel, which is what made everything crawl earlier
# (two yt-dlp processes splitting an already-throttled VPN pipe; stopping one
# took Sailor Moon from 116 KB/s to 573 KB/s instantly).
#
# Filenames now carry the video title (see get-playlist.sh).
set -u
cd "/Users/briantang/Downloads/Converted" || exit 1
LOG="_resume.log"
say(){ echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }
count(){ find "$1/_staging" -name '*.mp4' ! -name '*.f[0-9]*' 2>/dev/null | wc -l | tr -d ' '; }

# wait for Sailor Moon to finish - watch the log line, not a process name
say "waiting for the 2 Sailor Moon episodes..."
for i in $(seq 1 900); do
  grep -q "SAILOR MOON 2 DONE" _sailor2.log 2>/dev/null && break
  sleep 2
done
say "Sailor Moon done: $(count 'Sailor Moon') files"

say ">>> 1/3 Cantonés (resuming at $(count 'Cantonés')/102)"
for u in PL6lk5soCGSstbGSMphkidzxiJ8ByLL1D3 PL6lk5soCGSsuhDlQrWpUX5k_VLdZu9QIQ \
         PL6lk5soCGSsvqzFfbgz8lAH1MyHt2-w4r PL6lk5soCGSsstS7IVTO_3K8zUt_X4h9Jj; do
  ./_tools/get-playlist.sh "Cantonés" "https://www.youtube.com/playlist?list=$u" \
    >> "Cantonés/_download.log" 2>&1
done
say "    Cantonés: $(count 'Cantonés')/102"

say ">>> 2/3 Aprende Peque con Isa (resuming at $(count 'Aprende Peque con Isa')/34)"
./_tools/get-playlist.sh "Aprende Peque con Isa" \
  "https://www.youtube.com/playlist?list=PLb8t9pce11B6fMs7tondof5y2C-G6xYFs" \
  >> "Aprende Peque con Isa/_download.log" 2>&1
say "    Aprende Peque: $(count 'Aprende Peque con Isa')/34"

say ">>> 3/3 Spanish Basics (resuming at $(count 'Spanish Basics')/22)"
./_tools/get-playlist.sh "Spanish Basics" \
  "https://www.youtube.com/playlist?list=PLCGR7QYLeqvyk121oUP4e8333YVJc9q7x" \
  >> "Spanish Basics/_download.log" 2>&1
say "    Spanish Basics: $(count 'Spanish Basics')/22"

say "=== YOUTUBE RESUME COMPLETE ==="
