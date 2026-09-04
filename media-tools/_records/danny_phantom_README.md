# Danny Phantom — parked 2026-09-03

12 of 49 episodes downloaded (indices 3,4,5,16,20,21,22,29,30,39,48,49).

## Why it stopped
VidHide (dhtpre.com) serves the embed page and the m3u8 playlists fine, but its
ORIGIN returns HTTP 522 on every media segment, and both mirrors return 502.
Verified repeatedly across 2026-09-01 → 09-03. Nothing on this end affects it:
the page loads, the playlist enumerates 145 segments, only the segments fail.
A VPN does not help — 522 is Cloudflare failing to reach the backend.

## To resume
1. Test the host first:  python3 _tools/dhtpre.py https://dhtpre.com/embed/9d52hw5afm54
   If it prints links AND a segment fetch succeeds, the host is back.
2. Episode list + embed URLs: danny_phantom_episodes.tsv (49 rows).
3. Which 12 already existed: danny_phantom_download_log.jsonl.
4. Registered in _tools/shows.json as "Danny Phantom", 49 videos.

## ⚠️ The 12 downloaded episodes were NOT re-obtainable at park time.
These records let you RETRY; they do not guarantee recovery. If those 12 files
were deleted, they can only come back if VidHide's origin recovers.
