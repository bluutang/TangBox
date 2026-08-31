# Session Wrap — 2026-08-31 (late)

## What we worked on
Organised the whole library into channel folders, added ten shows, split and
joined a great deal of video, and cut commercial breaks to 30-60s on the box.
Media lives in `~/Downloads/Converted/`; the repo only changed in
`config.pi.yaml`.

## Status right now
**Daniel Tigre is cutting** — 12 files into 30 pieces, from Brian's timemarks.
`Daniel Tigre/_reenc` opens by itself when it finishes. Nothing else is running.

## Next 1-3 steps
1. **Review and file three shows.** All cut and verified, none filed yet:
   - `Daniel Tigre/_reenc` — 30 pieces (when it finishes)
   - `NickJr/Dora la Exploradora/_reenc` — 35 pieces, 17.698 h in and out
   - `Pistas de Blue y tú/_bundled` — 12 episodes, 4.911 h in and out
2. **Daniel 076 pt02 is a DUPLICATE of S01E85.** Brian's cut is at 21:36 and the
   duplicate starts ~22:26, so pt02 contains it from ~50s in. Check before
   keeping.
3. **Pistas: 22 compilations in `_compilations/` need split points** (18.7 to
   62.4 min, four near an hour). Brian is finding them. Two things to spot:
   `40 MIN de fiesta con Blue y Josh` appears TWICE at exactly 40.0 min, and
   `¡30 minutos de las canciones…` actually runs 18.7 min.

## Where things stand
- **2,428+ episodes across 24 channels.** 92 GB free; another ~20 GB frees once
  the three shows above are filed and their working folders swept.
- **Colour tags live in Finder AND on the tracker.** `_status.html` shows each
  show's channel before its source, plus badges matching the tags.
      python3 _tools/tag-incomplete.py --apply   # red = barely started, orange = partial
      python3 _tools/tag-artwork.py --apply      # purple = no tile.jpg
- **19 shows have no tile picture**, across 12 channels - almost all added in the
  last two sessions. `artwork.py`: the guide draws one tile per channel and
  neither child can read, so the picture IS the tile. No tile = a blank on the dial.
- Daniel left 5 files whole as episodes (024, 030, 033, 035, 061 — 31-37 min).

## Decisions made
- **Channels 19-23**: Anime Kids (Digimon+Pokémon, 6+, off the 10+ Anime block);
  Aprende/Ejercicio/Cantonés/Journey moved to the end of the dial.
- **Commercial breaks 30-60s** (was up to 3m45). LIVE on the Pi — its own
  `config.yaml` at `/home/brian/TangBox/`, service `tangbox.service`.
- **Spanish Basics renamed Ms. Nenna**, complete at 22 (one video unavailable).
- **Pistas de Blue has no real episodes** — clips bundled into ~22-min blocks;
  the short tail was folded into E08 (32.8 min) rather than left as a stub.
- **Barney and Dora get NO invented commercial breaks.** Brian scrubs playback;
  automated detection cannot match it (see below).
- Jorge's `NA-XBSF8xSNt2g` has no findable boundary — preserved in `_unsplit/`.

## Bugs found — do not reintroduce
- **ffmpeg concat truncates SILENTLY on an apostrophe in a filename.** The list
  format is `file '...'`, so `Blue's Clues & You!` ends the string early: valid
  short file, exit 0, no error. Escape as `'\''`. Cost three rebuilds; the first
  "fix" had one backslash too many and looked identical.
- **`curl` without `-L`** wrote 65 zero-byte files matching the target count.
- **`get-archive.py` picked ONE format label** and fetched 1 episode of 50.
- **No folder, no download** — a redirect into a missing folder makes the fetch
  never run; the pass reports 0 and moves on.
- **Editing a running bash script** breaks it (bash reads by byte offset).
- **A filename check is not a duration check** — Dora's 4h26m "episode" filed
  itself. `file-shows.py` now refuses anything over 45 min.
- **"ffmpeg decodes it" is not "it plays"** — two Barney files decoded clean and
  would not play. The person watching is the authority.
- **Appending new episodes past the highest number ignores the gaps.** Ms. Nenna's
  ten went in as E24-E33 when the gaps at E07-E17 were their real positions.

## The lesson that kept repeating
**A tool reporting success is not evidence it did the job.** Five times today:
zero-byte files matching the expected count, 1 episode of 50, a 4h26m "episode"
filing itself, concat dropping 19 minutes, and a credit-detection "match" that
cut mid-episode. Every one had a clean exit code. Only comparing input duration
against output duration — or looking at an actual frame — caught them.

**And verify every result, not a sample.** Two credit breaks survived the strict
threshold for Dora; I frame-checked one (correct) and offered the other on the
score alone. Brian found it cut an episode in half. It has been merged back.

## Detection notes
- **Jorge boundaries come three ways**: white title card (27), black gap (028),
  yellow bumper (029). One detector always misses some.
- **Dora marks boundaries with CREDITS** (2 black frames in 45 min). Credits are
  pale blue and so is sky: 8s matches are noise, real rolls run 20-34s. Eight of
  ten first-pass suggestions were false positives; of the two survivors, one was
  also wrong. 11 Dora pieces remain over 30 min with no reliable break found.
- **Barney compilations have NO act breaks** — 54 scene changes per 10 min
  against 4 silences. Continuous montage.
- **Rocket Power self-confirmed**: three files never compared produced boundaries
  agreeing within 2 seconds.
- **The tracker's process check has been widened five times** — yt-dlp, then
  archive.org, curl, ffmpeg ("splitting"), and finally the process WORKING
  DIRECTORY, because a job that `cd`s into a show folder never names it.

## Open questions
- Two tokyvideo user pages need the Chrome extension or a CSV export — the site
  has no URL pagination, so 24 videos is the fetch ceiling.
- The Google Sheet's `show` column made adding five shows trivial. Keep it.
- Deletions used `rm -rf`, which bypasses the Trash.

## How to resume
Start a fresh session (don't click "Keep full session"). Then say:
> "read SESSION-WRAP.md and continue."
