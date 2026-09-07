# TangBox — instructions for any agent

A Raspberry Pi 5 that plays folders of old kids' shows as real TV channels. It
boots straight to television in about 21 seconds. Repo:
`github.com/bluutang/TangBox`.

This file is deliberately self-contained: this repo is cloned on its own onto the
Pi, where nothing above it exists.

**When working inside Brian's `BluuClaude` workspace**, read these too — this repo
sits inside it as a nested repo:

| File | What it holds |
|---|---|
| `../CLAUDE.md` | Workspace-wide rules and how to talk to Brian |
| `../AGENT-PROTOCOL.md` | How Claude Code, Codex and Antigravity share this workspace |
| `docs/lessons.md` | **The full TangBox lessons. Read before any media work.** |
| `media-tools/README.md` | Index of ~29 scripts — check before writing a new one |

`CLAUDE.md` and `GEMINI.md` here are symlinks to this file, so all three agents
read the same thing.

---

## The rules that must not be missed

**Filenames are `Show - S01E03.mp4` inside `Show/Season NN/`.**

🔴 **Never take episode titles from a database lookup.** They landed on the wrong
episodes across many shows, and a wrong title is worse than none — the box plays a
random episode and never displays a title, so a title buys nothing. A title taken
from the *source's own metadata* (a YouTube video title) is fine, because it
describes the file it came from and cannot be mismatched.

🔴 **Every video must be H.264.** The Pi 5 has no AV1 hardware decoder. `yt-dlp`
picks AV1 by default — pin the format explicitly and verify with `ffprobe`.

🔴 **Verify the spoken language before filing.** Tags and filenames both lie. A
48-episode show was deleted because its audio was not Spanish while every file
carried a correct Spanish title and an `eng` tag. `whisper-cli` is installed; see
`docs/lessons.md`.

🔴 **The running box reads `/home/brian/TangBox/config.yaml`**, which is gitignored
and machine-local. `config.pi.yaml` in this repo is a template the box never
opens. Editing it and pulling on the Pi changes nothing. Never copy one over the
other — their paths differ and the box would lose its media.

**Media lives on a USB drive, not the SD card.** Channels reporting 0 episodes on
the Pi is the expected state, not a fault.

## The library

Episodes are staged on Brian's Mac in `~/Downloads/Converted/`, organised into
channel folders, then copied to the USB drive.

**The wanted-shows list is a Google Sheet, not a file in this repo**, and it is the
source of truth for what the library should contain. Updating it is part of a
conversion job, not a separate request.

## Before you build something

Check `media-tools/README.md`. There are already tools for downloading, cutting at
chapter marks, bundling short clips, deduping by audio fingerprint, finding
truncated or mismatched files, renaming and filing. Several problems here have
been solved twice.
