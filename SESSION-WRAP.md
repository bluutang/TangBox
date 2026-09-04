# Session Wrap — 2026-09-03/04

## What happened
Three shows filed (Lucas, Numberblocks, Octonautas) into a NEW channel,
Patoaventuras closed out at 48, five shows blocked and parked, and two real
bugs found — one in `bundle-clips.py` that would have filed broken episodes
silently.

## Library: 23 channels, 69 shows, 4,019 episodes, 1,509 hours. 9.1 GB free.

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
El show de Snoopy. All route through `xupalace.org` -> `embed69.org`; nothing
in the toolkit reaches it. Snoopy differs: its gateway returns **HTTP 444**
(deliberate blocking) even with browser headers, where the others give a plain
unsupported-URL error. **One embed69 resolver would unblock several at once** —
that is the highest-leverage piece of work available, and Snoopy is a 36-episode
source for a show that was pruned as a single-episode stub.

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
- 🔴 **USB drive.** 23 channels on the dial, no media on the Pi. Unchanged.
- 🔴 **Sheet rows owed** for all four shows — `workspace-mcp` failed to connect
  the entire session (CONNECT_TIMEOUT), so this is blocked, not skipped.
- Octonautas 360p re-pull (above), once YouTube lets us back in.
- `resume-last-channel` feature: DESIGNED, NOT BUILT. Brian chose "fall back
  after a few hours". Hook is `shutdown()` in `app.py:339` (fires once, in
  `run()`'s finally) writing channel+timestamp; read it in
  `_select_start_channel()` (app.py:1288) with a ~3 h threshold. SD-card wear
  is a non-issue at one write per power-off. No state-file convention exists
  in the repo yet.
- Patoaventuras is DONE at 48 — Brian's call, the other 25 are not coming.

## How to resume
Start a fresh session and say:
> "read SESSION-WRAP.md and continue."
