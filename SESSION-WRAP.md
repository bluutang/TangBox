# Session wrap — 11 shows queued, channel design decided (2026-08-28)

Downloads run without Claude. **Check them at
`/Users/briantang/Downloads/Converted/_status.html`** — self-refreshing: episodes,
GB, live speed, ETA, and catalogue size against the 1 TB drive.

    running now   ps -Ao args= | grep -E '[y]t-dlp|run-[q]ueue'
    queue log     tail -f ~/Downloads/Converted/_queue.log
    stop the queue  kill the run-queue pid; then kill yt-dlp BY SHOW NAME
    resume        cd ~/Downloads/Converted && nohup ./_tools/run-queue10.sh >> _queue.log 2>&1 &

## Where the downloads are — 271 / 748, catalogue 229 GB (23% of 1 TB)

| Show | State |
|---|---|
| **Franklin** | ✅ 78/78 — downloaded, named, filed in `Franklin/Season 01/` |
| **Daniel Tigre** | ✅ 61/61 (in `_staging`, unnamed) |
| **Barney el Dinosaurio** | ✅ 41/41 (in `_staging`, unnamed) |
| Jorge el Curioso | 29/34 — 5 geo-blocked, see below |
| Pistas de Blue y tú | 62/82 — downloading |
| Clifford | 0/77 |
| El Autobús Mágico | 0/50 (episodes only) |
| Arthur | 0/65 (archive.org) |
| Sailor Moon | 0/200 (5 seasons, the complete run) |
| Sailor Moon Películas | 0/3 (films, own folder — see the split rule) |
| Dragon Ball Z | 0/57 (archive.org, 480x360) |

## 🔴 VPN — the single biggest time sink

Spanish dubs licensed to ~212 countries. **Currently on Canada, which works for
everything except 5 Jorge videos.** Poland/USA/Germany/France are blocked for the
main catalogue; Mexico, Spain, Canada, UK and Latin America work.
Speed also matters hugely: Poland ~214 KB/s vs **Canada ~5.4 MB/s (25x)**.

- After ANY server change: **`_tools/check-vpn.sh`** — one probe per show, verdict
  in seconds.
- **`_tools/blocked.py`** — lists every geo-blocked video still missing AND
  intersects the "available in" country lists to name servers that would unblock
  them ALL. `--retry` re-fetches only those, no playlist re-walk.
- Right now: **5 Jorge videos blocked; 259 countries would fix them**, including
  Mexico, Spain, UK, Japan — and even Poland/Germany/France. Those five have a
  WIDER rights set than the rest; Canada is the odd exclusion.
- The failure is QUIET: `--ignore-errors` skips blocked videos and yt-dlp often
  reports a bare `Video unavailable` (normally meaning *deleted*). **Watch the
  episode count, not the log.**

## 🔴 Splitting: when it is safe, and when it destroys the thing

**Commercial breaks only ever happen BETWEEN files.** A break "inside" long
content means cutting it up. That is safe ONLY when each piece stands alone.

- **Compilations** (Daniel Tigre, Jorge, Barney) hold several *separate*
  episodes. Cut them and each piece is a whole episode — shuffle order is
  harmless. ✅
- **A film is one continuous story.** Split it under `shuffle` and part 2 plays
  days before part 1. `sequential` does not save it either: that bags the SHOWS
  and hands you the next file of one, so the next draw is a DIFFERENT show —
  half a film, something else, then the other half. ❌
- **The exception**: a film CAN be split if it is on a channel where its folder
  is the ONLY show. Sequential then draws that show every time and walks
  `pt01 → break → pt02` back to back. This is why the Sailor Moon films were
  un-merged into `Sailor Moon Películas/`.
- Their channel therefore NEEDS `episode_order: sequential` and
  `tune_in: resume`. **Write the channel config BEFORE cutting the films** — split
  files on a default shuffled channel are worse than unsplit ones.

## Jorge cuts — reviewed, NOT yet correct

All 34 are compilations; ~45:07 = two ~22-min episodes. **Zero chapter coverage**
across 27 videos, so `detect-breaks.py` is the only method.

Working settings: `--black-d 0.05 --pix-th 0.35 --black-only`
- `--black-only` because the joins fade the picture while music runs across them,
  so "black AND silent" never fires.
- `--pix-th 0.35` because the fades never reach full black, and vary between
  files (001 showed at 0.20, 002 needed 0.35).

Five files all cut at 22:10–22:11 into ~22:10 + ~22:57. **But the cut is wrong.**
Brian diagnosed it: the episode ends on a black frame and the CREDITS come after
it. So the detector fires on the story's end, and episode 1's credits + the
yellow "¡No te vayas!" interstitials land on the head of piece 2.

**Do not batch-run Jorge until this is fixed.** The fix is to cut at the end of
the credits block. Two of my contact sheets disagreed on where that is (I used
`-ss` before `-i`, which seeks to the nearest keyframe and is not frame-accurate;
`-ss` AFTER `-i` is). **Do not guess an offset — detect the yellow interstitial
cards by average frame colour**, which is deterministic and works on every file.

The 10 files in `Jorge el Curioso/_review/` are EVIDENCE, not output. Sources
untouched; delete and re-cut freely.

> **Lesson worth keeping:** five files agreeing on a timestamp proved the detector
> was *stable*, not *correct*. Only the visual check found the error. Always look
> at a frame before recommending a batch run.

## Tools (all in `Converted/_tools/`)

| File | Does |
|---|---|
| `get-playlist.sh` | YouTube playlist → `_staging`. H.264, ≤1.5 h, resumable. `$MATCHFILTER` overrides the filter, `$PLAYLIST_ITEMS` picks positions. |
| `get-archive.py` | archive.org → `_staging`. Picks the best format the item has (h.264 → MPEG4 → Matroska), ONE file per episode. |
| `run-queue10.sh` | One show at a time, **retried until it stops making progress**. |
| `detect-breaks.py` | Finds joins; `--black-only`, `--pix-th`, `--split`. |
| `name-from-titles.py` | Names staged files from YouTube titles. Dry-run by default. |
| `check-vpn.sh` | Is this VPN exit allowed? |
| `blocked.py` | Geo-blocked videos + which countries unblock them all. `--retry`. |
| `check-exfat.py` | Every name legal on the USB drive? **Re-run before copying.** |
| `status.py` / `watch-status.sh` | Regenerate `_status.html`. |

## Decisions

- **Discard anything over 1.5 h** (`duration<=5400`). Those were compilations
  repackaging episodes held elsewhere.
- **A 20–25 min piece is a finished episode**, even when it is two shorts joined.
  `--min-episode` 18 min; Franklin is never split.
- **El Autobús Mágico: episodes only** — its 41 compilations are ~46 h duplicating
  the 50 standalone episodes.
- **Sailor Moon films: 3, not 6** — the playlist holds each film twice under a
  different title. `PLAYLIST_ITEMS="1-3"`.
- **YouTube titles ARE allowed in filenames.** The no-titles rule bans *looked-up
  database* titles (the Rugrats problem); a YouTube title comes from the video
  itself and cannot be mismatched.
- **Multiple titles separated by fullwidth ｜ (U+FF5C), never ASCII `|`** — the USB
  is exFAT (README Part E) and exFAT forbids `" * / : < > ? \ |`.
- **Do not rebalance channels on episode count** — Brian is filling the thin ones.

## Still to do

1. Finish the queue; then `blocked.py --retry` after switching off Canada.
2. **Fix the Jorge cut** (yellow-card detection), then split all 34.
3. **Clifford**: 52 full episodes stay; 24 halves (10:34–12:40) **pair into 12**
   (~22:48) with `mkv2mp4/join_segments.py` — it did Dexter 47→18. Check titles
   first; real broadcast pairs may be reconstructable.
4. **Blue's Clues**: 56 clips joined *up* into ~52 episodes.
5. **Sailor Moon films**: split each ~60 min in half at a scene boundary — AFTER
   their channel exists with sequential + resume.
6. **Name** remaining shows with `name-from-titles.py` (dry-run first).
7. **Dedupe by content**, especially Daniel Tigre.
8. **Sheet**: Daniel Tigre (row 40), Barney (row 6) still `Wanted`; Franklin row 74
   says 41, should be 78; Sailor Moon (row 7) `Wanted`, 200 eps — now downloading.
9. **Write the channel config** (below).
10. **Copy to USB**, re-running `check-exfat.py` first.

## Channel lineup — DECIDED, not yet written

17 channels. **Every channel is ONE network/platform**; age splits each block.
`path:` must be **ASCII only** (macOS/Linux disagree on accent encoding).
Sailor Moon (200) + Dragon Ball Z (57) turn channel 18 from 1 episode into 257.

| Block | Ch | Channel | path | Age | Shows |
|---|---:|---|---|---|---|
| PBS | 2 | PBS Pequeños | PBSPequenos | 1-2 | Plaza Sésamo · Barney · Teletubbies |
| | 3 | PBS Kids | PBSKids | 2-4 | Daniel Tigre · Jorge el Curioso |
| | 4 | PBS Escolar | PBSEscolar | 4-8 | Arthur · Clifford · El Autobús Mágico |
| Nick | 5 | Nick Jr | NickJr | 2-5 | Franklin · Pistas de Blue y tú |
| | 6 | Nick Clásico | NickClasico | 5-8 | Rugrats · ¡Oye Arnold! · Doug |
| | 7 | Nick Moderno | NickModerno | 5-8 | Bob Esponja · Jimmy Neutron |
| | 8 | Nick Acción | NickAccion | 7+ | Avatar |
| Disney | 9 | Disney Jr | DisneyJr | 2-5 | Bluey · Spidey |
| | 10 | Disney | Disney | 6-9 | Kim Possible · Recreo · Pepper Ann |
| | 11 | Disney Aventura | DisneyAventura | 6-9 | Patoaventuras · Lilo y Stitch · Tres Caballeros |
| | 12 | Disney Acción | DisneyAccion | 7+ | Spider-Man · **Jake Long** |
| CN | 13 | Cartoon Network | CartoonNetwork | 6-10 | Dexter · Ed, Edd y Eddy · Escandalosos · KND |
| Apple | 14 | Apple Snoopy | AppleSnoopy | 3-6 | Camp Snoopy · Snoopy el astronauta · El show de Snoopy |
| | 15 | Apple Cuentos | AppleCuentos | 3-6 | Lago tranquilo · Sapo y Sepo · El niño lobo · Pato y Ganso |
| Netflix | 16 | Netflix Kids | NetflixKids | 4-8 | Misterios Animales · My Melody · Concierge Pokémon |
| | 17 | Netflix Cuentos | NetflixCuentos | 3-7 | Los guardaespíritus · Tibucán · Maya · Dr. Seuss |
| Anime | 18 | Anime | Anime | 10+ | Sailor Moon · Dragon Ball Z |
| Cine | 19 | Cine | Cine | 7+ | Sailor Moon Películas — **sequential + resume** |

`config.pi.yaml` still holds the OLD 5 channels, superseded by
`docs/superpowers/specs/2026-08-20-channel-numbering-design.md` and never
rewritten. It also cites a **different spreadsheet id** (`1fb_Xrny0G…`) than the
live one (`17ZosBycj…`).

## Code shipped

- `4e1b936` — `ChannelConfig.age` (`age: "2-4"`), drawn under the name on the
  channel banner.
- `b327d77` — guide detail row: one line under the grid giving the focused
  channel's age and shows. **Under the grid, not on tiles, because a tile with
  artwork draws no ASS at all** (mpv puts bitmaps above ASS, so its text is burned
  into the picture).

**Both inert until wired.** `app.py` does not pass `ages`/`shows` into
`guide_ass`, and no channel declares an `age:`. Both light up with the config
rewrite; `shows` can come from listing each channel folder's subdirectories,
computed once at start-up. **630 tests pass.**

## Gotchas — each of these cost real time

- **`pkill -f` matches your own shell.** A pattern appearing anywhere in the same
  command kills the command. Happened 3x (exit 144). Kill in a SEPARATE call from
  any that names the script, or match `run-[q]ueue` and reference the file by a
  glob that avoids the literal (`run-*ueue10.sh`).
- **Killing a wrapper does not kill `yt-dlp`** — its args hold the URL and output
  path, not the script name. **Kill by SHOW NAME.**
- **Progress lines use `\r`.** `grep '^ERROR'` misses errors glued to a progress
  line; `[N/M] file` entries get overwritten. `tr '\r' '\n'` first. This hid an
  error AND a filename on separate days.
- **`ffmpeg -ss` BEFORE `-i` is not frame-accurate** (seeks to nearest keyframe).
  Put `-ss` AFTER `-i` when the timestamp matters. This produced two contradictory
  contact sheets.
- **`ffmpeg` inside a `while read` loop eats the loop's stdin.** Add `</dev/null`.
- **zsh aborts a loop on an unmatched glob** and does NOT word-split unquoted
  variables (bash does).
- **Python buffers stdout** when not a tty — background jobs look empty until done.
- `du` sees a growing `.part` in ~1 MB steps, so short samples quantise to
  0/102/204 KB/s. Speed 0 does not mean stalled.

## Carried over — still outstanding

**Plaza Sésamo (80 episodes, 14 GB) has never been moved to the USB drive.** Also:
`Lineup` L2/M2 hold *US Sesame Street* totals so its bar reads 80/4662; and the
`Seasons breakdown` tab documented in CLAUDE.md does not exist in the spreadsheet.

## Repo

Clean apart from this file. Two commits pushed to `main`. All media work lives in
`~/Downloads/Converted/`.
