# Session Wrap — 2026-09-01 (long evening session)

## What we worked on
Put the repo's 22-channel lineup live on the Pi, filed **eleven shows** into the
library, fixed silent audio on 60 files across 8 shows, and built a reusable
ok.ru resolver. Media lives in `~/Downloads/Converted/`; the repo itself only
gained this file (`_tools/okru.py` lives with the media, not in git).

## Status right now
**Nothing of mine is running.** Everything below is filed and verified.
The Pi is up, `tangbox.service` active, 22 channels, 146 commercials.

`~/Downloads/Cartoons/` is empty except **Danny_Phantom** — 12 finished episodes
against **175 orphaned `.part` fragments**, i.e. a download that died partway.
Not mine, untouched. Those partials are dead weight if that run is not resuming.

## Library: 63 shows, 3,441 episodes, 600 GB. 43 GB free.
**Every show has a tile. Every file is AAC. Zero unreadable files.**

## Next 1-3 steps
1. 🔴 **USB drive** — still the only thing between this library and a working TV.
   600 GB now. Needs **1 TB, exFAT, mounted at `/media/tangbox`**.
2. **Sheet owed ~11 `Lineup` rows and ~900 `Episodes` rows.** `workspace-mcp`
   timed out at session start and never reconnected all evening.
3. Decide the re-pulls below (Jake Long, Winnie, Lilo) — they need disk headroom.

## The channel scheme — RESOLVED, do not re-litigate
The repo's `config.pi.yaml` (22 channels) won; the Pi's old 10-channel config
predated the library. Backed up to `config.yaml.bak-20260901-084639`, `git pull`
(it was 13 files behind), copied over with the `assets_dir` line carried across.

⚠️ `episode_order` is a RED HERRING. Both configs set `tune_in: broadcast`, which
builds its own running order and **ignores `episode_order` entirely**
(`config.pi.yaml:306`, `channel.py:307`). Nothing reads it.

## What was filed tonight
| Show | Before | After | Numbering |
|---|---|---|---|
| Dragon Ball Z (Anime) | 58 | **291** | REAL — sagas as seasons |
| Las Aventuras de Jackie Chan | — | **73** | real |
| Ed Edd y Eddy | 5 | **66** | REAL, from its download log |
| El laboratorio de Dexter | 18 | **30** | bundles, NOT canonical |
| Las Chicas Superpoderosas | — | **72** | flat, NOT canonical |
| KND Los chicos del barrio | 1 | **71** | flat, NOT canonical |
| Tom y Jerry | — | **48** | bundles, NOT canonical |
| Doug | 26 | **72** | REAL for the 46 added |
| Jake Long El Dragón occidental | 1 | **51** | REAL |
| Winnie the Pooh (DisneyJr) | — | **46** | REAL |
| Lilo y Stitch La Serie | 1 | **65 — COMPLETE** | REAL |

Every filing verified minutes-in against minutes-out, all exact.

## 🔴 The rule that saved the library FOUR times
**Never replace an existing episode without diffing quality first.** "Replace the
old ones" nearly destroyed better copies on four shows tonight:
- **Ed Edd S01E02** — the new 65-file set lacked it; the old copy was the only one.
- **Jake Long S01E01** — existing 1280x720 vs the new batch's 426x240.
- **Lilo S01E01** — existing 1920x1080 (2888 kbps) vs new 852x480.
- **Doug** — a blanket replace would have deleted **13 episodes that exist nowhere
  else** and downgraded 21 more from ~3135 kbps to ~750 kbps.

## Audio matching beats picture matching for finding duplicates
Doug's catalog copies carry no titles, so duplicates had to be found by content.
**Picture fingerprinting FAILED** — percentage-sampled frame hashes gave a smear
(483-710 of 1536) with no bimodal split, unstable thresholds, and ten existing
files each claimed by two new ones. A threshold picked from that would have been
fiction. **Audio envelope cross-correlation worked**: matches 0.982-0.997,
non-matches 0.09-0.19, a 0.354 gap, clean 1:1 mapping. The same method identified
Lilo's 1080p S01E01 at 0.997 against a 0.190 runner-up. Reuse this approach.

## Decisions made
- **`_tools/okru.py` is new and reusable** — resolves an ok.ru video id to its best
  direct rendition, with an optional quality cap. Adapted from Codex's
  `download_jackie_spanish.py` with one fix: that version required
  `hlsManifestUrl` in `data-options`, which older progressive uploads lack, so
  every Tom y Jerry video looked unresolvable.
- **Dexter's 90 shorts and Tom y Jerry's 161 shorts were BUNDLED** into ~21-min
  blocks (`bundle-clips.py --target 20`). Their `S01Exx` numbers are bundles.
- **Tom y Jerry's block composition WAS recorded and verified** (all 48 computed
  durations matched the files on disk). **Dexter's was NOT** — lost when
  `_staging` was deleted. Its 90 segment titles were later recovered from Brian's
  sheet, but which segments went into which block is gone for good.
- **Powerpuff and KND are numbered flat** — their sources carried no season data.
- **Doug: kept all 26 existing, added only the 46 genuinely new**; 13 duplicate
  downloads discarded.
- **Lilo renumbered to real seasons** (39 + 26) from its log's `source_title`.

## Bugs found — do not reintroduce
- 🔴 **`okru.py` RANK was missing `full`.** ok.ru calls 1080p `full`, not
  `full_hd`, so it scored as unknown and lost to `hd` — silently taking about half
  the bitrate. Fixed 2026-09-01. **Winnie was pulled BEFORE this fix.** Lilo's
  repaired S02E21 came down at 713 MB / 1920x1080 after it, vs 350 MB before.
- 🔴 **mp3 audio inside MP4 plays SILENT** on QuickTime and many hardware decoders.
  60 files across 8 shows (Teletubbies 17, Snoopy 26, El niño lobo 6, Sapo y Sepo
  5, Avatar 3, Pato y Ganso 2, Tibucán 1). All converted to AAC with video
  stream-copied, each verified on duration, loudness and decode.
- **`-v error` SUPPRESSES `volumedetect` and `psnr` output** — they log at info
  level. Cost two wrong "no output" readings before it was spotted.
- **`pgrep` reported dead processes that were plainly alive**, at least three
  times. **Judge by file growth and timestamps, not `pgrep`.**
- **A VPN coming up mid-session is poison for long downloads.** ProtonVPN
  connecting mid-run wedged three workers for 11 minutes past a 45 s socket
  timeout, and dropped Doug from 11 MiB/s to 80 KB/s. It also caused the truncated
  Winnie files: all six repairs failed repeatedly with it on and succeeded
  **first attempt** with it off. The tell is a *fresh* connection working while
  old ones hang.
- **zsh arrays are 1-indexed.** A bash-style `for i in 0 1` loop built an empty
  path and moved a whole temp folder into a Season directory. Nothing was lost,
  but use explicit paths and assert every file exists before touching anything.
- **The Drive connector TRUNCATES large sheets** — it returned 924 lines of a
  1,708-row tab, which is why Tom y Jerry "did not exist". Export the workbook as
  xlsx and parse that instead.
- **This machine's `find` rejects `-newermt '-30 minutes'`**; use `-mmin`.

## Open questions / blockers
- 🔴 **No USB drive.** 600 GB library, Pi SD card has 22 GB free. Every channel
  reads empty until one exists.
- 🔴 **Sheet owed ~11 rows + ~900 episode rows** (`workspace-mcp` down all evening).
- ⚠️ **RE-PULL CANDIDATES**, each recorded in its own `_source-titles.json`:
  - **Jake Long** — 426x240 at ~296 kbps, the worst in the library; source offers
    `hd` at ~325 MB/ep. S02E25 is 8.1 min (short); S02E26 was never obtainable.
  - **Winnie the Pooh** — pulled at `low` (~107 MB/ep) to fit a full disk, and
    before the RANK fix. `full` is available and would be a large gain.
  - **Lilo** — 852x480 ~1100 kbps except S02E21; `full` is ~3.7 Mbps.
- ⚠️ **Doug's `Season 05` labels look WRONG.** 13 of those episodes audio-match
  episodes the source numbers as S01-S03. Left alone; the folder now carries two
  conventions. **S05E22 is corrupt** (384 kbps, fails decode) and has **no
  replacement in the new set**.
- ⚠️ **Danny_Phantom: 175 orphaned partials** in `~/Downloads/Cartoons/`.
- **Deletions used `rm` (no Trash).** Swept tonight: 13 Doug duplicates, Lilo's
  staging, and each show's staging folder after filing.
- 🔴 **Sources are dying in real time.** 4 Winnie episodes, 7 Doug episodes, 2
  Avatar direct URLs (410/403) and Jake Long S02E26 all went unavailable **today**.
  This library is **not re-downloadable**. One copy on one USB drive is not a
  backup — and exFAT has no journaling, so a power cut on the Pi can corrupt it.
  The 13 MB of metadata (`_source-titles.json`, `_download-log.jsonl`, tiles,
  `_tools/`) is the irreplaceable part and should stay on the Mac regardless.

## How to resume
Start a fresh session (don't click "Keep full session"). Then say:
> "read SESSION-WRAP.md and continue."
