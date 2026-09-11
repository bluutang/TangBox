# Session Wrap — 2026-09-11
> Written by: Claude Code (Sonnet 5) · Scope: tang-box

## ▶ READ THIS FIRST

The box itself wasn't touched this session (still on standby, as the 2026-09-07
session left it — 23 channels, 4,031 episodes). This session did two things:
cut Colourblocks at Brian's own splitpoints, and updated the Google Sheet to
match. Antigravity's channel-reorg work also progressed during this session but
**is still not committed** — see below before touching those files.

## 🔴 Antigravity — download done, commit still pending

Same three uncommitted files as last wrap (`config.pi.yaml`,
`media-tools/organize-channels.py`, `media-tools/shows.json`), still sitting
uncommitted at end of this session. What changed: Brian confirmed the Tumble
Leaf download/conversion finished and Antigravity filed the results —
`PrimeKids/Tumble Leaf/Season 01/` now has 52 episodes on the Mac, and
`shows.json`'s uncommitted diff already has a `"Tumble Leaf"` entry.

**But `config.pi.yaml`'s uncommitted diff does NOT mention Tumble Leaf** —
the box-side channel wiring isn't done yet, and nothing has been committed.
So the same rule from last wrap still applies: **before touching these three
files or the PrimeKids folder, check `git status` and `git log`.** If the diff
is gone or a new commit covers them, Antigravity finished cleanly. If it's
still sitting there uncommitted, leave it and ask Brian rather than guessing
how Tumble Leaf should be numbered or grouped.

## What this session did: Colourblocks cut at Brian's own splitpoints

Brian had watched all 39 raw compilation videos in
`BlocksUniverse/Colourblocks/_staging` himself and gave back exact cut
timestamps per file (one line per file, in `ls -1 *.mp4` order — 35 files with
one or more splits, 4 already single-episode length and marked "as is"). That
replaced the `detect-breaks.py` auto-scan started earlier in the session
(killed and its log deleted once Brian's numbers arrived — his own eyes beat
the black+silence heuristic here).

Result: **85 new episodes, `Colourblocks - S01E90.mp4` through `S01E174.mp4`**,
filed into `Season 01` (which already had 89). All confirmed H.264 with
sensible durations. The 39 raw sources were deleted after verification, on
Brian's go-ahead (freed 8 GB).

**Two bugs surfaced and got fixed before real damage, both now in
`docs/lessons.md` (committed, `70d4f4d`)**:
1. First cutting script re-sorted the file list with Python's `sorted()`,
   which collates differently than the `ls` order Brian's splitpoints were
   given against — silently paired the wrong splits to the wrong file. Caught
   on the very first item before anything got filed into `Season 01`. Fixed by
   hardcoding the exact `ls -1` order and validating it against disk as an
   NFC-normalized *set*, never re-deriving order.
2. The job (a 2+ hour hardware re-encode) got killed by macOS for memory
   pressure partway through, competing with Antigravity's concurrent Tumble
   Leaf conversion. Nothing was lost — items 1-30 had already filed cleanly —
   because the script was made resumable by counting already-filed episodes
   against item boundaries, not by assuming a file position.

**Sheet updated to match** (`TangBox Media Library`, spreadsheet
`17ZosBycj-9h-rPOxlbyKl0ZbghPSSr87pUSzDdKmjAo`):
* `Lineup` row 104 added for Colourblocks (didn't exist before). Episodes
  have = 174. Seasons/Total episodes left **blank on purpose**: the real
  CBeebies show (Blue Zoo, debuted 2022-09-12) is only 45 episodes / 2
  seasons per TheTVDB/Wikidata, and this library is YouTube-native
  compilation content re-cut to episode length, not the broadcast series
  1:1 — same treatment as Pistas de Blue y tú and Tom y Jerry, where a
  percentage against a real episode count would be meaningless.
* `Episodes` tab: 174 new rows added (`A1099:F1272`), one per file, numbers
  only (no titles — Named stays 0). No prior Colourblocks rows existed to
  preserve.

## How to resume

Start a fresh session and say:
> "read tang-box/SESSION-WRAP.md and continue."

First check whether Antigravity's channel-wiring work (`config.pi.yaml`) has
landed — `git status` and `git log --oneline -5`. If it has, the likely next
job is copying whatever's new (Tumble Leaf, and anything else Antigravity
filed) onto the USB drive and reconciling the sheet, same pattern as
2026-09-07 and this session's Colourblocks work. If it hasn't, there's nothing
else pending on the Colourblocks side — that work is finished and pushed.
