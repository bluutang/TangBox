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

# Wait for whatever is downloading right now (Franklin) to finish its current pass.
if pgrep -f "get-playlist.sh" >/dev/null; then
  say "waiting for the in-flight download to finish..."
  while pgrep -f "get-playlist.sh" >/dev/null; do sleep 20; done
fi

# ORDER: shows with MEASURED geo-block exposure go first, because that content is
# only reachable while the VPN holds. Franklin lost 31 of 78 with the VPN off and
# Jorge 14 of 36; Barney and Blue's Clues have never been measured without it, so
# they go last - if the VPN drops, they are the cheapest to lose and re-run.
run_show "Franklin"             "https://www.youtube.com/playlist?list=PLjXyTw1_uY7NQbTvTWChxk9Qax1_1cYbV"
run_show "Jorge el Curioso"     "https://www.youtube.com/playlist?list=PL08EcHdANEaXYGEyezJCK4Lhtrhci_8oy"
run_show "Barney el Dinosaurio" "https://www.youtube.com/playlist?list=PLo-9TxilbtVEZ74l01fUbpZaK1N0omMpx" \
                                "https://www.youtube.com/playlist?list=PLo-9TxilbtVHm4DiE9hOGiZJ0QTb6JNkh"
run_show "Pistas de Blue y tú"  "https://www.youtube.com/playlist?list=PLaOguQAAiJUgdKXQXiWXml9XR7pEAmGCU"
run_show "Clifford"             "https://www.youtube.com/playlist?list=PL0l-iX-OLQy6ac8BlVaA_sDrVPjSp8xTd"
# El Autobus Magico: EPISODES ONLY. The playlist also holds 41 compilations of
# ~1:12 each, but the series only ran 52 episodes - those bundles are the same
# 50 standalone episodes re-cut, ~46 hours of pure duplication. Brian's call.
export MATCHFILTER="!is_live & duration>=900 & duration<=1800"
run_show "El Autobús Mágico"     "https://www.youtube.com/playlist?list=PL-czBqyTAEBMY_UFV76BqqTT_bcUIdhQW"
unset MATCHFILTER
# Sailor Moon: five season playlists into ONE folder, so the shared _archive.txt
# dedupes anything that appears twice. 200 episodes = the complete run.
# GEO-BLOCKED FIRST, so the VPN can come off as early as possible.
# Primera Temporada, R and S are blocked from the US; Super S and Sailor Stars
# are not. Fetched as separate passes into the SAME folder so the queue log
# says plainly when the blocked ones are finished.
#   blocked seasons: 46 + 43 + 38 = 127 episodes, plus the 3 films = 130.
#   Once Sailor Moon reaches 127 and Peliculas 3, nothing left needs the VPN.
say ">>> Sailor Moon PELICULAS - geo-blocked, VPN required (3 films, ~700 MB)"
# Only 2 of the 3 films are obtainable. "La promesa de la rosa" (Sailor Moon R)
# was taken down by a Viz Media copyright claim - BOTH uploads of it, so the
# duplicate at position 4 is gone too. Not a retry or VPN problem; it is simply
# not on this playlist any more. Sourced elsewhere or not at all.
export PLAYLIST_ITEMS="1-3"
run_show "Sailor Moon Películas" \
  "https://www.youtube.com/playlist?list=PLEqar3fXvaZ7h5tFyMNeYAGq7NW1_HrMX"
unset PLAYLIST_ITEMS

say ">>> Sailor Moon: GEO-BLOCKED seasons (1, R, S) - VPN required"
run_show "Sailor Moon" \
  "https://www.youtube.com/playlist?list=PLEqar3fXvaZ4DoeyiaememvSOCXqR5RN8" \
  "https://www.youtube.com/playlist?list=PLEqar3fXvaZ5O_xb538TMCEcI-I5fnq9u" \
  "https://www.youtube.com/playlist?list=PLEqar3fXvaZ4roFjee8UHOtbk883D-f96"

# The three theatrical films, on their OWN channel so they can be split.
# Positions 1-3 only: the playlist holds each film TWICE, re-uploaded under a
# different title, and taking all six would put every film on twice.
#
# They are split so the box can go to a break inside a 60-minute film. That is
# only safe because they will be the only show on their channel: sequential
# order then draws that same show every time, so pt01 and pt02 play back to
# back. In a shuffled folder the halves would scatter - which is exactly why
# the compilations elsewhere could be split and a film cannot.
say ">>> BLOCKED SAILOR MOON CONTENT COMPLETE - the VPN is no longer needed"
say ">>> Super S and Sailor Stars follow and are NOT geo-blocked"
run_show "Sailor Moon" \
  "https://www.youtube.com/playlist?list=PLEqar3fXvaZ6tBoHddjxUu3VDrt5b3Tjj" \
  "https://www.youtube.com/playlist?list=PLEqar3fXvaZ6dg_XfDQei3CwMfEvGyd2x"
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
