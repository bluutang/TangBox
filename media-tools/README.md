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

## Notable tools

| Tool | What it does |
|---|---|
| `bundle-clips.py` | Joins short clips into ~20-minute episode blocks. Verifies each block AND the total minutes in vs out - see the note in it about an orphaned ffmpeg silently overwriting finished blocks. |
| `dedupe.py` | Finds duplicate episodes by AUDIO fingerprint. Titles and durations both lie; the waveform does not. |
| `outliers.py` | Finds episodes that do not match their siblings in resolution or bitrate. Written after one 1080p file among 290 SD ones blocked the Pi's main loop and looked like a broken remote. |
| `status.py` | Reads each show's `_archive.txt` and writes `_status.html`. |
| `detect-breaks.py` | Finds ad-break points inside long files. |
| `dhtpre.py` | VidHide / dhtpre.com unpacker. Its media origin has been returning 5xx for days - see SESSION-WRAP.md. |
| `_records/` | Preserved provenance: episode TSVs, download logs, and the Google Sheet rows owed. |

## Warning

Several tools hardcode `/Users/briantang/Downloads/Converted`. They are written
for this one machine and this one library, not for general use.
