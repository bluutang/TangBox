# Session Wrap — 2026-08-31

## What we worked on
Finished the Jorge repair, downloaded ten new shows, and organised the whole
library into channel folders. **2,428 playable episodes across 24 channels**,
60 GB free. Media lives in `~/Downloads/Converted/`; the repo only changed in
`config.pi.yaml`.

## Status right now
Three jobs running unattended, watched by one monitor:
- **Dora** cutting 6 marathons into 36 pieces (`_dora-cut.log`)
- **Pistas de Blue** bundling 59 clips into 13 blocks (`_bundle.log`)
- **Ms. Nenna** fetching its last 6 videos at 360p (`_nenna.log`)

Both folders open automatically when their job finishes, for review.

## Next 1-3 steps
1. Review Dora's 36 pieces and Pistas' 13 blocks when they open.
2. **Daniel Tigre's 17 compilations still need split timemarks** — the only show
   left needing them.
3. `NA-XBSF8xSNt2g` (Jorge) has no findable boundary and is still unsplit.

## Decisions made
- **Channels 19-23 added/renumbered**: Anime Kids (Digimon+Pokémon, 6+, split off
  the 10+ Anime block), then Aprende/Ejercicio/Cantonés/Journey at the end.
- **Commercial breaks are 30-60s**, down from up to 3m45. Live on the box.
- **Spanish Basics renamed Ms. Nenna** (the creator).
- **Street Sharks → Disney Acción**; Gargoyles and Mighty Ducks too (146 eps).
- **Pistas de Blue has no real episodes** — 60 clips + compilations. Clips are
  bundled into ~22-min blocks; the 30-min compilations stay whole.
- **Barney's long pieces get no invented commercial breaks.** Brian scrubbed the
  playback himself; automated detection could not match it (see below).

## Bugs found — do not reintroduce
- **ffmpeg concat truncates SILENTLY on an apostrophe in a filename.** The list
  format is `file '...'`, so `Blue's Clues & You!` ends the string early: valid
  short file, exit code 0, no error. Escape with `'\''`. Cost two rebuilds.
- **`curl` without `-L`** wrote 65 zero-byte Arthur files that matched the target
  count exactly. `--fail` does not catch redirects.
- **`get-archive.py` picked ONE archive.org format label** and fetched 1 episode
  of 50 while reporting success. Dedupe by episode name, not by label.
- **No folder, no download**: a redirect into `$show/_download.log` fails if the
  folder does not exist, so the fetch never runs and the pass reports 0.
- **Editing a running bash script** breaks it - bash reads by byte offset.
- **`pgrep -f` matches your own monitor**, and a `bash -c` wrapper naming three
  shows marks all three busy. Match real workers only.
- **exFAT forbids `?`** and archive.org names contain it.
- **A filename check is not a duration check** - Dora's 4h26m "episode" filed
  itself because the NAME matched. `file-shows.py` now refuses anything >45 min.
- **"ffmpeg decodes it" ≠ "it plays"** - two Barney files decoded clean and would
  not play for Brian. The person watching is the authority.

## Detection notes worth keeping
- **Jorge boundaries come three ways**: white title card (27 files), black gap
  (028), yellow bumper (029). One detector always misses some.
- **Dora marks boundaries with CREDITS, not black** - 2 black frames in 45 min.
  Credits are pale blue, and so is sky: 8-second matches are noise, real credit
  rolls run 20-34s. Eight of ten first-pass suggestions were false positives.
- **Barney compilations have no act breaks at all** - 2 black frames in 85 min,
  no credit roll, 54 scene changes per 10 min against 4 silences. Continuous
  montage. Scrubbing is the only reliable way to mark these.
- **Rocket Power's specials self-confirmed**: three files never compared with
  each other produced boundaries agreeing within 2 seconds.

## Open questions / blockers
- Daniel Tigre timemarks (17 files). File 076 is HALF duplicate - cut ~22:26,
  keep the first piece only.
- Pistas `S01E09` is 9.3 min: the tail of the 23.976 fps group, and the rest of
  the clips are 25 fps so nothing can pad it without a re-encode.
- The Google Sheet now has a `show` column - keep it, it made adding 5 shows
  trivial where the previous sheet needed five separate URL parsers.
- Two tokyvideo user pages (more Gargoyles etc.) still need the Chrome extension
  or a CSV export; the site has no URL pagination, 24 videos is the fetch ceiling.

## How to resume
Start a fresh session (don't click "Keep full session"). Then say:
> "read SESSION-WRAP.md and continue."
