# Session Wrap — 2026-09-03/04

## What happened
Three shows filed (Lucas, Numberblocks, Octonautas) into a NEW channel,
Patoaventuras closed out at 48, five shows blocked and parked, the USB drive
finally installed so the box actually plays, and three real bugs found — one in
`bundle-clips.py`, one in `app.py`'s resume, and one that was not a bug at all
but 22 badly-matched video files making the remote lag.

## Library: 23 channels, 69 shows, 4,018 episodes, 1,509 hours.
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

## 🔴 `bundle-clips.py` HAS A BUG — do not trust its "ok"
Its mixed-encode path feeds clips of DIFFERENT RESOLUTIONS to ffmpeg's concat
filter, which cannot handle that. Two Octonautas blocks came out TIME-STRETCHED
— one to **144 minutes from an intended 20** — and the tool reported both as
`ok`, because it only verifies a block is not too SHORT. There is no guard
against a block coming out too LONG.

Caught only by comparing minutes-in to minutes-out (835.9 vs 977.6). **Always
run that check.** Fixed here by normalising every clip to one resolution first
(`scale=854:480:force_original_aspect_ratio=decrease,pad=...,setsar=1`) plus
`-fps_mode cfr` (`-vsync` is GONE from this ffmpeg — it fails loudly, but a
script can swallow it). The tool itself is still unfixed.

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

## 🔴 "The remote is lagging" was 22 BADLY-MATCHED VIDEO FILES
Brian reported the remote registering presses slowly. It measured clean at every
level — 0.0% I/O wait, idle CPU, 54.9°C, no throttling, no CEC loop, `select()`
returning instantly, Flirc enumerated fine. Moving the Flirc to a USB 3 port
would have done nothing (an HID keyboard uses 12 Mbps by standard, not because
the port limits it).

**It was content.** The Pi 5 has NO hardware H.264 decoder — everything is
software-decoded. `Dragon Ball Z S01E01` was 1920x1080 @ 4.64 Mbps sitting among
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

## How to resume
Start a fresh session and say:
> "read SESSION-WRAP.md and continue."
