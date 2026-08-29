# Session wrap — 17 shows, the channel config written (2026-08-29)

Downloads run without Claude. **Check them at
`/Users/briantang/Downloads/Converted/_status.html`** — self-refreshing, now in
DOWNLOAD ORDER with each show's source (YouTube / archive.org), plus a bar for
the 1 TB drive.

    running now   ps -Ao args= | grep -E '[y]t-dlp|run-[q]ueue'
    queue log     tail -f ~/Downloads/Converted/_queue.log
    stop the queue  kill the run-queue pid; then kill yt-dlp BY SHOW NAME
    resume        cd ~/Downloads/Converted && nohup ./_tools/run-queue15.sh >> _queue.log 2>&1 &

## State — 419 / 983 videos, 17 shows, 257 GB (26% of the drive)

**Seven complete:** Franklin 78, Barney 41, Pistas de Blue y tú 82, Clifford 77,
El Autobús Mágico 50, Daniel Tigre 61, and Jorge 29/34 (5 geo-blocked).

Downloading: Sailor Moon Películas, then the Sailor Moon blocks.
Queued after: Dora 32, Cosmic Kids Yoga 11, Spanish Basics 22, Aprende Peque 34,
Cantonés 102, then **archive.org last** — Arthur 65, Dragon Ball Z 57, Bear 34.

## 🔴 VPN — geo-blocking, and when it can come off

**US-blocked: El Autobús Mágico (done), Sailor Moon Primera Temporada / R / S /
Películas.** Currently on **Canada**, which works for everything except 5 Jorge
videos. Poland/USA/Germany/France are blocked for the main catalogue.

The queue fetches the blocked Sailor Moon content FIRST, so the VPN can come off
early. Watch for **Películas 3/3 and Sailor Moon 127/200**, or the log line:

    >>> BLOCKED SAILOR MOON CONTENT COMPLETE - the VPN is no longer needed

Everything after that (Súper S, Sailor Stars, Dora, the learning channels,
Cantonés) is unblocked, and the last three shows are archive.org.

- **`_tools/check-vpn.sh`** — is this exit allowed? One probe per show.
- **`_tools/blocked.py`** — what is still blocked, and which countries would fix
  it (it intersects the "available in" lists). `--retry` fetches only those.
  Right now: 5 Jorge videos; 259 countries work, including Mexico/Spain/UK.
- Failures are QUIET: `--ignore-errors` skips blocked videos and yt-dlp often
  says only `Video unavailable`. **Watch the count, not the log.**

## 🔴 The pipeline order — enforced, and why

**download → split/join → name → file into a channel folder**

`detect-breaks.py` and `name-from-titles.py` look for `ROOT/<show>/_staging`.
Filing a show into its channel folder before it is finished puts the remaining
work somewhere those tools cannot see, silently. `organize-channels.py` now
refuses to move a show while anything is left in `_staging`.

The same assumption broke the status page when Franklin moved to `NickJr/` and
read "not started" with 78 episodes on disk. `status.py` now follows shows into
channel folders; the two splitting/naming tools still do NOT.

## Jorge — split, but 10 of 29 need review (Brian is assessing)

Settings that work: `--black-d 0.05 --pix-th 0.35 --black-only --past-credits`

- `--black-only` because the joins fade the picture while music runs across them.
- `--pix-th 0.35` because the fades never reach full black, and vary per file.
- `--past-credits` because the fade ends the STORY; the credits and the yellow
  "¡No te vayas!" cards come AFTER it, and cutting on the fade hands them to the
  next episode. It samples average frame colour forward and cuts at the near-white
  title card.
- Cuts are then **snapped FORWARD to a keyframe**, because `-c copy` can only
  start on one and silently moves any other time BACKWARDS by up to ~5 s.

**Needing review:** no title card found (fell back to the raw fade) — `007`,
`011`, `026`, `028`, `029`. Large keyframe jump ~6 s, may overshoot into the
episode — `005`, `009`, `010`, `012`, `013`, `026`, `028`. `029` did not split.

> **The lesson that cost the most:** five files agreeing on a timestamp proved
> the detector was STABLE, not CORRECT. Only looking at a frame found the
> credits on the wrong piece. And two contact sheets misled me because `-ss`
> before `-i` is not frame-accurate — measuring average pixel colour was the
> only method that gave the truth.

## Still to split / join

| Show | Files | Job |
|---|---:|---|
| Daniel Tigre | 19 | split (42 singles already named) |
| Barney | 11 | split (30 singles already named) |
| Dora | 6 | split — up to 4:26 each, ~11-min episodes, so MANY cuts per file. The 18-min floor that protected Jorge is wrong here. |
| Pistas de Blue y tú | 82 | **join** 60 clips up into ~52 episodes |

## Naming — done for Franklin, Daniel, Barney

`name-from-titles.py`, dry-run by default. YouTube titles ARE allowed (the
no-titles rule bans *looked-up database* titles — a YouTube title comes from the
video and cannot be mismatched). Multi-story episodes use the **fullwidth ｜
(U+FF5C)**, never ASCII `|`, which exFAT forbids.

Four bugs it caught, all of which would have shipped silently:
season markers ("Temporada 3") arriving as story titles; the show name repeated
inside its own filename; only ONE of Barney's two playlists supplied, leaving 20
files unmatched; and **colliding episode numbers** — both playlists number from
001, so six numbers appeared twice. It now detects collisions and renumbers.
**Sailor Moon comes from five playlists**, so that guard matters.

## Channels — CONFIG IS WRITTEN (`06b17c7`)

17 channels, one network each, age splitting the blocks, ASCII paths.
`config.pi.yaml` no longer holds the old five. 38 shows are already filed into
their channel folders by `organize-channels.py`.

**Three channels still need adding** — all want `breaks: false`:

| Channel | Shows | Videos |
|---|---|---|
| Aprende | Spanish Basics, Aprende Peque con Isa | 56 |
| Ejercicio | Cosmic Kids Yoga | 11 |
| Cantonés | four learning playlists (one folder) | 102 |

They also need entries in `organize-channels.py`'s mapping or their folders
cannot be filed. Cantonés is the first non-Spanish content on the box; its four
playlists are age-banded by the uploader (0-3, 3-5, 6+, parent-child) and land in
one folder, so splitting into separate channels later is a file move.

## Code shipped this session

- `4e1b936` `ChannelConfig.age` — drawn on the channel banner.
- `b327d77` guide detail row — age + shows under the grid. **Under the grid, not
  on tiles, because a tile with artwork draws no ASS at all** (mpv puts bitmaps
  above ASS, so its text is burned into the picture).
- `a74819b` **stickiness** — `ShowOrder` holds a show while it is part-way through
  a `- ptNN` run, so a split film plays `pt01 → break → pt02` back to back. This
  is what lets a film be split at all. **The `- ptNN` suffix is now load-bearing**,
  coupling `detect-breaks.py` to `playlist._PART`.
- `06b17c7` the 17-channel lineup.
- `69238ac` **`breaks: false`** — a channel can opt out of adverts entirely.
  Defaults true; opting one channel out must not disable breaks elsewhere.

**639 tests pass.** `age` and the guide detail row are still inert: `app.py` does
not pass `ages`/`shows` into `guide_ass` yet. `shows` can come from listing each
channel folder's subdirectories, computed once at start-up.

## Parked: "adult mode"

Browse channel → show → episode and watch without breaks. **Assessed as
tractable, not a rewrite.** Most of it exists: `breaks: false`, the `Guide` pure
state machine (cursor rules that never land on nothing, paging, fully tested),
`_guide_consumes` input routing, `ShowOrder`'s show→episode grouping, and
`_play_request(PlayRequest(path=...))` to play any file. What is new: two more
browse levels, a list renderer (simpler than the tile grid), and a way in.

Decide first: how to enter it without a child finding it (Flirc buttons are
scarce); what happens when the chosen episode ends; whether a channel change
exits it. Biggest risk is scope — it can quietly become a full media browser.

## Tools (`Converted/_tools/`)

| File | Does |
|---|---|
| `get-playlist.sh` | YouTube → `_staging`. H.264, ≤1.5 h. `$MATCHFILTER`, `$PLAYLIST_ITEMS`. |
| `get-archive.py` | archive.org → `_staging`. Picks the best format present; `$NAME_FILTER` for multi-language items. |
| `run-queue15.sh` | One show at a time, retried until it stops progressing. |
| `detect-breaks.py` | `--black-only --pix-th --past-credits --split`. Snaps cuts to keyframes. |
| `name-from-titles.py` | Names from YouTube titles; caps at 30 min; fixes number collisions. |
| `organize-channels.py` | Files finished shows into channel folders. |
| `check-vpn.sh` / `blocked.py` | Geo-block checks and targeted retry. |
| `check-exfat.py` | Every name legal on the drive. **Re-run before copying.** |
| `status.py` / `watch-status.sh` | `_status.html`. |

## Decisions

- Discard anything over 1.5 h, EXCEPT Dora's six COMPLETOS compilations.
- **Dora**: only 26 short "EPISODIO COMPLETO" + 6 long "COMPLETOS". The other 26
  long videos are best-of/song/funny-moment reels — fragments duplicating what
  the six already hold. ~70 h skipped for no loss.
- **Bear**: `$NAME_FILTER="latin spanish"` — the item holds 4 languages.
- **Sailor Moon films: 3, not 6** — each is uploaded twice. `PLAYLIST_ITEMS=1-3`.
- **El Autobús Mágico: episodes only** — its 41 compilations duplicate the 50.
- A 20-25 min piece is a finished episode even when it is two shorts joined.
- Don't rebalance channels on episode count; Brian is filling the thin ones.

## Gotchas — each cost real time

- **`pkill -f` matches your own shell.** Kill in a SEPARATE call from any that
  names the script (3 self-kills, exit 144). Match `run-[q]ueue`, and refer to
  the file by a glob that avoids the literal (`run-*ueue15.sh`).
- **Killing a wrapper does not kill `yt-dlp`** — kill by SHOW NAME.
- **`ffmpeg -ss` BEFORE `-i` is not frame-accurate.** Put it AFTER when the
  timestamp matters. Two contact sheets lied because of this.
- **`-c copy` snaps cuts BACKWARDS to a keyframe**, silently, by up to ~5 s.
- **`ffmpeg` in a `while read` loop eats the loop's stdin** — add `</dev/null`.
- **Progress lines use `\r`** — `tr '\r' '\n'` before grepping, or errors and
  filenames glued to a progress line are invisible.
- **zsh** aborts a loop on an unmatched glob and does not word-split unquoted
  variables.
- **macOS stores some folder names decomposed (NFD)** — `Pistas de Blue y tú` is
  NFD while every other accented folder is NFC. `Path.exists()` hides it; set
  arithmetic does not.
- Python buffers stdout when not a tty; background jobs look empty until done.

## Carried over — still outstanding

**Plaza Sésamo (80 episodes) has never been moved to the USB drive** — it is now
filed under `PBSPequenos/`. Also open: `Lineup` L2/M2 hold *US Sesame Street*
totals so its bar reads 80/4662; the `Seasons breakdown` tab documented in
CLAUDE.md does not exist; and several new shows need `Lineup` rows (Clifford,
El Autobús Mágico, Arthur, Sailor Moon, Dora, Bear, Cantonés, the learning ones).

## Repo

Clean apart from this file. Five commits pushed to `main`. All media work lives
in `~/Downloads/Converted/`.
