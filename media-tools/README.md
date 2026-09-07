# media-tools

Mac-side tooling for building the TangBox media library: downloading, cutting,
bundling, deduping, renaming and verifying episodes. Distinct from `scripts/`,
which is box-side and runs on the Pi.

## This directory IS `~/Downloads/Converted/_tools`

It lives here and is symlinked from there:

```
/Users/briantang/Downloads/Converted/_tools -> tang-box/media-tools
```

That is deliberate. A copy in the repo would drift from the working copy while
still looking version-controlled, which is the exact failure this project keeps
running into. There is one directory; git tracks it; the old absolute paths
(several tools hardcode `/Users/briantang/Downloads/Converted/...`) still
resolve through the symlink.

If the symlink is ever lost:

```sh
ln -s /Users/briantang/BluuClaude/tang-box/media-tools \
      /Users/briantang/Downloads/Converted/_tools
```

## Every tool

Generated from each script's own docstring. Before writing a new one, check here —
there are more than thirty, and several problems have been solved twice already.

### Fetching

| Tool | What it does |
|---|---|
| `get-archive.py` | Download video files from archive.org items into a show's staging folder. |
| `get-commercials.py` | Fetch the approved 2000s/late-90s commercials into `_commercials/`. |
| `get-xiaolin.py` | Fetch the 52 Xiaolin Showdown files from Brian's shared Drive folder. |
| `okru.py` | Resolve an ok.ru video id to its best direct rendition and download it. |
| `dhtpre.py` | Resolve a VidHide (dhtpre.com) embed to its stream endpoints. |
| `tokyvideo-plan.py` | Turn `video-source-links.csv` into a download plan. |
| `tokyvideo-get.py` | Download that plan, one file at a time, into the show's real folder. |
| `blocked.py` | Which videos are geo-blocked, and which VPN country would unblock them all. |

### Cutting and bundling

| Tool | What it does |
|---|---|
| `youtube_compilation.py` | Turn YouTube compilation uploads into TangBox-length episodes. Cuts contiguous runs of chapters rather than each chapter separately — the joins inside a run are the uploader's own and cannot be mis-cut. |
| `detect-breaks.py` | Find episode boundaries inside a compilation video, and optionally cut it. |
| `find-title-cards.py` | Find episode starts by looking for the near-white title card. |
| `find-break-spot.py` | Find a good place to drop a commercial break inside a long episode. |
| `cut-at.py` | Cut a file at explicit timestamps, frame-accurately. |
| `bundle-clips.py` | Join short clips into ~20-minute blocks. Verifies each block **and** total minutes in vs out — see its note about an orphaned ffmpeg silently overwriting finished blocks. |
| `join-shorts.py` | Join Daniel Tigre's 11-minute segments into full-length episodes. |

### Verifying

| Tool | What it does |
|---|---|
| `decode-sweep.py` | Full-decode every playable episode and report anything not clean. |
| `outliers.py` | Find episodes that do not match their siblings in resolution or bitrate. Written after one 1080p file among 290 SD ones blocked the Pi's main loop and looked like a broken remote. |
| `dedupe.py` | Find true duplicate episodes by **audio content**, not filename or duration. Titles and durations both lie; the waveform does not. |
| `find-dupes.py` | Find episodes that already exist inside a show's long compilations. |
| `check-exfat.py` | Check every name under `Converted/` against exFAT's rules before copying to USB. |

> Language is **not** covered by any script here. Use `whisper-cli` directly —
> see `../docs/lessons.md`. A show was lost to non-Spanish audio that carried
> correct Spanish titles and an `eng` tag, so neither names nor tags can be
> trusted.

### Naming and filing

| Tool | What it does |
|---|---|
| `name-from-titles.py` | Name staged downloads from their YouTube titles. |
| `backfill-titles.py` | Add the video title to files downloaded before the template carried one. |
| `file-shows.py` | Move finished episodes out of `_staging` into Season folders. |
| `file-cut-pieces.py` | File the finished cut/bundled pieces for Daniel Tigre, Dora and Pistas. |
| `organize-channels.py` | Sort show folders into the channel folders the box expects. |

### Status and Finder helpers

| Tool | What it does |
|---|---|
| `status.py` | Read each show's `_archive.txt` and write a self-refreshing `_status.html`. |
| `tag-incomplete.py` | Colour-tag show folders in Finder by how complete they are. |
| `tag-artwork.py` | Colour-tag folders whose show has no tile picture yet. |
| `keywatch.py` | Timestamp remote keypresses as the kernel sees them, for diagnosing input lag on the Pi. |

### Show-specific one-offs

Kept because they document what was done, not because they generalise:
`digimon-file.py`, `jorge-swap.py`, `rolie-cut.py`, `sailor-seasons.py`.

### Other

`_records/` — preserved provenance: episode TSVs, download logs, and the Google
Sheet rows owed.

## Warning

Several tools hardcode `/Users/briantang/Downloads/Converted`. They are written
for this one machine and this one library, not for general use.
