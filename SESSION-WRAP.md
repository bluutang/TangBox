# Session wrap — adult mode 3/4 built, 17 shows downloading (2026-08-29)

Downloads run without Claude. **Check them at
`/Users/briantang/Downloads/Converted/_status.html`** — in DOWNLOAD ORDER, with
each show's source (YouTube / archive.org) and a bar for the 1 TB drive.

    running now   ps -Ao args= | grep -E '[y]t-dlp|run-[q]ueue'
    queue log     tail -f ~/Downloads/Converted/_queue.log
    stop the queue  kill the run-queue pid; then kill yt-dlp BY SHOW NAME
    resume        cd ~/Downloads/Converted && nohup ./_tools/run-queue15.sh >> _queue.log 2>&1 &

## State — 523 / 982 videos, 17 shows, 275 GB (28% of the drive)

**Seven complete:** Franklin 78, Barney 41, Pistas de Blue y tú 82, Clifford 77,
El Autobús Mágico 50, Daniel Tigre 61, Sailor Moon Películas 2/2.

Downloading: **Sailor Moon 103/200** — the blocked seasons finish at 127. Then Dora 32, Cosmic Kids Yoga 11, Spanish
Basics 22, Aprende Peque 34, Cantonés 102, then **archive.org last** —
Arthur 65, Dragon Ball Z 57, Bear 34. Jorge sits at 29/34 (5 geo-blocked).

## 🔴 VPN — when it can come off

**US-blocked: El Autobús Mágico (done), Sailor Moon Primera Temporada / R / S /
Películas.** On **Canada**, which works for everything except 5 Jorge videos.
Poland / USA / Germany / France are blocked for the main catalogue.

The blocked Sailor Moon content is fetched FIRST. Watch for **Sailor Moon
127/200** (Películas is already done at 2/2), or the log line:

    >>> BLOCKED SAILOR MOON CONTENT COMPLETE - the VPN is no longer needed

Everything after is unblocked, and the last three shows are archive.org.

- `_tools/check-vpn.sh` — is this exit allowed?
- `_tools/blocked.py` — what is blocked + which countries fix it all; `--retry`
  fetches only those. Now: 5 Jorge videos, 259 countries work.
- Failures are QUIET (`--ignore-errors`). **Watch the count, not the log.**
- **A takedown is NOT a geo-block.** The third Sailor Moon film ("La promesa de
  la rosa") was removed by a Viz Media copyright claim — BOTH uploads — so no
  VPN or retry brings it back. Its target is set to 2 and the reason is recorded
  in the queue script.

## Adult mode — 3 of 4 parts built, nothing wired yet

Browse channel → show → episode, no commercial breaks. Brian's decisions:
**enter by digit sequence** (`000`), **play the next episode in order** when one
finishes, **browse-and-play only** for v1.

| Part | Commit | |
|---|---|---|
| State machine | `2a8c5c7` | `Browser` — cursors, descend/back, `next_episode()` |
| Tree builder | `d85299e` | `tree_from_config` — reads the real lineup |
| List renderer | `7f361db` | `list_ass` — rows, paging, scrim, position |
| Wiring | `?` | `000` to enter, NAV/ENTER/BACK routed, plays with breaks off |

**ADULT MODE IS COMPLETE AND TESTED.** Type `000`, browse channel → show →
episode, choose one; it plays with no advert and the next episode of that show
follows until the show ends, then the box hands back to ordinary television.
Built entirely on the MockPlayer harness — **no television was needed**. What
still wants a screen is only calibration: `ROW_H`, `_ROW_SIZE`, the `>` marker
and `DEFAULT_DIM`, all constants at the top of `browser.py`.

All three are pure (no player, clock or drawing), which is why each was fully
tested before anything touched `app.py`. **The remaining part is the only one
that modifies existing behaviour** — do it carefully and keep the box identical
when adult mode is closed.

### The wiring does NOT need a television

`tests/test_interstitial.py` already builds a real `TVApp` on a `MockPlayer`,
`FakeClock` and `InputManager([])`, drives it with `end_episode(app)` and asserts
what is playing. Everything the last part does can be proven that way:

* `000` on the digit pad opening the browser (`_push_digit` / `_confirm_digits`)
* NAV / ENTER / BACK routed to the browser, the way `_guide_consumes` routes to
  the guide
* the chosen file playing, with **no advert before it**
* `advance()` giving the next episode when one ends, and the mode closing
  cleanly at the end of a show

**What genuinely needs the TV is only calibration**, and none of it is logic:
whether the rows are legible from a sofa, whether `ROW_H`/`_ROW_SIZE` are big
enough, whether the `>` marker reads at distance, and whether `DEFAULT_DIM`
works over real moving video under the CRT shader. All of those are constants at
the top of `browser.py` — tune them on the television without touching a test.

So: build and test the wiring headless next session; save the numbers for when
the box is in front of you.

Design choices worth not re-litigating:
- **Lists STOP at their ends, they do not wrap.** The Guide wraps because a
  cursor parked on nothing reads as broken to a 2-year-old; here the user can
  read, and silently looping a list is worse. What holds instead: you can always
  get back out from any depth.
- **The page follows the CURSOR.** Rugrats has 169 episodes; starting at the top
  would draw 1-12 and hide the selection.
- **Rows, not tiles** — an adult reads names; a pre-reader needs pictures.
- **Underscore folders are never shows.** Found by running against the real
  library, where Clifford appeared as one show called `_staging`.

Still to decide when wiring: whether a channel change exits the mode.

## 🔴 Pipeline order — enforced

**download → split/join → name → file into a channel folder**

`detect-breaks.py` and `name-from-titles.py` look for `ROOT/<show>/_staging`.
Filing a show before it is finished hides the remaining work from them, silently.
`organize-channels.py` refuses to move a show while `_staging` has anything in it.
`status.py` follows shows into channel folders; **the other two do NOT**.

## Jorge — split, 10 of 29 need review (Brian is assessing)

`--black-d 0.05 --pix-th 0.35 --black-only --past-credits`

- `--black-only`: the joins fade the picture while music runs across them.
- `--pix-th 0.35`: the fades never reach full black, and vary per file.
- `--past-credits`: the fade ends the STORY; the credits and yellow cards come
  AFTER it. Samples average frame colour forward, cuts at the near-white title
  card.
- Cuts snap FORWARD to a keyframe: `-c copy` can only start on one and silently
  moves any other time BACKWARDS by up to ~5 s.

**Needs review:** no title card found — `007`, `011`, `026`, `028`, `029`.
Large ~6 s keyframe jump, may overshoot — `005`, `009`, `010`, `012`, `013`,
`026`, `028`. `029` did not split at all.

> Five files agreeing on a timestamp proved the detector STABLE, not CORRECT.
> Only looking at a frame found the defect — and contact sheets misled twice
> because `-ss` before `-i` is not frame-accurate. Average pixel colour was the
> only method that gave the truth.

## Still to split / join

| Show | Files | Job |
|---|---:|---|
| Daniel Tigre | 19 | split — SAMPLE DONE, see below |
| Barney | 11 | split — SAMPLE DONE, needs a different method |
| Dora | 6 | split — up to 4:26 with ~11-min episodes, so MANY cuts each. The 18-min floor that suited Jorge is wrong here. |
| Pistas de Blue y tú | 82 | **join** 60 clips up into ~52 episodes |

### 🔴 START HERE NEXT SESSION — the Jorge repair

Brian reviewed all 29 Jorge splits. **17 have problems**, in three distinct kinds
(my automated flags only caught 10 — his review is the authority):

| | Files | Symptom |
|---|---|---|
| **A** | 006, 008, 014, 016, 018, 020, 021, 023, 024, 025, 027 | `pt02` opens with 4-7 s of the previous episode's credits |
| **B** | 007, 010, 012, 013 | `pt01` runs long carrying the NEXT episode; `pt02` is missing that start |
| **C** | 011 (to 4:17), 026 (to 3:05) | `pt02` carries MINUTES of the previous episode |
| **D** | 028, 029 | uncertain — may be geo-blocked sources; revisit when the missing 5 arrive |

**Group A is solved and proven.** The cause was the seek, not the detection:
`-c copy` used `-ss` BEFORE `-i`, which rounds to the nearest keyframe *at or
before* the requested time - so even after snapping the cut forward onto a
keyframe, ffmpeg could round back down, landing 4-7 s early. That interval is
exactly Jorge's keyframe spacing.

`--reencode` (added to `detect-breaks.py`) seeks with `-ss` AFTER `-i`, which is
frame-accurate and has no keyframe constraint. Measured on file 006:

    _split/ (copy)   t=0.5s yellow credits  t=2s yellow  t=4s yellow
    _reenc/          t=0.5s TITLE CARD      t=2s TITLE   t=4s TITLE

**Next session: re-encode the 11 group A files** (~45 min, ~9 GB), then diagnose
B and C. Re-encoding will NOT fix B or C - their cuts are at the wrong boundary,
so it would only place a wrong cut precisely. **Measure those, do not reason
about them** (I was wrong twice today doing the latter).

**Do not re-encode by default.** Daniel's 4 pieces are 460 MB copied and 1.6 GB
re-encoded - 3.5x - and copying is lossless. Re-encoding is a REPAIR for broken
cuts, not the normal path.

### Daniel and Barney — approved

Brian reviewed both and they are **fine as they are**; a split-second of frames
at some starts, acceptable for a young child's show. The remaining **18 Daniel
and 10 Barney** files can be batch-split with the same settings, stream-copied.

Barney correction: the 30:04 file that refused to split was the SHORTEST of its
set - the other ten run 42:43 to 85:12 and will split normally. "Barney needs a
different method" was a sampling artifact.

### Why the cut is the MIDDLE of the fade, not its end

Tried and reverted. Cutting at the fade's end is better in theory but lands
between keyframes: measured on Daniel, the midpoint snaps 0.04-0.15 s while the
fade-end snaps 4.09-4.17 s, dropping ~4 s of the NEXT episode onto the previous
piece. The midpoint leaves ~1 s of closing fade on the next piece, which is the
far smaller error. Recorded in the code so it is not re-tried.

### Sample splits, for assessment (in each show's `_split/`)

Jorge's settings were used as a baseline. They do NOT transfer:

* **Daniel Tigre** 82:13 → **4 pieces of 20:31-20:36**, very uniform, so the
  boundaries are real. BUT `0 with a credit roll` — no near-white title card was
  found, so the cuts sit on the RAW FADES. That is exactly the state Jorge was in
  when the credits landed on the following piece. **Check the head of pt02.**
* **Barney** 30:04 → **1 piece, no split**. 14 black intervals and 4 joins, all
  rejected by the 18-minute floor — arithmetic, since a 30-minute file cannot
  have a cut with 18 minutes either side. Either it is one 30-minute episode, or
  two ~15-minute ones the floor forbids. Barney also had **1 silence in 30
  minutes** against Daniel's 156, so any silence-based rule is useless there.

`--min-episode` and the credits refinement are per-show settings, not global.

## Channels — config written (`06b17c7`), three still missing

17 channels, one network each, age splitting the blocks, ASCII paths. 38 shows
already filed by `organize-channels.py`.

**All three added (`d3a1c2f`)** — Aprende (19), Ejercicio (20), Cantonés (21),
each `breaks: false`, and all three are in the `organize-channels.py` mapping.
**20 channels now.** Cantonés is the first non-Spanish content; its playlists are
age-banded by the uploader (0-3, 3-5, 6+, parent-child) in one folder, so
splitting into separate channels later is a file move.

Note the channel PATH is ASCII (`/media/tangbox/Cantones`) while the show folder
keeps its accent — macOS and Linux disagree on accent encoding, and only `path:`
has to survive both.

## Code shipped this session

`4e1b936` `ChannelConfig.age` · `b327d77` guide detail row (under the grid, not
on tiles — a tile with artwork draws no ASS at all) · `a74819b` **stickiness**
(a `- ptNN` run plays back to back; **the suffix is load-bearing**, coupling
`detect-breaks.py` to `playlist._PART`) · `06b17c7` the 17-channel lineup ·
`69238ac` **`breaks: false`** · `2a8c5c7` + `d85299e` + `7f361db` adult mode.

**665 tests pass.** `age` and the guide detail row are still inert — `app.py`
does not pass `ages`/`shows` into `guide_ass`.

## Tools (`Converted/_tools/`)

`get-playlist.sh` (`$MATCHFILTER`, `$PLAYLIST_ITEMS`) · `get-archive.py`
(`$NAME_FILTER`) · `run-queue15.sh` · `detect-breaks.py` · `name-from-titles.py`
· `organize-channels.py` · `check-vpn.sh` · `blocked.py` · `check-exfat.py`
(**re-run before copying to USB**) · `status.py` / `watch-status.sh`

## Decisions

- Discard over 1.5 h, EXCEPT Dora's six COMPLETOS.
- **Dora**: 26 short "EPISODIO COMPLETO" + 6 long "COMPLETOS" only. The other 26
  long videos are best-of / song / funny-moment reels — fragments duplicating
  what the six hold whole. ~70 h skipped for no loss.
- **Bear**: `$NAME_FILTER="latin spanish"` — the item holds 4 languages.
- **Sailor Moon films: 3 uploaded twice**, and one is taken down → 2 obtainable.
- **El Autobús Mágico: episodes only.**
- YouTube titles ARE allowed in filenames; multi-story episodes use the
  **fullwidth ｜ (U+FF5C)**, never ASCII `|` (exFAT forbids it).
- Don't rebalance channels on episode count.

## Gotchas — each cost real time

- **`pkill -f` matches your own shell.** Kill in a SEPARATE call from any that
  names the script (3 self-kills). Match `run-[q]ueue`; refer to files by a glob
  avoiding the literal (`run-*ueue15.sh`).
- **Killing a wrapper does not kill `yt-dlp`** — kill by SHOW NAME.
- **`ffmpeg -ss` BEFORE `-i` is not frame-accurate.** Put it AFTER when the
  timestamp matters.
- **`-c copy` snaps cuts BACKWARDS to a keyframe**, silently, by up to ~5 s.
- **`ffmpeg` in a `while read` loop eats the loop's stdin** — add `</dev/null`.
- **Progress lines use `\r`** — `tr '\r' '\n'` before grepping.
- **zsh** aborts a loop on an unmatched glob; does not word-split unquoted vars.
- **Some folders are stored NFD** (`Pistas de Blue y tú`); `Path.exists()` hides
  it, set arithmetic does not.
- Python buffers stdout when not a tty.
- **Run new tools against the REAL library, not just fixtures.** That is what
  caught `_staging` being offered as a show.

## Carried over

**Plaza Sésamo has never been copied to the USB drive** (now under
`PBSPequenos/`). `Lineup` L2/M2 hold *US Sesame Street* totals. The
`Seasons breakdown` tab does not exist. Many new shows need `Lineup` rows —
Clifford, El Autobús Mágico, Arthur, Sailor Moon, Dora, Bear, Cantonés, and the
three learning channels.

## Repo

Clean apart from this file. Eight commits pushed to `main`. Media work lives in
`~/Downloads/Converted/`.
