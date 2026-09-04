#!/bin/bash
# The 10 Spanish Basics videos the normal fetch cannot get.
#
# Their owner disabled off-site playback, so the default client returns
# "Video unavailable. Playback on other websites has been disabled by the video
# owner". The android/mweb clients CAN see them - but YouTube's SABR experiment
# hides every format except 18 (640x360 avc1), so 360p is genuinely all that is
# on offer. yt-dlp is already at the latest release (2026.08.19); this is not
# something an update fixes.
#
# Brian's call 2026-08-29: fetch them, but keep them OUT of the channel folder
# until he has looked at one on the television. Everything else on the box is
# 720p and these will be visibly soft.
#
# Still H.264, so the Pi hardware-decodes them fine (never AV1).
set -u
cd "/Users/briantang/Downloads/Converted/Spanish Basics" || exit 1
LOG="../_spanish-360.log"
say(){ echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }
mkdir -p _360p
say "=== Spanish Basics: the 10 embed-restricted videos, at 360p ==="
yt-dlp --ignore-errors --no-abort-on-error \
  --extractor-args "youtube:player_client=android" \
  -f 'best[vcodec^=avc1][height<=720]/best[height<=720]' \
  --merge-output-format mp4 \
  --download-archive _360p/_archive.txt --no-overwrites \
  --retries 10 --fragment-retries 10 --socket-timeout 30 --sleep-requests 3 \
  -o '_360p/%(playlist_index)03d-%(id)s.%(ext)s' \
  "https://www.youtube.com/playlist?list=PLCGR7QYLeqvyk121oUP4e8333YVJc9q7x" \
  >> "$LOG" 2>&1
n=$(ls _360p/*.mp4 2>/dev/null | wc -l | tr -d ' ')
say "=== got $n files into Spanish Basics/_360p (NOT filed into a channel) ==="
say "note: if this returned 0, YouTube's bot check is refusing this IP - retry later"
