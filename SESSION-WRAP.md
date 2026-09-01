# Session Wrap — 2026-08-31 (full day)

## What we worked on
Filed the three shows the previous session left cut but unfiled, added three new
shows, took Jimmy Neutron from 1 episode to 56, finished Pistas, retired the
purple artwork tag, and cleaned ~25 GB of working files out of the library.
Media lives in `~/Downloads/Converted/`; the repo itself was not touched.

## Status right now
**Nothing is running.** Everything below is filed and verified.

## Next 1-3 steps
1. **The Google Sheet is BEHIND — auth expired mid-write.** Pistas (Lineup row 52)
   still reads 20 episodes when it is 43, and its notes rewrite never landed.
   Re-authorise, then rewrite `Lineup!O52` = 43 and `Lineup!H52`. Everything else
   on the sheet is current.
2. **Convert the two Kim Possible `.mkv` files** waiting in `~/Downloads` —
   S02E20 and S04E07, the two the catalog records as damaged. They need
   `mkv2mp4`, not a rename. That takes the show 81 -> 83 of 87.
3. **Kim Possible is missing more than the sheet said.** Corrected today: Season 3
   has **14** episodes and only 10 are held, so E11-E14 are the real gap.

## Where things stand
- **2,666 episodes across 64 shows in 25 channels. 63 GB free.**
- **Every show has a verified tile** — all 64 probed as decodable 1024x768
  images, not merely present.
- **Colour tags: 19 red, nothing else.** Purple is retired.

| Show | Now | Missing |
|---|---|---|
| Xiaolin Showdown | **52 — COMPLETE** | — |
| Daniel Tigre | 70 | — |
| Dora la Exploradora | 61 | — |
| Jimmy Neutron | 56 | S01E14, S01E15, S02E08, S02E20 |
| Pistas de Blue y tú | **43 — COMPLETE** | — |
| Kim Possible | 81 | S02E20, S04E07 (mkv in hand), **S03E11-E14** |
| 123 Andrés - Letras / Canciones | 4 / 6 | — |

## Decisions made
- **Purple (no-artwork) tags are RETIRED.** Only incomplete flags remain.
  `tag-incomplete.py --apply` REPLACES every tag, so one run does the whole job.
  ⚠️ `tag-artwork.py` still exists and **will re-add purple** the moment a show
  arrives without a tile. Harmless today; a landmine later.
- **Cut pieces number PAST the highest episode, they do not fill gaps.** Daniel
  E86-E115, Dora E177-E211. These shows number by DOWNLOAD INDEX, not broadcast
  order, so a gap exists *because* that source was cut up. Opposite call to Ms.
  Nenna, where the gaps genuinely were the episodes' places.
- **Short clips bundle into ~21-min blocks.** A 2-minute alphabet clip would be
  shorter than the commercial break after it.
- **Bundled-clip shows get BLANK Seasons/Total on Lineup** (Pistas, both 123
  Andrés) — a percentage against a real series count would be meaningless.
- **Jimmy Neutron S01E01 stays at 768x576**; the batch's 360p copy was discarded
  twice. **S02E19 (44.2 min) is KEPT AS IS**, not split.
- **Pistas E28/E31 (35.1 and 40.0 min) were "don't split"** on Brian's marks and
  are the two longest episodes in the show.

## Bugs found — do not reintroduce
- **The tracker is registry-driven.** `_tools/shows.json` lists every show
  status.py will display; a show absent from it is INVISIBLE however healthy the
  download. A registry "videos" count means source CLIPS, not filed BLOCKS —
  after bundling, leaving the clip count makes a finished show read 4/41 = 10%
  and tags it red. **Pistas still holds 82 against its 43 episodes** and only
  escapes a false flag by the `ú` bug below.
- **`ú` is stored DECOMPOSED on this disk.** `Pistas de Blue y tú` written with a
  precomposed ú matches nothing — `find -name`, globs and dict lookups all fail
  SILENTLY. Normalise to NFC before comparing.
- **ffmpeg's concat DEMUXER cannot join clips of differing frame rate.** It
  assumes a shared timebase and drifts audio — a fault NO duration check catches.
  Use the concat FILTER. 123 Andrés' 41 alphabet clips carry 8 encodes across 20
  interleaved runs.
- **Grouping clips by encode destroys playlist order** — would have put D, W, X,
  Z, CH in one block and A, B, C, E in another, and the blocks would still have
  looked fine.
- **`gdown --id` was REMOVED in gdown 6.x** (take the id positionally). Passing it
  exits on a usage error and writes ZERO bytes — 52 of them, silently.
- **`gdown --folder` caps at 50 files.** On a 52-episode series it drops two.
- **Google Drive's download quota is per-FILE, not per-IP** — proven by switching
  the VPN exit to Tokyo and getting the identical refusal on the same files.
  Browser downloads keep working while the API path is blocked. A VPN cannot
  route around it, unlike a geo-block.
- **Editing a running bash script breaks it** (bash reads by byte offset). Stop,
  edit, restart; `_archive.txt` makes the resume free.
- **`timeout` does not exist on macOS** — use a Python subprocess timeout.
- **zsh does not word-split unquoted `$VAR`**; `for x in $LIST` iterates once.
  Cost several mangled outputs. Use python or an explicit array.
- **A gap-check cannot find a missing SEASON TAIL.** Kim Possible S3 runs
  contiguously 1-10 with no internal hole, so it read as complete for weeks. Only
  comparing against the real season length caught it.

## The lesson that kept repeating
**Verify by content, never by name or exit code.** Everything that mattered today
was minutes-in against minutes-out, a byte count, or an actual frame:
- Every filing verified exactly: 13.626 h, 17.698 h, 9.616 h, 3.583 h, 18.326 h,
  9.278 h — each in and out to within a second.
- **Byte-size checks caught 52 zero-byte gdown failures and then 20 more.** gdown
  exits 0 on a truncated transfer AND on Google's quota HTML page.
- Jimmy Neutron's three 44-46 min files looked like joined episodes by duration
  alone. Contact sheets showed two are legitimate double-length specials — one a
  Jimmy Timmy Power Hour crossover that switches to 2D partway.
- Two "identical" Pistas compilations and a Jimmy Neutron S02E19/E20 pair were
  proven duplicates by PSNR (mse 0.00, psnr inf), not by their matching titles.
- All 64 tiles were probed as images, not merely tested for existence.

```
ffmpeg -i EP.mp4 -vf "fps=1/45,scale=200:-1,tile=6x5" -frames:v 1 -y sheet.jpg
ffmpeg -ss N -t 90 -i A -ss N -t 90 -i B -filter_complex "[0:v][1:v]psnr" -f null -
```

## Tools changed (all in `~/Downloads/Converted/_tools/`)
- `file-cut-pieces.py` **NEW** — filed Daniel/Dora/Pistas. `file-shows.py` could
  not: it reads `_staging`, expects top-level shows, has no rule for these. Its
  45-min guard was left alone — that guard caught Dora's 4h26m "episode".
- `bundle-clips.py` **PARAMETERISED** — `--show`, `--target`, `--max-clip`,
  `--no-group`. Pistas defaults unchanged. Backup `.bak-20260831`.
- `get-123andres.sh`, `get-xiaolin.py`, `xiaolin-resume.sh`, `pistas-cut.sh` **NEW**
- `shows.json` — 2 entries added. Backup `.bak-20260831`.
- `_tools/.venv/` **NEW** — holds gdown 6.1.0. Homebrew Python blocks pip
  (PEP 668), so a venv was used rather than `--break-system-packages`.

## Cleanup done
~25 GB freed. Swept only after proving each source was fully represented in
filed episodes. **Deliberately kept:** `_commercials` (61 files — the box plays
these, `config.yaml` points at it) and `PBSKids/Jorge el Curioso/_unsplit`
(66-min source with no findable boundary, never filed, only copy).
32 `_archive.txt` files (1,930 ids) survive — deleting those means re-downloading.

## Open questions
- Retire `tag-artwork.py`, or leave it to resurrect purple later?
- CLAUDE.md describes a **`Seasons breakdown` tab that no longer exists** — the
  sheet has only Lineup, Cine, Sheet1, Episodes.
- CLAUDE.md says Lineup col Q is "Named"; most rows carry a leftover `=O/M`
  percentage formula and HAVE rows carry a literal 0.
- Deletions used `rm -rf`, which bypasses the Trash.

## How to resume
Start a fresh session (don't click "Keep full session"). Then say:
> "read SESSION-WRAP.md and continue."
