# Session Wrap — 2026-08-30

## What we worked on
Finished the Jorge el Curioso repair (all 19 broken splits fixed, plus the 5
geo-blocked files that finally arrived), then spent most of the session
recovering a download pipeline that was silently failing, and added six new
shows. **No code in this repo changed** — everything lives in
`~/Downloads/Converted/`.

## Status right now
The **off-VPN queue is running unattended** (`_tools/offvpn-queue.sh`, log
`_offvpn.log`), ~12 hours of work at the measured 2.87 MB/s:
Journey to the West (42) → Rocket Power (62) → Digimon (105) → tokyvideo (353).
Check progress at `~/Downloads/Converted/_status.html` (refreshes itself).

Everything else is **done**: every YouTube show is complete except 6 Spanish
Basics episodes (see blockers).

## Next 1-3 steps
1. Let the off-VPN queue finish. Nothing to do.
2. Look at `Spanish Basics/_360p/001-OpC5Q90bxd4.mp4` and decide if 360p is
   acceptable. If yes, the remaining 6 need the VPN back on briefly.
3. Split `NA-XBSF8xSNt2g` (the one Jorge file with no findable boundary).

## Files touched this session (all in `~/Downloads/Converted/_tools/`)
- `get-archive.py` — **added `-L`** and exFAT filename sanitising
- `status.py` — 3 fixes: order by mtime, smoothed speed/ETA, archive.org shows
  no longer read "stopped"
- `get-playlist.sh` — filenames now carry the video title
- `detect-breaks.py` — re-encode bitrate 2500k → 800k
- `find-title-cards.py`, `cut-at.py`, `sailor-seasons.py`, `tokyvideo-plan.py`,
  `tokyvideo-get.py`, `backfill-titles.py`, `digimon-file.py` — new tools
- `shows.json` — 24 shows, each with a `source`; Digimon and Sailor Moon merged

## Decisions made
- **Jorge boundaries are found three ways**: white title card (27 files), black
  gap (028), yellow "¡No te vayas!" bumper (029). One detector will always miss some.
- **The 5 late Jorge files are a different edit** — 66 min, six stories, three
  episodes, no title cards. Not the same shape as the other 29.
- **Cut at the fade's END when re-encoding.** The old "cut at the middle" rule
  only existed because `-c copy` snapped backwards; it does not apply now.
- **Re-encode is a repair, not the default** — 800k (~2x source) is plenty.
- **Titles from YouTube/source URLs are safe.** The no-titles rule bans
  *looked-up* database titles matched by guesswork, not ones shipped with the file.
- **Cantonés is now "Uncle Calvin"** (the channel's creator). Channel path stays
  ASCII `Cantones`.
- **Sailor Moon is one show**: 5 seasons + Movies, 202 files. Third film is a
  genuine takedown — 2 of 3 is the ceiling.
- **Digimon Tamers skipped** — 85 GB for a 1080p upscale of SD material.

## Bugs found (each cost real time — do not reintroduce)
- **`curl` without `-L`** wrote 65 zero-byte Arthur files that a file-count check
  called "complete". `--fail` does not catch redirects.
- **No folder, no download**: `run_show` redirects into `$name/_download.log`
  before anything creates `$name`; seven shows silently downloaded nothing.
- **Editing a running bash script** breaks it — bash reads by byte offset. This
  killed the queue mid-run.
- **`pgrep -f` matched my own monitor**, idling a job for 47 minutes.
- **A 0.3s black-gap threshold hid two real boundaries** (both 0.28s).
- **"Video unavailable" ≠ removed.** YouTube says the same thing for
  region-locked content. Two Sailor Moon episodes I called permanently gone came
  down fine from Romania.
- **The VPN throttles ~29x.** Check it before blaming a server.

## Open questions / blockers
- 6 Spanish Basics episodes are owner-restricted (360p only) and need the VPN.
- `NA-XBSF8xSNt2g` has no black gap near 1979 or 2638 — needs a human eye.
- Jorge's repaired files are in `_reenc/`; the broken originals are still in
  `_split/`. **Nothing has been swapped in yet** — worth eyeballing one first.
- Files 012 and 013 share an 11-minute story. The other 27 are unchecked.
- The Google Sheet has not been updated: Jorge 29→38 pieces, and rows are
  missing for every new show.
- `/wrap` fails from this folder: the command lives at
  `~/BluuClaude/.claude/commands/wrap.md` (workspace), not in `tang-box/.claude/`.

## How to resume
Start a fresh session (don't click "Keep full session"). Then say:
> "read SESSION-WRAP.md and continue."
