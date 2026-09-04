#!/bin/bash
# One show at a time, and each show is retried until it stops making progress.
#
# The old queue advanced as soon as yt-dlp walked the playlist once - but a pass
# that skips 31 geo-blocked videos still "finishes", so Franklin was abandoned at
# 45/78 and Barney started. Each show now gets up to MAX passes and only moves on
# when it is complete, or when a whole pass adds no videos AND no bytes.
cd "/Users/briantang/Downloads/Converted" || exit 1
MAX=4
say(){ echo "[$(date '+%H:%M:%S')] $*"; }
target(){ python3 -c "import json;print(json.load(open('_tools/shows.json'))['$1']['videos'])" 2>/dev/null || echo 9999; }
count(){ local n; n=$(wc -l < "$1/_archive.txt" 2>/dev/null | tr -d ' '); echo "${n:-0}"; }
bytes(){ local n; n=$(du -sk "$1/_staging" 2>/dev/null | awk '{print $1}'); echo "${n:-0}"; }

run_show(){
  local name="$1"; shift
  local tgt; tgt=$(target "$name")
  for i in $(seq 1 $MAX); do
    local c0 b0 c1 b1
    c0=$(count "$name"); b0=$(bytes "$name")
    if [ "$c0" -ge "$tgt" ]; then say "$name already complete ($c0/$tgt)"; return; fi
    say "=== $name pass $i/$MAX (have $c0/$tgt)"
    for u in "$@"; do "./_tools/get-playlist.sh" "$name" "$u" >> "$name/_download.log" 2>&1; done
    c1=$(count "$name"); b1=$(bytes "$name")
    say "--- $name pass $i: $c0 -> $c1 videos, ${b0}KB -> ${b1}KB"
    if [ "$c1" -ge "$tgt" ]; then say "$name COMPLETE ($c1/$tgt)"; return; fi
    if [ "$c1" -eq "$c0" ] && [ "$b1" -le "$b0" ]; then
      say "$name made no progress this pass - moving on at $c1/$tgt"; return
    fi
  done
  say "$name stopped after $MAX passes at $(count "$name")/$tgt"
}

# archive.org items: same retry shape as run_show, different fetcher. No geo-block
# and no format negotiation, so this one is far less likely to need its retries.
run_archive(){
  local name="$1"; shift
  local tgt; tgt=$(target "$name")
  for i in $(seq 1 $MAX); do
    local c0 c1
    c0=$(count "$name")
    if [ "$c0" -ge "$tgt" ]; then say "$name already complete ($c0/$tgt)"; return; fi
    say "=== $name pass $i/$MAX (have $c0/$tgt)"
    python3 "./_tools/get-archive.py" "$name" "$@" >> "$name/_download.log" 2>&1
    c1=$(count "$name")
    say "--- $name pass $i: $c0 -> $c1"
    if [ "$c1" -ge "$tgt" ]; then say "$name COMPLETE ($c1/$tgt)"; return; fi
    if [ "$c1" -eq "$c0" ]; then say "$name no progress - moving on at $c1/$tgt"; return; fi
  done
}

# ---------------------------------------------------------------------------
# SECOND RESUME, 2026-08-29 17:30. The first resume "completed" in 10 minutes
# having downloaded nothing for seven shows. Two independent one-line bugs:
#
#  1. NO FOLDER, NO DOWNLOAD. run_show redirects to "$name/_download.log" before
#     anything creates "$name". If the folder does not exist the redirect fails,
#     get-playlist.sh never runs, and the pass reports "0 -> 0, no progress" and
#     moves on. Only shows with folders left over from earlier sessions worked.
#     Fixed here by creating every folder up front.
#
#  2. curl WITHOUT -L. archive.org 302-redirects /download/ to a specific node.
#     Without -L curl saves the empty redirect body and exits 0 (--fail only
#     trips on 4xx/5xx), so every file landed at 0 bytes while reporting
#     "FAIL (rc=0)". Arthur had 65 empty files that a count check would read as
#     complete. Fixed in _tools/get-archive.py; the empty files were deleted.
#
# Measured, not reasoned: curl without -L returned rc=0 and 0 bytes; with -L,
# rc=0 and 100001 bytes on the same URL.
# ---------------------------------------------------------------------------
for d in "Dora la Exploradora" "Cosmic Kids Yoga" "Spanish Basics" \
         "Aprende Peque con Isa" "Cantonés" "Arthur" "Dragon Ball Z" \
         "Bear in the Big Blue House"; do
  mkdir -p "$d/_staging"
done
# --- Dora: TWO passes over one playlist, into one folder --------------------
# The playlist mixes the 2024 reboot with the classic series and 158 h of clip
# reels. Only two kinds are worth having, so each is fetched by its own filter:
#   1. ~26 short videos titled "EPISODIO COMPLETO" - already single episodes.
#   2. 6 long videos titled "...COMPLETOS" - real episodes, to be split.
# Everything else is best-of/song/funny-moment reels: fragments with no episode
# boundaries to find, duplicating what the COMPLETOS six already contain. That
# is ~70 h of download skipped for no loss.
export MATCHFILTER="!is_live & duration<=1800 & title~=(?i)episodio.?completo"
run_show "Dora la Exploradora" "https://www.youtube.com/playlist?list=PLXJZReOlh8yIRGXvKw-Enzn3MEqYWNymf"
export MATCHFILTER="!is_live & duration>5400 & duration<=17000 & title~=(?i)completos"
run_show "Dora la Exploradora" "https://www.youtube.com/playlist?list=PLXJZReOlh8yIRGXvKw-Enzn3MEqYWNymf"
unset MATCHFILTER

# --- Not television: their own channels -------------------------------------
run_show "Cosmic Kids Yoga" \
  "https://www.youtube.com/playlist?list=PL8snGkhBF7njrfPJ9g3bTmbR_Orc44o8_"
run_show "Spanish Basics" \
  "https://www.youtube.com/playlist?list=PLCGR7QYLeqvyk121oUP4e8333YVJc9q7x"
run_show "Aprende Peque con Isa" \
  "https://www.youtube.com/playlist?list=PLb8t9pce11B6fMs7tondof5y2C-G6xYFs"

# --- Cantonese learning: ONE channel for now ---------------------------------
# The uploader has already age-banded these into four playlists (0-3, 3-5, 6+,
# parent-child) and they land in one folder, so splitting them into separate
# channels later is a matter of moving files rather than re-downloading.
# Worth revisiting once there is a sense of which bands actually get watched.
#
# NOTE: the first non-Spanish content on the box. Nothing breaks - a channel is
# just a folder - but "everything is a Spanish dub" stops being true here.
run_show "Cantonés" \
  "https://www.youtube.com/playlist?list=PL6lk5soCGSstbGSMphkidzxiJ8ByLL1D3" \
  "https://www.youtube.com/playlist?list=PL6lk5soCGSsuhDlQrWpUX5k_VLdZu9QIQ" \
  "https://www.youtube.com/playlist?list=PL6lk5soCGSsvqzFfbgz8lAH1MyHt2-w4r" \
  "https://www.youtube.com/playlist?list=PL6lk5soCGSsstS7IVTO_3K8zUt_X4h9Jj"

# --- archive.org LAST, deliberately -------------------------------------------
# These two are the only sources here that are NOT geo-blocked: archive.org
# serves worldwide and needs no VPN. Everything above is YouTube and only works
# while the VPN holds an allowed exit, so it goes first. If the connection is
# lost or reshuffled to a blocked country, these two are unaffected and can be
# fetched at any time.
run_archive "Arthur" arthurT01LatCast ArthurT02LatCast ArthurtT03LatCast

# 57 of the 291-episode run, Cloverway LATAM dub, 480x360 - lower resolution
# than everything else here, but a period-correct 4:3 rip.
run_archive "Dragon Ball Z" DBZ-Cloverway-Episodes

# One item holds Latin Spanish, Mandarin and Italian side by side - without the
# filter this channel would change language between episodes.
export NAME_FILTER="latin spanish"
run_archive "Bear in the Big Blue House" BearintheBigBlueHouseLanguages
unset NAME_FILTER
say "QUEUE COMPLETE"
