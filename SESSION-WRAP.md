# Session Wrap — 2026-09-01 (afternoon + evening)

## What we worked on
Closed the red "two channel schemes" item from the last wrap — the Pi now runs
the repo's 22-channel lineup and its folder names match the Mac library exactly.
Then filed FIVE shows into Cartoon Network: Jackie Chan (new), Powerpuff (new),
KND (1 -> 71), and replacement sets for Ed Edd y Eddy and Dexter.

## Status right now
**Nothing is running for me.** Everything below is filed and verified. The Pi is
up, `tangbox.service` active, 22 channels loaded, 146 commercials.

**KND finished and is filed.** `Lilo_and_Stitch` is **STILL DOWNLOADING** in
`~/Downloads/Cartoons/` — confirmed by watching the file count climb, not by
`ps` (a process check came back empty while it was plainly still working, so
trust changing file counts over process lists here). **Left untouched; Brian
will ping when it is done.** It DOES have a `download_log.jsonl`, so it should
file as cleanly as Ed Edd did — check that for real `SxxExx` first.

## Next 1-3 steps
1. File Lilo when Brian says it's done — check its `download_log.jsonl` for
   real `SxxExx` first, the way Ed Edd's was used.
2. Google Sheet is owed FIVE rows — see blockers, the tool was down all session.
3. `Las Chicas Superpoderosas` needs a `tile.jpg` (1024x768). Only show of 61
   without one; `tag-artwork.py` will tag it purple if it runs.

## The channel scheme — RESOLVED, do not re-litigate
The repo's `config.pi.yaml` (22 channels) won. It is newer (2026-08-28, written
against a design spec) and the Mac library already matched it byte-for-byte —
proven, not eyeballed. The Pi's old 10-channel `config.yaml` predated the library.

Done on the Pi: backed up to `config.yaml.bak-20260901-084639`, `git pull`
(it was 13 files behind), copied `config.pi.yaml` over `config.yaml` with the
`assets_dir` line carried across, restarted. Log said "on the air. 22 channels."

⚠️ `episode_order` is a RED HERRING on this box. Both configs set
`tune_in: broadcast`, which builds its own running order and **ignores
`episode_order` entirely** (`config.pi.yaml:306`, `channel.py:307`). Don't
spend time choosing between shuffle and sequential — nothing reads it.

## What was filed — Cartoon Network is now 363 eps across 6 shows
| Show | Before | After | Note |
|---|---|---|---|
| Las Aventuras de Jackie Chan | — | **73** | of 95; S1 + S4 complete |
| Ed Edd y Eddy | 5 | **66** | all 5 seasons COMPLETE, no gaps |
| El laboratorio de Dexter | 18 | **30** | 5.7 h -> 10.8 h of content |
| Las Chicas Superpoderosas | — | **72** | 71 episodes + 1 film |
| KND Los chicos del barrio | 1 | **71** | 70 new + the original, kept |

**Library: 61 shows, 2,954 episodes, 543 GB. 48 GB free on the Mac.**

Every filing verified minutes-in against minutes-out: 25.809 h, 24.611 h,
27.826 h all exact; Dexter's 90 clips -> 30 blocks differed by 0.00004 s.
KND 26.501 h exact. One bundled Dexter block was also fully decoded end to end,
clean.

## Decisions made
- **Dexter's 90 files are SHORTS (6-11 min), not episodes.** Bundled with
  `bundle-clips.py --target 20` into 30 blocks averaging 21.7 min. Target 20,
  not 22 — 22 overshoots to 4-clip/28-min blocks, 19 leaves an 11-min stub.
  All 90 shared identical stream format, so the joins were lossless copies.
- **Dexter's `S01E01-30` numbering is NOT canonical.** They are bundles. The
  source had no season data, only a running segment index. Don't read it as
  "season 1 complete".
- **Powerpuff's season structure is unknown.** Its filenames carried a
  within-season episode number but not the season, so all 71 are `S01E01-E71`
  in sorted order. Also not canonical.
- English source titles preserved in `_source-titles.json` inside the Ed,
  Powerpuff and KND show folders — filenames stay numbers-only per the rule.
  **Dexter's were lost; see blockers.**
- **The Powerpuff film goes in `Las Chicas Superpoderosas/Movies/`**, unsplit,
  keeping its name. Matches how the Sailor Moon films actually sit on disk
  (the config comment claims films are split into `ptNN`; they are not).
- Show named **Las Chicas Superpoderosas** (official Spanish, one word).
- **KND numbering is also NOT canonical** — `S01E01-E71`, same situation as
  Powerpuff (within-season number in the filename, season missing).
- **KND's pre-existing episode was KEPT, parked at `S01E71`.** PSNR against all
  70 new files scored 13.1 at best (identical content scores 40+), so it is
  probably an episode the new set does not have. It may still be a duplicate the
  test could not see if the two rips do not line up at the sample point — but
  keeping a possible duplicate is cheaper than losing a unique episode.

## Bugs / traps found this session
- **A blind "replace" would have destroyed Ed Edd S01E02.** The new 65-file set
  is missing it and the old set had it. Kept the old 720p copy; season is now
  complete at 13. **Always diff old against new before deleting a replacement set.**
- **Ed's `download_log.jsonl` carries the REAL `SxxExx`** in its `stream_title`
  field — authoritative source data, not a lookup. All 65 mapped, no collisions.
  Powerpuff and Dexter shipped no such log, which is the whole reason their
  numbering is guesswork.
- **Audio language tags are worth reading.** Ed = `spa`, Powerpuff = `eng`
  (single track, no Spanish alternative), Dexter and Jackie Chan = `und`.
  Brian confirmed Powerpuff is Spanish and the tag is wrong; filed on his word.
- A "no audio streams" error in Ed's log pointed at a discarded intermediate
  file, not a real episode. All 65 were checked individually and have audio.
- **`find ... -print0 | xargs -0` for anything with spaces.** An unquoted
  `$(find)` in a `for` loop split "Las Aventuras de Jackie Chan" into six words
  and produced pages of parse errors mid-verification.
- `find -newermt '-30 minutes'` is rejected by this machine's `find` (bfs);
  `-mmin -15` works.

## Open questions / blockers
- 🔴 **STILL THE REAL BLOCKER: there is no USB drive.** The library is 543 GB;
  the Pi's SD card has 22 GB free and nothing is mounted at `/media`. Every
  channel reads empty until a drive exists. Needs **1 TB, formatted exFAT,
  mounted at `/media/tangbox`**. The config is ready and waiting.
- 🔴 **The Google Sheet is owed five `Lineup` rows and ~312 `Episodes` rows.**
  `workspace-mcp` timed out at session start and never reconnected; the Drive
  connector that did load can read Sheets but not write them.
- ⚠️ **22 old files were deleted with `rm` (no Trash, unrecoverable):** 4 Ed
  episodes and all 18 Dexter. The Ed four were each replaced by a 1080p version
  of the same episode. The old Dexter 18 had stripped titles, so it was never
  knowable which segments they held — the new 90 segments are probably a
  superset of the old ~54, but that could not be proven and now cannot be checked.
- ⚠️ **One KND file is SHORT: `S01E49` is 14.8 min against a 22.6 min norm.**
  It decodes clean with no errors and the container agrees with the decode, so
  it is not corrupt — it is simply missing about a third of the episode. Filed
  anyway; re-download if it bothers anyone.
- **Titles: Ed Edd (65), Powerpuff (72) and KND (71) have `_source-titles.json`
  in their show folders. DEXTER DOES NOT — those 90 segment titles were lost**
  when `_staging` was deleted after bundling. Nothing depends on them, but they
  are not recoverable.
- KND's titles arrived mangled by the downloader (`Operaci_n_F_U_T_U_R_O`).
  They are de-mangled in the JSON (`Operación F.U.T.U.R.O.`) with the raw
  filename kept beside each. Two are imperfect where accents were destroyed at
  download time: `P.R.A.C.T.Ic.A.` and `H.O.S.P.I.Ta.L.`
- `/Users/briantang/BluuClaude/SESSION-WRAP.md` is a SECOND, stale wrap file
  (Aug 26) — the location `/wrap` points at. TangBox wraps live in this repo now.

## How to resume
Start a fresh session (don't click "Keep full session"). Then say:
> "read SESSION-WRAP.md and continue."
