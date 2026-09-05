# Session Wrap — 2026-09-03/04

## What happened
Three shows filed (Lucas, Numberblocks, Octonautas) into a NEW channel,
Patoaventuras closed out at 48, five shows blocked and parked, the USB drive
finally installed so the box actually plays, and four real bugs found — an
ffprobe storm that blocked the main loop for 68 seconds (the remote lag), one
in `bundle-clips.py`, one in `app.py`'s resume, and 22 badly-matched video
files.

## Library: 23 channels, 69 shows, 4,017 episodes, ~1,509 hours.
Mac 662 GB; drive 656 GB used / 266 GB free.

## Filed this session
| Show | Eps | Min | Channel |
|---|---|---|---|
| La arana Lucas | 30 | 654 | Netflix Jr (new) |
| Numberblocks | 47 | 871 | Netflix Jr |
| Octonautas | 85 | 1,721 | Netflix Jr |
| Patoaventuras | 48 | 1,080 | Disney Aventura |

Patoaventuras' existing S01E01 was KEPT — 720p @ 2392 kbps vs the new 480p @
710 kbps. Diff-before-replace held again.

## NEW CHANNEL: Netflix Jr (19), age 2-6
Netflix was merged FROM two thin channels the day before, so splitting it
again needed justification: this time it came with 162 episodes behind it, not
a channel holding one show. Younger sits first, as with PBS/Apple/Anime.
Netflix -> 20, Anime Kids -> 21, Anime -> 22, Cantones -> 23, Journey -> 24.
Pushed (`5ecec67`), validated with `load_config`, live on the Pi — startup log
confirms 23 channels.

## `bundle-clips.py` — CORRECTED, and now has an end-to-end check
🔴 **An earlier version of this wrap said the tool "only verifies a block is
not too SHORT". THAT WAS WRONG.** The check is `abs(got - secs) > 5`, which
catches too-long exactly as well as too-short. The claim came from misreading
the MESSAGES ("short by...", "STILL SHORT") for the logic.

So the 144-minute Octonautas block has a different explanation, and it is the
one that fits: an ORPHANED ffmpeg from an earlier killed run was still writing
the same filenames. The bundler verified each block correctly at the moment it
checked, and a stray process overwrote them afterwards. No in-process check can
catch that.

What mixed RESOLUTIONS actually do (the real defect, still true): ffmpeg's
concat FILTER cannot handle differing dimensions and time-STRETCHES rather than
truncating. Fixed by normalising every clip to one resolution first
(`scale=W:H:force_original_aspect_ratio=decrease,pad=...,setsar=1`) plus
`-fps_mode cfr` (`-vsync` is GONE from this ffmpeg).

FIXED 2026-09-04 (Mac only — `_tools/` is NOT in git, and was deliberately left
off the USB drive):
- Messages now say "LONG by" / "short by" correctly, and a failed block reads
  WRONG LENGTH rather than STILL SHORT.
- **A total check at the end**: sums the staged clips against the finished
  blocks re-probed from disk, prints `minutes in -> out`, and on a mismatch
  over 10s prints "DO NOT FILE THESE. Check for a stray ffmpeg" and exits 1.
  That is the check that actually caught the problem, so it now lives in the
  tool rather than in somebody's head.
- Verified both branches: a clean run reports 85.1 -> 85.1 MATCH; a block
  swapped for a longer one reports 85.1 -> 87.9 MISMATCH +2.8 min and exits 1.

⚠️ ALWAYS `ps -eo command | grep ffmpeg` before relaunching anything that
writes files. Killing a parent leaves its ffmpeg children alive, and they do
not match a `pkill -f` on the parent's name.

## Dedupe by AUDIO, never by title or duration
All three shows arrived full of re-uploads under different Spanish titles.
Filenames disagree and durations disagree too — episodes cut to a fixed
broadcast slot share durations by chance, which produced outright FALSE pairs.
Audio-envelope correlation (>0.97) got it right every time:

| Show | Downloaded | Dupe pairs | Unique |
|---|---|---|---|
| Lucas | 139 | 12 | 127 |
| Numberblocks | 154 | 33 | 121 |
| Octonautas | 143 | 16 | 127 |

Tool: `scratchpad/dedupe.py` (worth moving into `_tools/`). `--apply` keeps the
larger file of each pair. Confirmed by title: `HOGAR DULCE HOGAR` =
`UNA CASA DELICIOSA`, `LA CASA RESPIRA` = `LA CASA ESTA VIVA`.

## 🔴 Half of Octonautas is 360p — owed a re-pull
43 ten-minute clips + 20 twenty-minute episodes came down at 640x360. For those
episodes YouTube offers 480p ONLY in VP9/AV1, and the Pi 5 cannot hardware-
decode AV1 — but **H.264 IS available at 720p**. Per Brian's own rule (480p if
available, else 720p) they should be 720p, not 360p. The selector treated
"<=480" as satisfied by 360p instead of escalating. ~63 episodes, ~2.8 GB.
Fix the format chain before re-pulling.

## 🔴 YouTube rate-limited us
"Sign in to confirm you're not a bot" after ~470 downloads. No further YouTube
pulls until it clears, or pass browser cookies. VPN is currently OFF (Comcast
residential IP).

## Compilations have no episode boundaries — get the playlist instead
The three Lucas hour-longs carry no chapters, no black frames, nothing
detectable. Brian supplied splitpoints by eye (21:05/38:12, 29:48, 17:24/37:03)
and they cut clean at zero drift. NOTE: two cuts landed exactly on a CARTOONITO
bumper, so bumpers DO exist — an earlier claim that there were none was wrong;
they are just brief enough to fall between 40-second contact-sheet samples.
The 181-video playlist superseded the compilations entirely.

## Five shows PARKED — all behind one gateway
Sharkdog, StoryBots, La Isla de las Figuras, Jugando con Winnie Pooh,
El show de Snoopy. All route through `xupalace.org` -> `embed69.org`.

🔴 **CORRECTED — do NOT build an "embed69 resolver".** An earlier note in this
wrap called that the highest-leverage work. It was wrong on both counts, and
the page source proves it. embed69 has **no obfuscation whatsoever**: the real
link sits in plain HTML as
`onclick="playServerVast('https://streamwish.to/e/...')"`. A regex would read
it — and it hands back the SAME StreamWish URL already sitting in the show
TSVs, which yt-dlp already rejects. The gateway was never the obstacle.

The actual wall is the HOST layer — StreamWish, VOE, Doodstream, FileLions.
StreamWish serves a 452-byte "Page is loading" shell that pulls a **71 KB
string-array-obfuscated** `main.js` (obfuscator.io style: `fetch`, `atob`,
`token` and every endpoint appear ZERO times as readable text; strings look
like `'Ag/cSmkmrq'`). That is a much harder target than the packed-JS used by
VidHide/cubeembed, which had a known unpacking method. Hand-decoding is not
worth it.

**If these shows are ever wanted: drive the page with Playwright** (already in
the toolchain), let their own script run, and capture the video request off the
network. That sidesteps the obfuscation entirely instead of fighting it, and
generalises to all four hosts. Optional — five shows against a 4,018-episode
library.

Snoopy differs at the gateway: `xupalace.org` returns **HTTP 444** (deliberate
blocking) even with browser headers, where the others give a plain
unsupported-URL error. It is a 36-episode source for a show pruned earlier as
a single-episode stub, so it is the one most worth recovering.

## 🔴 THE REMOTE LAG WAS A 68-SECOND ffprobe STORM (FIXED `57f2650`, `951251d`)
**This is the real cause. The 22-file section below is a genuine but SEPARATE
defect — it did not fix the lag.**

Every channel is `broadcast`. Building a channel's schedule probes EVERY episode
with `ffprobe`, synchronously, **on the main loop**, the first time anyone tunes
there. Measured on the Pi with the library on USB:

```
117 ms per probe x 493 episodes (Anime)  =  68.5 s of BLOCKED MAIN LOOP
Nick Clasico 75 s · Nick Moderno 55 s · Disney Jr 48 s · Cartoon 40 s
```

Input is read on a SEPARATE THREAD and queued, so presses were never lost —
they piled up and fired all at once when the storm ended. Brian: *"I pressed a
number of sequential buttons and nothing happened for a little bit, then all
the actions cascaded onscreen."* **That sentence is what cracked it.** Queue-
then-cascade = blocked loop. A failing remote LOSES presses; it does not bank
and replay them in order.

🔴 **Why it appeared only now: empty channels return early and never build a
schedule.** The bug was always there and was invisible until the USB drive gave
the channels content. Anyone reading the git history will not see this.

### The fix
`probe.py` now caches durations to `~/.cache/tangbox/durations.json` (SD card —
the library drive is read-only on purpose), keyed by path and validated against
**size + mtime**, so re-encoded files self-invalidate. Written atomically.

```
channels     68.5 s -> 0.01 s      commercials  15.0 s -> 0.006 s
cache: 4,164 entries, 587 KB (4,018 episodes + 146 adverts), fully warmed
```

Two flush paths, because there are two kinds of caller:
- `channel.py::_ensure_broadcast` flushes explicitly after its loop.
- The LAZY callers — `interstitial.py` drawing a break clip, `app.py:1220`
  timing the current episode — probe one file at a time and had NO flush, so
  all 146 adverts were re-probed every boot (~102 ms each, a hitch mid-break).
  `probe_duration()` now self-flushes every 20 new entries, so any caller
  persists without knowing the cache exists.

### Diagnostic lessons — this took far too long
- **Ask what the failure LOOKS like before measuring.** CPU, I/O wait, thermals,
  CEC, memory, codecs and the IR path were all measured clean — because they
  were sampled BETWEEN storms. One sentence describing the symptom beat six
  clean measurements.
- **A kernel-level input capture cleared the remote** (`/dev/input/event1`, 23
  presses, none lost, no bunching). Worth keeping: it is how you prove the IR
  path is innocent.
- Backgrounding over SSH kept silently failing (exit 255, stale logs). Write the
  script locally, `scp` it, run it in the FOREGROUND.

## 🔴 22 BADLY-MATCHED VIDEO FILES (real, but NOT the lag)
Found while hunting the lag. It did NOT fix the lag (see above) but is a real
defect worth having fixed. The Pi 5 has NO hardware H.264 decoder — everything
is software-decoded. `Dragon Ball Z S01E01` was 1920x1080 @ 4.64 Mbps sitting among
290 files at 848x480 @ 0.57 Mbps: **4.3x the decode cost**, measured
(8.6x realtime vs 37.1x). That was enough to starve input handling.

What made it feel like hardware: `ShowOrder` starts every show at its FIRST
episode, so the one odd file was reliably the first thing played. Land on the
channel, remote goes slow, every time.

**The pattern repeated 10 times.** A first episode gets grabbed alone as a
sample at whatever quality was going; the series is bulk-downloaded later at
something lower. A library-wide scan (`scratchpad/outliers.py`, worth moving to
`_tools/`) found 645 outliers — 157 heavier than their siblings, 488 lighter.

**22 files normalised** to their own show's modal resolution and median bitrate:
DBZ, then Jake Long (9.0x!), Lilo y Stitch, Tres Caballeros, Patoaventuras,
Mighty Ducks and Pokémon first episodes, then the remaining 15 heavy files in
Pokémon and Mighty Ducks. Every one verified for duration drift AND decode
before swapping, on the Mac and the drive. Verified after: fixed episodes now
decode at or better than their siblings.

- Originals kept as `_orig_*.mp4.keep` — **22 files, 6.3 GB**, Mac only,
  excluded from playback by the `_*` rule. They are the only higher-res copies
  and several sources are dead. Not deleted without Brian saying so.
- ⚠️ **Patoaventuras S01E01 was one of them** — the file kept EARLIER the same
  session under "diff before replacing, keep the better copy". That rule
  optimises for quality and creates decode outliers. Both instincts are right;
  they point opposite ways. On a 480p library behind a CRT shader, consistency
  won.
- LESSON FOR FUTURE DOWNLOADS: match the sample episode to whatever the bulk
  download produces, or re-pull the sample after. This is what created all 22.
- Three files still read as "heavy" (486x360, 470x360, 478x360 against a
  480x360 norm). Ignore them — 1% dimension variation, two are SMALLER.

## Writing to the drive: remount, do it, remount back
```
sudo mount -o remount,rw /media/tangbox
... replace files ...
sync && sudo mount -o remount,ro /media/tangbox
```
Check nothing is playing the target file first:
`for p in $(pgrep -f "tangbox|mpv"); do ls -l /proc/$p/fd | grep -o "/media/tangbox/.*"; done`
Remounting does NOT disturb open reads; replacing a file being played would.

⚠️ **The Pi's `/tmp` is a 2 GB tmpfs (RAM).** Staging 17 files there filled it
and four `scp`s failed with "write remote: Failure". `scp` STRAIGHT to the
destination under `/media/tangbox/...` while it is rw — the mount is uid=1000,
so brian owns it.

## 🔴 RESUME WAS BROKEN — `app.py` checked the GLOBAL setting (FIXED `22dcf47`)
```python
if self.config.tune_in != "resume" ...:   # WRONG: global, which is 'broadcast'
    return                                 # so it returned EVERY time
```
`_remember_position()` tested `self.config.tune_in` — the global default — not
the channel's own mode. It therefore returned early on every call and no
position was ever saved. `Channel.tune_in()` then looked for a saved position
that nothing had ever written, so a `resume` channel silently restarted its
episode instead. Now reads `self.lineup.current.tune_in_mode`.

Nasty because it LOOKS like a config error: the channel setting was right, the
code reading it was right, only the code WRITING the position was wrong, and
nothing logs an error. Found only because Brian reported the symptom.

The fix is correct but now DORMANT — no channel uses `resume` any more.

## The Anime channel went through three modes in one evening
`resume` → `random` → `broadcast` (final, `4476d45`), each decided by watching
it on the actual television:
- `resume` dropped him mid-episode at the second he left. Not what standby
  should do.
- `random` gave the next episode in sequence from its start — it falls through
  to `_next_shuffled()`, so `episode_order: sequential` still applied.
- `broadcast` (Brian: "for simplicity, let's treat the anime channel like the
  rest") — no override at all now.

⚠️ **Accepted cost: broadcast builds its own shuffled running order and IGNORES
`episode_order: sequential`, so DBZ and Sailor Moon no longer play in episode
order.** The `sequential` line is KEPT but marked inert in the config, because
it is what the channel wants if it ever comes off broadcast.

## Guide fixes: the tile lied, and the dots pointed the wrong way

### 🔴 The guide showed one show and tuned to another (FIXED `2a76474`)
Brian: *"guide tile shows sailor moon, but i click and land on dbz"*. Measured
before the fix: **ALL 23 channels disagreed** between what the guide drew and
what tuning played.

`peek_next()` refused to build a broadcast schedule and fell through to the
SHUFFLE BAG, while `tune_in()` built one and played what was airing on the
SCHEDULE. Two different answers for every channel not yet tuned to.

The refusal was deliberate and, when written, right — its docstring says
building a schedule was *"far too slow to do while somebody is holding a
remote"*, which was the 68-second ffprobe storm. **Caching durations removed
that constraint, which is what made this fixable rather than a choice between
two bad options.** After: 0 of 23 disagree.

⚠️ This got WORSE tonight through no fault of its own: moving every channel to
`broadcast` made every channel subject to it. Under `random` or `resume` the
two paths agreed. Three symptoms — the lag, the cascade, the lying guide — all
traced back to one missing cache.

### Page dots now run DOWN the centre gutter (`9442fae`)
They were crammed along the bottom AND said the wrong thing: `down()` carries
onto the next page keeping your column, so paging is a VERTICAL movement and a
horizontal row of dots implied sideways. (Worth knowing: the guide already
scrolled vertically — only the indicator was misleading.)

Vertical only when the column count is EVEN, because then the canvas centre is
a gutter and not a tile; an odd count keeps the bottom row. With the 2x2 page
the gutter runs x=567-713, so 18px dots have 146px of room.

The bottom strip is no longer reserved when the dots are vertical, so the grid
gets it back: **tiles 399x299 -> 421x316**.

## `episode_order: sequential` now works under broadcast (`80d44ee`, `90983c4`)
Brian: serialised shows should play in order while the channel still rotates
randomly between its shows. `ShowOrder` already means exactly that — but
broadcast IGNORED it and built one flat shuffle, so **Nick Acción and Anime had
been asking for sequential order and silently not getting it.**

`BroadcastSchedule` now takes an optional `show_key`, and `_sequential_order()`
groups episodes by show, keeps each show in order, and picks the next show
**WEIGHTED BY EPISODES REMAINING**.

🔴 **The weighting is the whole trick, do not "simplify" it.** ShowOrder hands
each show out once per turn regardless of length — fine for a live generator,
wrong for a finite loop. Drawing naively, Sailor Moon (202) would wrap and
repeat while DBZ (291) was two thirds through, so the cycle would both REPEAT
and OMIT episodes. Weighting makes both run out together. Pleasant side effect:
a long series against a short one interleaves proportionally rather than
alternating, which is what a real station did.

| Ch | Channel | Shows |
|---|---|---|
| 10 | Nick Acción | Avatar 61 · Korra 48 |
| 21 | Anime Kids | Pokémon 115 · Digimon Adventure 104 |
| 22 | Anime | Dragon Ball Z 291 · Sailor Moon 202 |
| 14 | Disney Acción | Gargoyles 78 · Jake Long 51 · Street Sharks 40 · Mighty Ducks 26 |
| 24 | Journey to the West | 42 (single show, nothing to interleave) |

Disney Acción is the one set for a SINGLE show's benefit — only Gargoyles has
arcs; the other three are episodic and come along. Cost: each now opens at its
own episode 1 rather than anywhere in its run. Watch Mighty Ducks (26, the
shortest) for repetitiveness.

Each verified: every episode exactly once per cycle, every show in sequence,
shows interleaved randomly.

Still available if wanted: Kim Possible, Rocket Power (light continuity only).
NOT the preschool channels — no continuity there, and sequential would make each show always open
on episode 1 rather than anywhere in its run.

## The cache does NOT pin the box to one episode
Asked and answered: it stores DURATIONS only — a static fact per file. What
plays is `schedule.at(now)`, a function of the clock, built from a FIXED epoch
long before the box existed. Demonstrated on Anime: now, +25 min, +60 min,
+3 h and +24 h each gave a different episode. Turn the box off for an hour and
the channel has moved on an hour, as a real station would.

## `scripts/audit-agreement.py` — the regression guard (`9b6c0bf`)
Every bug this session had one shape: something claimed success, or two paths
that should have agreed quietly did not, and nothing logged a word.

🔴 **Static checks CANNOT find this class.** `episode_order` WAS referenced —
just in one path and not the other. A grep for "config fields never used
outside config.py" returned four hits and ALL FOUR were false positives
(`default_shuffle`, `media_root`, `start_number` belong to the auto-discovery
path this config deliberately does not use; `seasons` is a local variable).
Comparing ANSWERS is the only method that worked.

Seven read-only checks, safe while the box is playing:

| | Check |
|---|---|
| A | guide tile == the episode tuning actually plays |
| B | `peek_next()` does not consume |
| C | `advance()` follows the same schedule as tuning |
| D | each channel's declared `episode_order` is genuinely honoured |
| E | the cycle covers every episode exactly once |
| F | the schedule moves with the clock |
| G | no episode on disk is unreachable |

`cd ~/TangBox && python3 scripts/audit-agreement.py` — currently **7/7 pass**.
A found 23/23 disagreeing three hours earlier; D is what would have caught
`sequential` being silently ignored. Passing now proves the fixes hold; it has
not discovered anything new, and that is the point of a guard.

## `media-tools/` IS `~/Downloads/Converted/_tools` (`0f77dfa`)
The tools that built the whole library were UNTRACKED — no history, no second
copy, and deliberately kept off the USB drive. One folder on one Mac.

Now 87 files (38 shell, 28 Python, 15 JSON, plus `_records`), 0.4 MB, in git.

**MOVED, not copied**, with the old path symlinked to it:
```
~/Downloads/Converted/_tools -> tang-box/media-tools
```
A copy would drift while still looking version-controlled — the exact failure
this project keeps producing. Several tools hardcode
`/Users/briantang/Downloads/Converted/...` and still resolve through the
symlink; verified, including `get-xiaolin.py`'s absolute path to
`.venv/bin/gdown`.

⚠️ `.venv` (20 MB, 98% of the folder) is gitignored but must stay PHYSICALLY
there for that hardcoded path. Recreate:
`python3 -m venv .venv && .venv/bin/pip install beautifulsoup4 requests gdown`

If the symlink is ever lost:
```sh
ln -s /Users/briantang/BluuClaude/tang-box/media-tools \
      /Users/briantang/Downloads/Converted/_tools
```

## Full-library decode sweep — 4,018 files, 4 real defects (1 fixed)
Ran `media-tools/decode-sweep.py` over every playable episode: 314 minutes,
8 workers on the Mac. **39 flagged raw; only 4 had missing footage.**

🔴 **CLASSIFYING BY ERROR TEXT FAILED TWICE. Only one test works:**
```
does the file decode to its STATED duration?
```
- First I counted `[null @ ...]` lines as corruption. They are the null MUXER
  complaining about timestamps it was handed — **my own harness**, not the
  file. 19 of 39 were this. All 8 flagged Los guardaespíritus episodes are
  perfectly fine.
- Then I read `Invalid data found when processing input` as truncation. 13 of
  those 15 play in full.
- I reported "2 real defects" having length-tested only 15 of 39. Testing the
  other 24 found **two more**, the worst in the library.

| Episode | Missing | Outcome |
|---|---|---|
| Jimmy Neutron S01E04 | 10.1 min of 23.4 (43%) | 🗑️ **DELETED** 2026-09-04 |
| Jimmy Neutron S01E16 | 5.9 min | no source recorded |
| Dragon Ball Z S05E79 | 3.5 min | ✅ **FIXED** |
| Gargoyles S01E40 | 3.1 min | source truncated AT ORIGIN |

The other 35 decode to full length — no content missing. (Not the same as "no
visible glitch": nothing was watched.)

### DBZ S05E79 fixed, the other three cannot be
- The RECORDED source (`DBZ-Cloverway-Episodes`) holds eps 001 + 146-224 — no
  278, HTTP 404. Found an alternative by searching archive.org:
  `dragon-ball-z-etc-tv` ("[LACRA's] ... [291-291]"), 292 files, episode 278
  complete at 140 MB. Swapped on Mac AND drive; damaged copy kept as
  `_orig_truncated_S05E79.mp4.keep`.
  ⚠️ It is 640x480 where the old was 848x480 — a complete episode at slightly
  lower resolution beat one that stops before the ending, on a channel that now
  plays in sequence.
- **Gargoyles S01E40: re-downloading is pointless.** The fetched file is
  BYTE-IDENTICAL (md5 5fc6b746acd5, 45,400,036 bytes) to the one on disk. The
  archived source is itself truncated. `capgarg78` is the only Gargoyles item
  on archive.org.
- **Jimmy Neutron: no provenance at all** — no `_archive.txt`, no
  `_source-titles.json`, no `shows.json` entry. Archive.org has nothing usable.

🔴 **LESSON: the show with NO source records has the WORST damage.** Provenance
costs nothing at download time and is unrecoverable afterwards. Make
`_archive.txt` / `_source-titles.json` standard for every show.
Also: a record NAMING a source is not evidence the file is still there, or was
ever complete. I promised two recoveries on the strength of records; one item
404'd and the other was truncated at origin.

### Tooling preserved (`media-tools/`)
`decode-sweep.py` (parallel full decode), `sweep-status.sh` (progress any time),
`outliers.py`, `dedupe.py`, and the results at
`_records/decode-sweep-2026-09-04.json`.
⚠️ decode-sweep.py still records muxer noise as errors — classify results with
the decode-length test, never by error string.

## Bugs and lessons (recurring)
- **VPN FIRST.** A Rotterdam datacenter exit made every Lucas/Numberblocks URL
  read "This video is not available". I wrongly told Brian the videos had been
  PULLED. A control video resolved fine; switching to a US server fixed it
  instantly. Second time this has bitten.
- **`--match-filter "width>height"` is INVALID** — yt-dlp compares the field to
  the literal string "height" and errors `'>' not supported between int and
  str`, rejecting every video while looking like it works. Use
  `aspect_ratio>1`.
- **Killing a parent orphans ffmpeg children.** A stray ffmpeg survived
  `pkill -f bundle-clips` and `-f h264_videotoolbox` because it matched
  neither. Verify with `ps` before relaunching anything that writes files.
- **ffmpeg eats stdin** — a `find | while read` verification loop silently
  skipped every OTHER file, reporting exactly the even-numbered ones as
  corrupt. Use `ffmpeg -nostdin`.
- **Process presence lies; file growth does not.** Again. Also: real wall-clock
  time between tool calls can be hours, so "it only ran 35 seconds" reasoning
  is wrong.
- **`kill -STOP` did not pause the Patoaventuras pipeline** — it kept running
  and reached 72/73 while believed paused.
- Patoaventuras' pipeline **printed "ALL SEASONS COMPLETED AND VALIDATED"
  while 25 episodes were missing** and 24 outputs were `.tmp.mp4` fragments
  (`moov atom not found` = header never written = trash). Same shape as the
  EOD-sync bug: a script that reports success while failing.

## Open
- ✅ **USB drive DONE (2026-09-04).** 1 TB SanDisk, exFAT + GPT, label TANGBOX,
  659 GB copied. Mounted READ-ONLY at `/media/tangbox` by UUID `6A9A-7E45` via
  `/etc/fstab` (`ro,nofail,x-systemd.device-timeout=10,uid=1000,gid=1000,umask=022`)
  — read-only because the box only ever reads, which removes exFAT's
  no-journal corruption risk when the box is switched off at the wall; `nofail`
  so the Pi still boots without the drive. Verified: all 23 channels populated,
  **4,018 playable episodes, no empty channels.**
  - exFAT (not ext4) because macOS cannot WRITE ext4 without paid software,
    and the Mac has to put 659 GB on it.
  - `_commercials` deliberately NOT copied — it lives on the SD card at
    `~/tangbox-commercials` (146 clips). A mount HIDES what is beneath it, so a
    copy on the drive would silently do nothing. `_tools` skipped as pointless.
  - macOS wrote 4,019 `._*.mp4` AppleDouble sidecars (62 MB). HARMLESS —
    `channel.py:146` skips anything starting with a dot. Do not panic at a
    doubled file count.
  - Formatting and reading the volume FAILED from the Bash tool
    (`restricted by Sandbox ... -69464`); Disk Utility had to do it. Expect
    that for any removable-volume operation from this harness.
  - 4,018 not 4,019: `PBSKids/Jorge el Curioso/_unsplit/NA-XBSF8xSNt2g.mp4` was
    an unsplit raw source, correctly excluded by `exclude: ["_*", "*/_*"]` —
    a raw `find` over-counted it; the box was right. DELETED from the Mac
    2026-09-04 (213 MB). Still on the DRIVE, harmless and ignored; it will go
    at the next sync.
- 🔴 **Sheet rows owed** for all four shows — `workspace-mcp` failed to connect
  the entire session (CONNECT_TIMEOUT), so this is blocked, not skipped. Try
  restarting that server. **The rows are already built and waiting** — paste
  them or push them the moment it connects:
  `_tools/_records/sheet_lineup.tsv` (4 rows) and
  `_tools/_records/sheet_episodes.tsv` (210 rows, one per file). Tab-separated,
  so they paste straight into Sheets. `Named` is 0 for all four per the
  no-titles rule; `Verified` / `Actually contains` left EMPTY deliberately —
  those are hand-written and must never be invented.
- Octonautas 360p re-pull (above), once YouTube lets us back in.
- `resume-last-channel` feature: **DROPPED, do not build it.** The box ALREADY
  restores the CHANNEL across standby, which is how it is actually used:
  `_toggle_standby()` calls `tune_current()` on the way out and the process
  never dies. (An earlier version of this note also claimed it restored the
  same episode and timestamp. It did not — `_remember_position()` was broken,
  see the resume bug below. And Brian does not want that anyway: "I just want
  standby to resume the channel, not the show at the signed-off timemark".)
  The only real gap is a PULLED PLUG: `shutdown()` (app.py:339) fires from
  `run()`'s finally, so it covers a clean halt but never a killed process —
  which is precisely the case the feature was for. Covering that would mean
  writing on every channel change (still harmless: ~290 MB/year at an absurd
  200 changes a day, and the Pi's overlay FS is off so writes do land). Brian
  judged it not worth it, since the box lives on the TV and is halted properly.
  Revisit ONLY if it starts losing power unexpectedly.
- Patoaventuras is DONE at 48 — Brian's call, the other 25 are not coming.
- 🔴 **Doug (Nick Clásico, 72 eps) is in ENGLISH** — spotted 2026-09-04, wants
  replacing with a Spanish version. It has a `_source-titles.json`, so its
  provenance exists.
- 2 truncated episodes remain, unfixable without new sources: Jimmy Neutron
  S01E16 (5.9 min missing) and Gargoyles S01E40 (3.1 min, truncated AT ORIGIN).
  Both only lose an ending. Jimmy Neutron S01E04 was DELETED on Brian's call -
  43% missing made it not an episode; Nick Moderno kept its other 234.

## How to resume
Start a fresh session and say:
> "read SESSION-WRAP.md and continue."
