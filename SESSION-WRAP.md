# Session Wrap — 2026-08-31 (late)

## What we worked on
Organised the whole library into channel folders, added ten shows, split and
joined a great deal of video, and cut commercial breaks down to 30-60s on the
box. Media lives in `~/Downloads/Converted/`; the repo only changed in
`config.pi.yaml`.

## Status right now
**Dora is still cutting** — 6 marathons into 36 pieces, ~19 done. The folder
`NickJr/Dora la Exploradora/_reenc` opens by itself when it finishes. Nothing
else is running.

## Next 1-3 steps
1. **Daniel Tigre: 17 compilations need split timemarks.** The only show still
   waiting on them. File 076 is HALF duplicate — cut ~22:26 and keep the FIRST
   piece only (its second half is S01E85, already held).
2. **Review and file Pistas de Blue's 13 bundles** in `_bundled/`. Verified
   exact: 4.911 h in, 4.911 h out.
3. **Review Dora's 36 pieces** when the folder opens, then file them.

## Where things stand
- **1710/1710** registered episodes downloaded. But the registry post-dates much
  of the library: the tagging pass is the truer picture — **17 show folders are
  incomplete**, 14 of them sitting on exactly ONE episode across six channels.
- **Colour tags are live in Finder.** Red = barely started, Orange = partial;
  channel folders take the worst tag inside them. Re-run any time:
  `python3 _tools/tag-incomplete.py --apply` (dry run by default). It clears
  tags from anything that has since completed.
- 92 GB free after deleting 32.8 GB of superseded working files. Roughly another
  20 GB frees up once Dora, Daniel and Pistas are filed.

## Decisions made
- **Channels 19-23**: Anime Kids (Digimon+Pokémon, 6+, split off the 10+ Anime
  block); Aprende/Ejercicio/Cantonés/Journey moved to the end of the dial.
- **Commercial breaks 30-60s** (was up to 3m45). LIVE on the Pi — its own
  `config.yaml` at `/home/brian/TangBox/`, service `tangbox.service`.
- **Spanish Basics renamed Ms. Nenna**; now complete at 22/23 (one video is
  unavailable on YouTube, so 22 is the ceiling).
- **Pistas de Blue has no real episodes** — 60 clips plus compilations. Clips are
  bundled into ~22-min blocks; the 30-min compilations stay whole.
- **Barney's long pieces get NO invented breaks.** Brian scrubbed the playback;
  automated detection could not match it.
- Jorge's `NA-XBSF8xSNt2g` has no findable boundary — preserved in `_unsplit/`.

## Bugs found — do not reintroduce
- **ffmpeg concat truncates SILENTLY on an apostrophe in a filename.** The list
  format is `file '...'`, so `Blue's Clues & You!` ends the string early: valid
  short file, exit 0, no error. Escape as `'\''`. Cost three rebuilds, and the
  first "fix" had one backslash too many and looked identical.
- **`curl` without `-L`** wrote 65 zero-byte files matching the target count.
- **`get-archive.py` picked ONE format label** and fetched 1 episode of 50.
- **No folder, no download** — a redirect into a missing folder makes the fetch
  never run, and the pass reports 0 and moves on.
- **Editing a running bash script** breaks it (bash reads by byte offset).
- **A filename check is not a duration check** — Dora's 4h26m "episode" filed
  itself. `file-shows.py` now refuses anything over 45 min.
- **"ffmpeg decodes it" is not "it plays"** — two Barney files decoded clean and
  would not play. The person watching is the authority.
- **Appending new episodes past the highest number ignores the gaps.** Ms. Nenna's
  ten went in as E24-E33 when the gaps at E07-E17 were their real positions.

## Detection notes
- **Jorge boundaries come three ways**: white title card (27), black gap (028),
  yellow bumper (029). One detector always misses some.
- **Dora marks boundaries with CREDITS** (2 black frames in 45 min). Credits are
  pale blue and so is sky: 8s matches are noise, real rolls run 20-34s. Eight of
  ten first-pass suggestions were false positives.
- **Barney compilations have NO act breaks** — 54 scene changes per 10 min
  against 4 silences. Continuous montage; scrubbing is the only way.
- **Rocket Power self-confirmed**: three files never compared produced boundaries
  agreeing within 2 seconds.
- **The tracker's process check has been widened five times** — yt-dlp, then
  archive.org, curl, ffmpeg ("splitting" state), and finally the process WORKING
  DIRECTORY, because a job that `cd`s into a show folder never names it.

## Open questions
- Two tokyvideo user pages still need the Chrome extension or a CSV export — the
  site has no URL pagination, so 24 videos is the fetch ceiling.
- The Google Sheet's `show` column made adding five shows trivial. Keep it.
- Deletions used `rm -rf`, which bypasses the Trash. Say so if you would rather
  they were recoverable.

## How to resume
Start a fresh session (don't click "Keep full session"). Then say:
> "read SESSION-WRAP.md and continue."
