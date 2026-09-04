#!/bin/bash
# Retry the 7 Daniel Tigre videos that failed on transient network errors, then
# hand back to the normal queue (Franklin resumes first, then Barney/Jorge/Blue).
# Only the 7 are fetched: the other 54 are in _archive.txt and get skipped.
cd "/Users/briantang/Downloads/Converted" || exit 1
say() { echo "[$(date '+%H:%M:%S')] $*"; }
say "=== Daniel Tigre retry (54 already in archive, will be skipped)"
./_tools/get-playlist.sh "Daniel Tigre" \
  "https://www.youtube.com/playlist?list=PLpX4BrBayzzpPvu58ut-HfqfFlpaMVXGE" \
  >> "Daniel Tigre/_download.log" 2>&1
say "--- Daniel Tigre now at $(wc -l < 'Daniel Tigre/_archive.txt' | tr -d ' ') videos"
say "=== handing back to the queue (Franklin first)"
exec ./_tools/run-queue.sh
