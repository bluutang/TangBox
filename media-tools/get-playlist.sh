#!/bin/bash
# Download a YouTube playlist into a show's resumable staging folder.
#   usage: get-playlist.sh "Show Name" "https://youtube.com/playlist?list=..."
#
# Everything is downloaded (no duration filter) - long compilations get split
# into episodes later by detect-breaks.py. Re-running is safe and cheap: the
# _archive.txt file records finished video IDs and they are never re-fetched,
# so both playlists of a show can share one archive and dedupe automatically.
set -uo pipefail

SHOW_NAME="${1:?usage: get-playlist.sh \"Show Name\" PLAYLIST_URL}"
URL="${2:?usage: get-playlist.sh \"Show Name\" PLAYLIST_URL}"

ROOT="/Users/briantang/Downloads/Converted/$SHOW_NAME"
STAGE="$ROOT/_staging"
mkdir -p "$STAGE"

# Filenames carry the VIDEO TITLE as well as the index and id. The no-titles
# rule bans LOOKED-UP database titles matched to episodes by guesswork - the
# thing that put wrong names on 246 files. A YouTube title ships with the video
# and cannot be mismatched, so it is safe and useful. The index keeps sort order
# and the id keeps the file traceable. yt-dlp sanitises illegal characters
# itself, including turning "|" into the fullwidth "｜" that exFAT accepts.
#
# H.264 ONLY. yt-dlp's default "best" serves AV1, and the Pi 5 has no AV1
# hardware decoder - AV1 files play as a slideshow or not at all.
yt-dlp \
  --ignore-errors \
  --no-abort-on-error \
  --match-filter "${MATCHFILTER:-!is_live & duration<=5400}" \
  -f "bestvideo[vcodec^=avc1][height<=720]+bestaudio[ext=m4a]/best[vcodec^=avc1][height<=720]/best[height<=720]" \
  --merge-output-format mp4 \
  ${PLAYLIST_ITEMS:+--playlist-items "$PLAYLIST_ITEMS"} \
  --download-archive "$ROOT/_archive.txt" \
  --no-overwrites \
  --retries 10 --fragment-retries 10 \
  --socket-timeout 30 \
  --sleep-requests 1 \
  -o "$STAGE/%(playlist_index)03d-%(id)s - %(title)s.%(ext)s" \
  "$URL"

echo "=== $SHOW_NAME staged: $(find "$STAGE" -name '*.mp4' ! -name '*.f[0-9]*.mp4' | wc -l | tr -d ' ') files"
