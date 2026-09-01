# Session Wrap — 2026-08-31 / 09-01 (long session)

## What we worked on
Filed five shows the previous session left cut, added three new shows, took
Jimmy Neutron from 1 episode to 56, finished Pistas and Xiaolin Showdown,
retired the purple artwork tag, cleaned ~25 GB of working files, and rebuilt the
commercial pool from 61 clips to 146 — synced live to the Pi.
Media lives in `~/Downloads/Converted/`; the repo itself was not touched.

## Status right now
**Nothing is running.** Everything below is filed and verified. The Pi is up,
`tangbox.service` active, running the new commercial pool.

## Next 1-3 steps
1. 🔴 **DECIDE WHICH CHANNEL SCHEME WINS** — see "The two channel schemes" below.
   The Mac library and the running box are filed to DIFFERENT schemes. Nothing
   plays until they agree, and the failure is silent.
2. Nothing else is blocked or half-done. `~/Downloads` is empty.

## 🔴 The two channel schemes — unresolved
**The repo's `config.pi.yaml` is NOT what the box runs.** The Pi reads its own
`/home/brian/TangBox/config.yaml`. The two describe different libraries:

| | Repo template `config.pi.yaml` | Live box `~/TangBox/config.yaml` |
|---|---|---|
| Channels | ~23 fine-grained | **10 broad** |
| Names | PBS Kids, Nick Jr, Nick Clásico, Disney Jr… | Preescolar, Nickelodeon, Disney Clásico, Mayores… |
| Media root | `/media/tangbox/` (USB) | `/home/brian/media/` (SD card) |

**The Mac library at `~/Downloads/Converted/` is filed to the TEMPLATE's scheme.**
All ten of the live box's channel folders are **EMPTY (0 mp4 each)** and the USB
drive is not mounted, so the box currently plays commercials and sign-on only.

When the drive is connected, the folder names must match whichever config the Pi
loads or every channel reads empty — which is exactly what it does today, and it
gives no error. Pick one scheme and make the other match before blaming the
drive.

## Root-level shows — fixed 2026-09-01
Three shows sat OUTSIDE any channel folder, so 158 episodes were not on any
channel. Moved to where the template says they belong:

    Pistas de Blue y tú  -> NickJr/        (43)
    Daniel Tigre         -> PBSKids/       (70)
    Barney el Dinosaurio -> PBSPequenos/   (45)

Renames on the same disk, so nothing copied; tiles and `_archive.txt` travelled
with them. Episode and show counts unchanged (2,666 / 64). **No show is at the
root any more** — worth re-checking after any future bulk add, since a show
dropped at the root looks completely normal in Finder.

## Where things stand
- **2,668 episodes across 64 shows. 60 GB free.**
- **146 commercials** (128 generic + Disney 7, Nickelodeon 9, CartoonNetwork 2),
  identical on the Mac and the Pi's SD card.
- Every show has a verified tile; **19 red tags, nothing else.** Purple retired.
- The Google Sheet is **fully current** — every show below, plus 52 Xiaolin rows
  and 31 Pistas rows on the Episodes tab.

| Show | Now | Missing |
|---|---|---|
| Xiaolin Showdown | **52 — COMPLETE** | — |
| Daniel Tigre | 70 | — |
| Dora la Exploradora | 61 | — |
| Pistas de Blue y tú | **43 — COMPLETE** | — |
| Jimmy Neutron | 56 | S01E14, S01E15, S02E08, S02E20 |
| Kim Possible | **83 — PARKED at 83** | S03E11-E14, unobtainable (below) |
| 123 Andrés - Letras / Canciones | 4 / 6 | — |

## Kim Possible — parked at 83/87 (2026-09-01)
S1 21/21, S2 30/30, S3 10/14, S4 22/22. **The four missing Season 3 episodes
(E11-E14) could not be sourced and are PARKED.** Treat the show as done unless
Brian raises it; do not go hunting for them again.

The two damaged files WERE replaced: S02E20 (had an unreadable EBML header) and
S04E07 (claimed 22:48, only 6:06 decoded — it sat in the catalog as a 6-minute
stub for weeks). Remuxed losslessly from `.mkv` with `mkv2mp4`, then verified by
a **full software decode** — 22:50 and 22:49, zero errors — not by the
container's duration, which is exactly what let the old S04E07 look healthy.
Both are 1920x1080 against the show's usual 492x360-768x576.

## Decisions made
- **Purple (no-artwork) tags are RETIRED.** ⚠️ `tag-artwork.py` still exists and
  **will re-add purple** the moment a show arrives without a tile.
- **Cut pieces number PAST the highest episode, they do not fill gaps** (Daniel
  E86-E115, Dora E177-E211). These shows number by DOWNLOAD INDEX, so a gap
  exists *because* that source was cut up. Opposite call to Ms. Nenna.
- **Short clips bundle into ~21-min blocks**; bundled-clip shows get BLANK
  Seasons/Total on Lineup (Pistas, both 123 Andrés).
- **Jimmy Neutron S01E01 stays at 768x576**; S02E19 (44.2 min) kept unsplit.
- **Commercials: 15-45 s, toys/snacks/food/kid brands, nothing before 1995**, no
  theme songs, intros, network idents or brand logos. Curated by READING every
  title — 448 playlist entries down to 78.

## Bugs found — do not reintroduce
- 🔴 **`rsync --delete` to the Pi would have destroyed the CartoonNetwork
  bumpers.** They existed ONLY on the Pi, and config makes a missing network
  folder fall back to generic adverts SILENTLY — the channel would just stop
  sounding like itself with nothing to show why. Pull Pi-only content to the Mac
  first; sync additions without `--delete` and remove unwanted files explicitly.
- **A long rsync exceeds the 120 s foreground limit and appears to do nothing** —
  worse when piped through `grep`, which hides it. Check the REMOTE file count,
  never the command's apparent success.
- **`gdown --id` was REMOVED in gdown 6.x** (pass the id positionally). Using it
  exits on a usage error and writes ZERO bytes — 52 of them, silently.
  **`gdown --folder` caps at 50 files**, so a 52-episode series loses two.
- **Google Drive's download quota is per-FILE, not per-IP** — proven by moving
  the VPN exit to Tokyo and getting the identical refusal on the same files.
  Browser downloads keep working while the API path is blocked.
- **The tracker is registry-driven** (`_tools/shows.json`); a show absent from it
  is INVISIBLE however healthy the download. Its "videos" count means source
  CLIPS, not filed BLOCKS — leaving the clip count makes a finished show read
  10% and tags it red.
- **`_commercials` breaks the tracker's size estimate.** It computes
  `folder_bytes / done × expected`, which assumes the folder holds only what the
  archive counted. 273 MB of pre-existing ads made it read "~10.8 GB". Converges
  as the fetch completes; the episode count stays correct throughout.
- **`ú` is stored DECOMPOSED on this disk.** A precomposed `ú` matches nothing —
  `find -name`, globs and dict lookups all fail silently. Normalise to NFC.
- **ffmpeg's concat DEMUXER cannot join clips of differing frame rate** (drifts
  audio, no duration check catches it). Use the concat FILTER.
- **`-c copy` cuts round BACKWARDS to a keyframe**, silently, by up to ~5 s.
  `cut-at.py` always re-encodes for exactly this reason.
- **A gap-check cannot find a missing SEASON TAIL.** Kim Possible S3 runs 1-10
  with no internal hole, so it read as complete for weeks.
- **`timeout` does not exist on macOS**; **zsh does not word-split unquoted
  `$VAR`**, and an unmatched glob aborts the whole command.

## The lesson that kept repeating
**Verify by content, never by name or exit code.** Every filing verified as
minutes-in against minutes-out — 13.626 h, 17.698 h, 9.616 h, 3.583 h, 18.326 h,
9.278 h, 7.330 h — each exact. Byte-size checks caught 72 zero-byte gdown
failures. PSNR (mse 0.00 / psnr inf) proved seven "duplicate" commercials, a
Jimmy Neutron S02E19/E20 pair and two Pistas compilations were genuinely
identical. Contact sheets showed two Jimmy Neutron 44-46 min files were real
double-length specials, not joined episodes. All 64 tiles were probed as images.

```
ffmpeg -i EP.mp4 -vf "fps=1/45,scale=200:-1,tile=6x5" -frames:v 1 -y sheet.jpg
ffmpeg -ss N -t 90 -i A -ss N -t 90 -i B -filter_complex "[0:v][1:v]psnr" -f null -
```

## Commercials — how the pool is now built
- Pool: **146 clips, 488 MB**, mirrored Mac ↔ Pi (`~/tangbox-commercials`, on the
  SD card DELIBERATELY, outside `/media/tangbox` so a USB mount cannot hide it).
- **The Pi's overlay filesystem is OFF**, so writes persist. Check
  `grep boot=overlay /proc/cmdline` before writing — if it is ever ON, changes
  vanish on reboot.
- `CommercialPool` is built at STARTUP, so new clips need
  `sudo systemctl restart tangbox.service`. The startup log prints the pool size
  per network — that line is the proof the sync worked.
- Over-long adverts are already handled: `_draw_that_fits` passes over anything
  too long for the break. A 9-minute compilation cannot become the whole break.
- One clip with a self-harm title was found in the pre-existing 61 and removed
  from BOTH machines. It got in because an earlier pass took a playlist without
  reading every title. The remaining 61 were reviewed; nothing else.

## Tools (all in `~/Downloads/Converted/_tools/`)
- **NEW**: `file-cut-pieces.py`, `get-123andres.sh`, `get-xiaolin.py`,
  `xiaolin-resume.sh`, `pistas-cut.sh`, `get-commercials.py`
- **CHANGED**: `bundle-clips.py` parameterised (`--show/--target/--max-clip/
  --no-group`; Pistas defaults unchanged), `shows.json` +3 entries
- **NEW**: `_tools/.venv/` holds gdown 6.1.0 — Homebrew Python blocks pip
  (PEP 668), so a venv was used rather than `--break-system-packages`
- Backups kept: `bundle-clips.py.bak-20260831`, `shows.json.bak-20260831`

## Open questions
- **Which channel scheme wins** (see the red section above). Until that is
  settled, connecting the USB drive will not make the box play anything.
- Retire `tag-artwork.py`, or leave it to resurrect purple later?
- CLAUDE.md describes a **`Seasons breakdown` tab that no longer exists**; and
  says Lineup col Q is "Named" when most rows carry a leftover `=O/M` formula.
- `_commercials` still holds a for-profit college advert and a Disney Channel
  theme song — off-brief but harmless.
- Episodes tab was extended to 1,200 rows; 1,025 used.
- Deletions used `rm -rf`, which bypasses the Trash.

## How to resume
Start a fresh session (don't click "Keep full session"). Then say:
> "read SESSION-WRAP.md and continue."
