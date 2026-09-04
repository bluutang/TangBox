#!/bin/bash
# Everything still missing, in priority order, while a working VPN exit holds.
#
# Order is deliberate: the 5 Jorge videos are GEO-blocked and need a specific
# country, so they go first - the exit can change at any moment. Cantones and
# Aprende Peque were never geo-blocked; they failed YouTube's bot check on the
# home IP, which any VPN exit clears. Spanish Basics is owner-restricted and can
# only ever be 360p, so it goes last and into its own folder.
set -u
cd "/Users/briantang/Downloads/Converted" || exit 1
LOG="_catchup.log"
say(){ echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }
count(){ ls "$1/_staging" 2>/dev/null | wc -l | tr -d ' '; }

say "=== CATCH-UP starting ==="

say ">>> 1/4 Jorge - the 5 GEO-BLOCKED videos (needs this exit)"
before=$(count "Jorge el Curioso")
python3 _tools/blocked.py --retry >> "$LOG" 2>&1
say "    Jorge: $before -> $(count 'Jorge el Curioso') / 34"

say ">>> 2/4 Cantonés - 102 videos (bot check, not geo)"
for u in PL6lk5soCGSstbGSMphkidzxiJ8ByLL1D3 PL6lk5soCGSsuhDlQrWpUX5k_VLdZu9QIQ \
         PL6lk5soCGSsvqzFfbgz8lAH1MyHt2-w4r PL6lk5soCGSsstS7IVTO_3K8zUt_X4h9Jj; do
  ./_tools/get-playlist.sh "Cantonés" "https://www.youtube.com/playlist?list=$u" \
    >> "Cantonés/_download.log" 2>&1
done
say "    Cantonés: $(count 'Cantonés') / 102"

say ">>> 3/4 Aprende Peque con Isa - 26 missing"
./_tools/get-playlist.sh "Aprende Peque con Isa" \
  "https://www.youtube.com/playlist?list=PLb8t9pce11B6fMs7tondof5y2C-G6xYFs" \
  >> "Aprende Peque con Isa/_download.log" 2>&1
say "    Aprende Peque: $(count 'Aprende Peque con Isa') / 34"

say ">>> 4/4 Spanish Basics - 10 owner-restricted, 360p, kept separate"
./_tools/spanish-basics-360.sh >> "$LOG" 2>&1
say "    Spanish Basics 360p: $(ls 'Spanish Basics/_360p'/*.mp4 2>/dev/null | wc -l | tr -d ' ')"

say "=== CATCH-UP done ==="
