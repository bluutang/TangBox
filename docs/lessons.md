# TangBox — hard-won lessons

Things that cost time to learn once and should never cost it again. Written for
**any** agent working on TangBox (Claude Code, Codex, Antigravity) — none of this
is tool-specific.

If something here contradicts the code, the code wins and this file is wrong:
say so rather than working around it.

---

## Media: format and codec

**Every video must be H.264.** The Raspberry Pi 5 has no AV1 hardware decoder, so
AV1 falls back to software and stutters. `yt-dlp` left alone picks AV1 for "best
quality". Pin the format explicitly, every time:

```sh
-f "bestvideo[vcodec^=avc1][height<=720]+bestaudio[ext=m4a]/best[height<=720]"
```

Verify after, never assume:

```sh
ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 FILE
```

720p is the sensible ceiling — the CRT shader softens the picture anyway. Note
that some sources offer 480p in *both* avc1 and HEVC/AV1; picking by resolution
alone is not enough.

## Media: verifying a download actually worked

**A file's size and its container duration can both lie.** Found 2026-09-06 on a
Puffin Rock episode: the container claimed 20:03 and `ffprobe` reported a healthy
bitrate, but decoding produced only 160 seconds of video. The metadata was
inherited from the manifest rather than measured.

The reliable screen is **actual size against bitrate x duration**. Complete files
land near 1.0; the truncated one stood out instantly:

```sh
# ratio well below ~0.85 means truncated
python3 - <<'PY'
# size / ((video_bitrate + audio_bitrate) * duration / 8)
PY
```

For certainty, count frames — that decodes the whole file:

```sh
ffprobe -v error -count_frames -select_streams v:0 \
  -show_entries stream=nb_read_frames -of csv=p=0 FILE
```

## Media: verifying the LANGUAGE

**Language tags are worthless and correct titles prove nothing.** Coraje El Perro
Cobarde was swept in full (48 episodes) because its audio was not Spanish — while
every file was tagged `eng` and the source had supplied correct *Spanish episode
titles*. The filenames looked perfect.

`whisper-cpp` is installed. Check the spoken language directly:

```sh
ffmpeg -v error -ss "$SS" -t 30 -i FILE -vn -ac 1 -ar 16000 -c:a pcm_s16le -y /tmp/x.wav
whisper-cli -m ~/Downloads/_whisper/ggml-base.bin -dl -f /tmp/x.wav
```

`-dl` exits after detecting — no transcription. Two rules learned applying it to
162 episodes on 2026-09-06:

* **Validate against a known-good control first.** Patoaventuras reads `es` at
  p=0.98, which is what makes a reading on an unknown file trustworthy.
* **Judge by confidence, and re-sample before acting.** Low-confidence readings
  (Spanish/Italian confusion sat at p=0.35-0.63 against a Spanish mean of 0.941)
  were false alarms — three samples per episode cleared them. Genuinely wrong
  episodes held their reading at p>0.94 across every sample and clustered
  together. Four English episodes in Los Padrinos Mágicos were found this way.

Run this on new material **before** filing it, not after.

## Media: files carrying MORE THAN ONE audio track

**A dual-language file can be Spanish and still play English.** Sonic X arrived
from lacartoons.com on 2026-09-07 with two AAC tracks per file, `spa` first and
`eng` second — and **both were flagged `default`**. `player.py` sets no `--aid`
and no `--alang`, so nothing in this project actually chooses; the outcome rests
on mpv's tie-breaking between two tracks that both claim to be the default.

Do not leave that to chance. **Strip the unwanted track when filing**, which is
lossless and needs no re-encode:

```sh
ffmpeg -i IN.mp4 -map 0:v:0 -map 0:a:0 -c copy -movflags +faststart \
  -metadata:s:v:0 language=und -metadata:s:a:0 language=spa OUT.mp4
```

Check the layout before assuming a file is single-track — every other show in the
library is, which is exactly why this is easy to miss:

```sh
ffprobe -v error -select_streams a \
  -show_entries stream=index:stream_disposition=default:stream_tags=language \
  -of compact FILE
```

Verify which track is which by **listening**, not by reading the tag: the same
whisper check above, with `-map 0:a:0` / `-map 0:a:1` on the extract. On Sonic X
the tags happened to be honest, but Coraje above is the reason that is confirmed
rather than assumed.

### The container-duration trap that follows from it

**Dropping a track can legitimately shorten the container duration, and that is
not damage.** A file's `format=duration` is its longest stream. On Sonic X the
English track ran up to 8 seconds past the video, so it — not the picture — was
setting that number. Removing it made the container 6-8 s "shorter" on 23 files
and a verify step that compared `format=duration` failed every one of them, all
of them perfectly good.

**Compare per-stream durations instead**, source against output:

```sh
ffprobe -v error -select_streams v:0 -show_entries stream=duration -of csv=p=0 FILE
ffprobe -v error -select_streams a:0 -show_entries stream=duration -of csv=p=0 FILE
```

Both matched to the microsecond on all 73 files. Two habits made the bad check
harmless rather than costly, and both are worth keeping: a failed verification
**deleted nothing**, and each source was removed only after its replacement
survived a full software decode (`ffmpeg -v error -i OUT -f null -`).

## Media: cutting and joining

**Chapter marks are typed by hand and often sit seconds early**, which leaves the
tail of the previous segment at the head of the next. Find the real boundary
rather than trusting the mark. Two detectors are needed because they are
complementary: where a title card exists, scene detection sees nothing (a white
card onto a white background is barely a change); where no card exists, the
reverse. Together they resolved 21 of 21 marks on a test upload.

**Prefer cutting a contiguous run of chapters over cutting each one and gluing
them back.** The joins inside a run are the uploader's own and were never cut, so
they cannot land early or late. Measured on 62 Pocoyo episodes: all 5 decode
faults were in the 23 stitched from fragments; the 39 cut as whole runs were
clean first time.

**Join through MPEG-TS, not by concatenating .mp4 directly.** Direct concat leaves
two frames sharing a timestamp at every boundary; via TS there are none.

**An MP4 stream copy carries pre-roll packets that survive an `-ss` cut.** A
"lossless" retrim can therefore appear to work — the file changes, the duration
changes — while the decoder still emits the frames you meant to remove. If a trim
must be exact, re-encode.

## Media: naming

Convention is `Show - S01E03.mp4` inside `Show/Season NN/`.

**Never take episode titles from a database lookup.** They landed on the wrong
episodes across many shows (the Rugrats problem), and a wrong title is worse than
no title. The box plays a random episode and never displays a title, so a title
buys nothing.

**A title from the source's own metadata is fine** — a YouTube video title
describes the file it came from and cannot be mismatched. Strip channel prefixes
and boilerplate, remove emoji, replace `/` and `:`.

## The Pi

**The running service reads `/home/brian/TangBox/config.yaml`.** That file is
gitignored, machine-local and hand-maintained. `config.pi.yaml` in the repo is a
committed *template the box never opens*. Editing it and pulling on the Pi changes
nothing about behaviour — every config change needs a second manual step over SSH.

**Never copy `config.pi.yaml` over `config.yaml`.** Its paths point at
`/media/tangbox`, and the box would lose all its media.

**Media lives on a USB drive, not the SD card.** The catalog is far larger than
the card's free space. Channels reporting 0 episodes on the Pi is the expected
state, not a fault — do not offer to copy episodes onto the card.

## Machines

`scutil --get ComputerName` → `Tangcito` (Mac mini) or `Blue-Tangium` (MacBook).
They are equal peers. Rosetta 2 is installed on Tangcito (for the Intel-only Flirc
app) and **not** on Blue-Tangium — check that first if the Flirc app won't launch.

## Diagnosing slow downloads

**Ask about the VPN before proposing workarounds.** A download once crawled at
16 KiB/s and was diagnosed as server-side throttling with a 12-hour projection;
Brian exited a VPN and the same job finished in under an hour.

Two related traps: momentary speed readings are bursty and near-useless — measure
*sustained* throughput from file mtimes; and a short speed test measures nothing,
because `yt-dlp` spends the first 15+ seconds on metadata reporting 0 B/s.

Separately, YouTube rate-limits after heavy use (HTTP 429, then a sign-in
challenge). It clears after some hours. Roughly 200 metadata requests was enough
to trigger it on 2026-09-06.

## Shell

**Agent shells here are `zsh`, not bash.** `[[ "$s" =~ re ]]` succeeds but leaves
`$BASH_REMATCH` **empty** — zsh puts captures in `$match[1]`. Use
`sed -n 's/.../\1/p'`, which works in both. A no-match glob aborts the command in
zsh, unlike bash.

**Always guard a bulk rename or move**: assert `unique targets == planned moves`
and abort otherwise. That guard caught a 97-file rename where every target had
collapsed to the same name, before anything moved.

## The spreadsheet

The wanted-shows list is a Google Sheet, not a file in this repo, and it is the
source of truth for **what the library should contain** — the shopping list.
Updating it is part of any conversion job, not a separate request. Writing to it
needs the `workspace-mcp` server — the Drive connector cannot write cells.

🔴 **The Mac is the source of truth for what the library ACTUALLY contains.**
`~/Downloads/Converted` is where Brian curates the channel folders by hand: he
adds, prunes and swaps versions there directly. The sheet tracks that work and
routinely lags behind it, sometimes by dozens of shows. When disk and sheet
disagree about what exists, **the Mac wins and the sheet gets corrected** — never
the other way round.

The sheet's *notes* lag hardest, because they are written once and rarely
revisited. A note can confidently describe episodes that Brian deleted weeks
later. Read a stale note as history, not as an instruction to restore anything.

**What this does NOT license.** The Mac wins on *existence*, not on intent. A
show being absent there is not on its own a reason to delete the drive's copy —
ask Brian what the absence means before removing anything, and say plainly which
way you are proposing to sync. Deletions on an external drive skip the Trash and
are unrecoverable.

**Measured 2026-09-07**, reconciling the drive against the Mac after a long gap:
24 episode counts on the sheet were wrong (Dragon Ball Z said 1, disk had 291;
Bluey 1 vs 150), 8 shows sat as `Wanted` with files already on disk, 5 rows
claimed a "pilot only" episode that existed nowhere, and **26 shows on the box
had no row at all** — 1,227 episodes. None of that was visible from the sheet
alone. Reconcile from disk, per show, before trusting any figure on it.
