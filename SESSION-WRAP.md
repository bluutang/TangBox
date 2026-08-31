# Session Wrap — 2026-08-31 (morning)

## What we worked on
Filed the three shows the last session left cut but unfiled, added two new shows
from 123 Andrés YouTube playlists, took in a batch of Jimmy Neutron episodes, and
retired the purple artwork tag. Media lives in `~/Downloads/Converted/`; the repo
itself was not touched this session.

## Status right now
**Nothing is running.** Everything below is filed and verified.

## Next 1-3 steps
1. **Pistas: 21 compilations need split points.** Brian is reviewing them now;
   the folder is open. `Pistas de Blue y tú/_compilations`, 14.5 h, 18.7-62.4 min
   each. Two already-known traps, BOTH now confirmed:
   - `027` and `028` "40 MIN de fiesta con Blue y Josh" are THE SAME VIDEO -
     identical to the millisecond (2401.663 s) and pixel-identical mid-file
     (mse 0.00, PSNR inf). Keep **028** (187.8 MB vs 187.3). 027 not yet deleted.
   - `035` "¡30 minutos de las canciones…" actually runs **18.7 min**.
2. **More Jimmy Neutron episodes arriving today.** Same handling as below - the
   filer is a ~20-line script, not a saved tool. Existing episodes:
   S01 {1,5,12,13,17,20}, S02 {1,2,5,7,9,19}, S03 {2,3,5,6,7,11,14,15,18,19}.
3. **Two registry/reality mismatches** left in `_tools/shows.json` - see below.

## Where things stand
- **2,549 episodes across 63 shows. 103 GB free** (14.8 GB swept this session).
- **Every show has a tile.** All 63 verified as decodable 1024x768 images, not
  merely present - a tile that exists but will not render is still a blank.
- **Colour tags: 19 red, nothing else.** Purple is retired.

## Decisions made
- **Purple (no-artwork) tags are RETIRED.** Only incomplete flags remain.
  `tag-incomplete.py --apply` REPLACES every tag, so one run does the whole job.
- **Cut pieces number PAST the highest episode, they do not fill gaps.** Daniel
  E86-E115, Dora E177-E211. These shows number by DOWNLOAD INDEX, not broadcast
  order, so a gap exists *because* that source was cut up. This is the opposite
  call to Ms. Nenna, where the gaps genuinely were the episodes' places.
- **Dora's 12 double-length pieces (42-47 min) were filed as-is** - two episodes
  joined, boundary marked only by credits, no reliable cut point after real
  effort.
- **Short clips are bundled into ~21-min blocks, not filed individually.** A
  2-minute alphabet clip would be shorter than the commercial break after it.
  Same precedent as Pistas and Rolie Polie Olie.
- **123 Andrés is TWO shows under Aprende**, Letras (4) and Canciones (6).
- **Jimmy Neutron S01E01 stays at 768x576.** The new batch is 360p throughout;
  the better original was kept and the batch's Cap.101 discarded.
- **Jimmy Neutron S02E19 (44.2 min) is KEPT AS IS**, not split.
- **Seasons/Total episodes are left BLANK on Lineup for bundled-clip shows**
  (Pistas, both 123 Andrés). A percentage against a real series count would be
  meaningless. Era is blank for 123 Andrés too - playlists span years.

## Bugs found — do not reintroduce
- **The tracker is registry-driven.** `_tools/shows.json` lists every show
  status.py will display; a show absent from it is INVISIBLE no matter how
  healthy the download. This is why 123 Andrés "did not appear".
- **A registry "videos" count means source CLIPS, not filed BLOCKS.** After
  bundling, leaving the clip count makes a finished show read 4/41 = 10% and tags
  it red. Fixed for both 123 Andrés shows; **Pistas still holds 82 against its 12
  episodes** and only escapes a false red flag by accident (below).
- **`ú` is stored DECOMPOSED on this disk.** `Pistas de Blue y tú` written with a
  precomposed ú matches nothing - `find -name`, globs and dict lookups all fail
  silently. Normalise to NFC before comparing. This hid the folder from a search
  and is why the Pistas registry lookup misses.
- **ffmpeg's concat DEMUXER cannot join clips of differing frame rate.** It
  assumes a shared timebase and drifts audio - a fault NO duration check catches.
  Use the concat FILTER for mixed input. 123 Andrés' 41 alphabet clips carry 8
  encodes interleaved across 20 runs.
- **Grouping clips by encode destroys playlist order.** The alphabet playlist is
  alphabetical; grouping would have put D, W, X, Z, CH in one block and A, B, C,
  E in another, and the blocks would still have looked fine.
- **Editing a running bash script breaks it** (bash reads by byte offset). To add
  a skip mid-run: stop it, edit, restart. `_archive.txt` makes the resume free.
- **`status.py` speed reads "stalled" for ~2 min after a show is added** - a cold
  start with no byte history, not a fault.
- **zsh does not word-split unquoted `$VAR`**; `for x in $LIST` silently iterates
  once. Cost several mangled command outputs. Use python or an explicit array.

## The lesson that kept repeating
**Verify by content, never by name or exit code.** Every check that mattered this
session was total-minutes-in against total-minutes-out, or an actual frame:
- Daniel's 30 cuts: 10.903 h in, 10.903 h out, 0.4 s across all of them.
- Jimmy Neutron's three 44-46 min files looked like joined episodes *by duration
  alone*. Contact sheets showed two are legitimate double-length specials - one a
  Jimmy Timmy Power Hour crossover that switches to 2D Fairly OddParents midway.
- The two identical Pistas compilations are provably identical by PSNR, not by
  their matching titles.
- All 63 tiles were probed as images, not just tested for existence.

    ffmpeg -i EP.mp4 -vf "fps=1/45,scale=200:-1,tile=6x5" -frames:v 1 -y sheet.jpg
    ffmpeg -ss N -t 90 -i A -ss N -t 90 -i B -filter_complex "[0:v][1:v]psnr" -f null -

## Tools changed (all in `~/Downloads/Converted/_tools/`)
- `file-cut-pieces.py` **NEW** - filed Daniel/Dora/Pistas. `file-shows.py` could
  not: it reads `_staging`, expects top-level shows, and has no rule for these.
  Its 45-min guard was left alone deliberately - that guard caught Dora's 4h26m
  "episode".
- `bundle-clips.py` **PARAMETERISED** - `--show`, `--target`, `--max-clip`,
  `--no-group`. Pistas defaults unchanged. Backup `.bak-20260831`.
- `get-123andres.sh` **NEW** - fetches 4 playlists into 2 shows. Dedupes with no
  new code by seeding the second show's `_archive.txt` from the first; skips are
  pre-seeded ids.
- `shows.json` - 2 entries added. Backup `.bak-20260831`.

## Open questions
- `tag-artwork.py` still exists and **will re-add purple** the moment a show
  arrives without a tile. Harmless today; a landmine later. Retire it?
- CLAUDE.md describes a **`Seasons breakdown` tab that no longer exists** - the
  sheet has only Lineup, Cine, Sheet1, Episodes.
- CLAUDE.md says Lineup col Q is "Named"; in practice most rows carry a leftover
  `=O/M` percentage formula and HAVE rows carry a literal 0.
- Two empty folders could not be removed (permission classifier blocked `rmdir`):
  `NickJr/Dora la Exploradora/_reenc`, `Pistas de Blue y tú/_bundled`.
- Deletions used `rm -rf`, which bypasses the Trash.

## How to resume
Start a fresh session (don't click "Keep full session"). Then say:
> "read SESSION-WRAP.md and continue."
