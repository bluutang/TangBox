# Session wrap — eight shows downloading, channel design decided (2026-08-28)

Downloads run without Claude. **Check them at
`/Users/briantang/Downloads/Converted/_status.html`** — self-refreshing every
15s: episodes, GB, live speed, ETA, and catalogue size against the 1 TB drive.

    running now   ps -Ao args= | grep -E '[y]t-dlp|run-[q]ueue'
    queue log     tail -f ~/Downloads/Converted/_queue.log
    stop all      pkill -f run-queue; then kill the yt-dlp BY SHOW NAME
    resume        cd ~/Downloads/Converted && nohup ./_tools/run-queue6.sh >> _queue.log 2>&1 &

## Where the downloads are

| Show | State |
|---|---|
| **Franklin** | ✅ 78/78 — downloaded, named, filed in `Franklin/Season 01/` |
| **Daniel Tigre** | ✅ 61/61 downloaded (still in `_staging`, unnamed) |
| Jorge el Curioso | 26/34 — downloading |
| Barney el Dinosaurio | 15/41 |
| Pistas de Blue y tú | 0/82 |
| Clifford | 0/77 |
| El Autobús Mágico | 0/50 (episodes only, see below) |
| Arthur | 0/65 (archive.org, not YouTube) |

Catalogue **219 GB = 22% of the 1 TB drive**; ~238 GB projected at 1254 episodes.

## 🔴 The VPN rule — this cost hours

These are Spanish dubs licensed to ~212 countries. **Poland, the USA, Germany
and France are NOT among them. Mexico, Spain, Canada, the UK and Latin America
are.** Currently on **Canada**, which works for all shows.

- Franklin lost **31 of 78** and Jorge **14 of 36** on a Polish exit.
- Speed also matters hugely: Poland ~214 KB/s, **Canada ~5.4 MB/s (25x)**.
- **After any server change run `_tools/check-vpn.sh`** — probes one video per
  show, verdict in seconds.
- The failure is QUIET: `--ignore-errors` skips blocked videos and yt-dlp often
  reports a bare `Video unavailable` (which normally means *deleted*). **Watch
  the episode count, not the log.**

## Decisions made

- **Discard anything over 1.5 h.** Cut 32 videos, 108 GB → 67 GB. Those were
  compilations repackaging episodes that exist standalone — proved when the one
  Daniel file that refused to download turned out to contain two episodes we
  already had.
- **A 20–25 min piece is a finished episode**, even when it is two shorts joined.
  So `--min-episode` is 18 min and Franklin is never split.
- **El Autobús Mágico: episodes only.** Its 41 compilations are ~46 h of pure
  duplication of the 50 standalone episodes. Filter is in `run-queue6.sh` via
  `MATCHFILTER`.
- **YouTube titles ARE allowed in filenames.** The no-titles rule bans *looked-up
  database* titles (the Rugrats problem). A YouTube title comes from the video
  itself and cannot be mismatched. Same reasoning as Plaza Sésamo.
- **Multiple titles separated by fullwidth ｜ (U+FF5C), never ASCII `|`.**
  The USB is exFAT (README Part E) and exFAT forbids `" * / : < > ? \ |`.

## Tools (all in `Converted/_tools/`)

| File | Does |
|---|---|
| `get-playlist.sh` | YouTube playlist → `_staging`. H.264 only, ≤1.5 h, resumable. `$MATCHFILTER` overrides the filter. |
| `get-archive.py` | archive.org items → `_staging`. No geo-block, no format negotiation. |
| `run-queue6.sh` | One show at a time, **retried until it stops making progress**. |
| `detect-breaks.py` | Finds episode joins (black AND silent); `--split` cuts. |
| `name-from-titles.py` | Names staged files from YouTube titles. Dry-run by default. |
| `check-vpn.sh` | Is this VPN exit allowed? One probe per show. |
| `check-exfat.py` | Every name legal on the USB drive? **Re-run before copying.** |
| `status.py` / `watch-status.sh` | Regenerate `_status.html`. |

## Next steps

1. **Finish the queue** — Jorge, Barney, Blue's, Clifford, Magic School Bus, Arthur.
2. **Split / join**, per show:
   - **Jorge**: all 34 are compilations, ~45:07 = two 22-min episodes. **Zero
     chapter coverage** across 27 videos measured, so `detect-breaks.py` is the
     only method. **Show Brian the first proposed cuts before running all 34.**
   - **Clifford**: 52 full episodes stay; 24 halves (10:34–12:40) **pair into 12**
     (~22:48). Use `mkv2mp4/join_segments.py` — it did Dexter's 47→18. Check the
     titles first: real broadcast pairs may be reconstructable.
   - **Blue's Clues**: 56 clips joined *up* into ~52 episodes of ~22 min.
3. **Name** the rest with `name-from-titles.py` (dry-run first — it caught a
   duplicated show name on Franklin).
4. **Dedupe by content**, not title, especially Daniel Tigre.
5. **Sheet**: Daniel Tigre (row 40) and Barney (row 6) still say `Wanted`;
   Franklin row 74 says 41 and should read 78.
6. **Write the channel config** — see below.
7. **Copy to USB**, re-running `check-exfat.py` first.

## The channel lineup — DECIDED, not yet written

17 channels, 45 shows, ~1306 episodes. **Every channel is ONE network/platform**;
age splits each block internally. `path:` must be **ASCII only** (config.pi.yaml
warns macOS/Linux disagree on accent encoding).

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
| Anime | 18 | Anime | Anime | 10+ | Dragon Ball Z |

Brian will add episodes to the thin channels — **do not rebalance on episode
count.** Channels under ~5 episodes are probably worth leaving out of the config
until they fill; one episode plays on endless repeat.

`config.pi.yaml` still holds the OLD 5 channels, superseded by
`docs/superpowers/specs/2026-08-20-channel-numbering-design.md` and never
rewritten. It also cites a **different spreadsheet id** (`1fb_Xrny0G…`) than the
live one (`17ZosBycj…`) — one is stale.

## Code shipped this session

- `4e1b936` — `ChannelConfig.age` (`age: "2-4"`), drawn under the name on the
  channel banner. Free text; absent means no line.
- `b327d77` — guide detail row: one centred line under the grid giving the
  focused channel's age and shows. **Under the grid, not on tiles, because a
  tile with artwork draws no ASS at all** (mpv puts bitmaps above ASS, so its
  text is burned into the picture) — a per-tile age would need writing twice.

**Both are inert until wired.** `app.py` does not yet pass `ages`/`shows` into
`guide_ass`, and no channel declares an `age:`. Both light up with the config
rewrite; `shows` can come from listing each channel folder's subdirectories,
computed once at start-up rather than per draw.

630 tests pass.

## Gotchas — several cost real time

- **`pkill -f` matches your own shell.** Killing by a pattern that appears
  anywhere in the same command kills the command. Happened 3x (exit 144). Kill
  in a SEPARATE call from any that names the script, or match `run-[q]ueue`.
- **Killing a wrapper does not kill `yt-dlp`.** Its args hold the URL and output
  path, not the script name — orphans keep downloading. **Kill by SHOW NAME.**
- **Progress lines use `\r`.** `grep '^ERROR'` misses errors glued to the end of
  a progress line; `[N/M] file` entries get overwritten. Convert with
  `tr '\r' '\n'` first. This hid an error and a filename on two separate days.
- **Python buffers stdout** when not a tty — background jobs look empty until done.
- **zsh does not word-split unquoted variables** (bash does). `for x in $LIST`
  iterates ONCE over the whole string.
- `du` sees a growing `.part` in ~1 MB steps, so short samples quantise to
  0/102/204 KB/s. Speed 0 does not mean stalled.

## Carried over — still outstanding

**Plaza Sésamo (80 episodes, 14 GB) has never been moved to the USB drive.** Also
open: `Lineup` L2/M2 hold *US Sesame Street* totals (56 seasons / 4662 episodes)
so its bar reads 80/4662; and the `Seasons breakdown` tab documented in CLAUDE.md
does not exist in the spreadsheet.

## Repo

Clean apart from this file. Two commits pushed to `main`. All media work lives in
`~/Downloads/Converted/`.
