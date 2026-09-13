# Session Wrap — 2026-09-12 (late night)
> Written by: Claude Code (Sonnet 5) · Scope: tang-box

## What we worked on

The box was crash-looping (USB drive dropped and remounted under a new device
name, so every file read failed). Fixed that, then a routine "is the box
aligned with the Mac's catalog" check turned up something much bigger: the
Pi was 27 commits behind and its live `config.yaml` had never been updated
for last week's channel reorg — two channels pointed at folders that no
longer existed, and four channels' worth of already-organized content (581
episodes) had no channel entry at all, so nothing on the box could reach it.

## Status right now

**Done and verified live:**
- USB mount fixed, service stable (0 restarts since).
- Deployed the pending code + a hand-spliced `config.yaml` channels list.
  Box now runs all **25 channels** (was 23) — Apple Kids, Blocks Universe,
  Prime Kids, and Netflix Pequeños are reachable for the first time.
- `weighted_replay` is on, live, for the first time on real hardware.
- Added `scripts/warm-duration-cache.py` and ran it — every channel's
  episode durations are pre-cached, so no channel will freeze/cascade
  buttons on its first tune-in.
- Brian confirmed buttons feel responsive after the final restart.
- Committed `00823f2`: the script, plus a `docs/lessons.md` section
  spelling out the full deploy sequence (stop service → git pull → splice
  `config.pi.yaml`'s channels block into the live `config.yaml`, never the
  whole file → warm cache → start service).

**One real mistake this session, now documented:** ran the cache-warming
script (81s of `ffprobe` calls) against the *live, running* box instead of
stopping it first. Made every button laggy for that whole window — nothing
broke, but it's exactly the kind of thing `docs/lessons.md` now warns future
agents about.

## Next 1-3 steps

1. **Shape Island / "La isla de las formas"** — Brian is still finishing
   these 10 episodes. When he says they're ready:
   - Move `Converted/AppleCuentos/La isla de las formas` → `Converted/AppleKids/`
     on the Mac (the folder is still sitting under the old pre-merge name).
   - Add a `tile.jpg` to that show folder — it's the only show in the whole
     library missing one.
   - Copy the ~2.2GB to the Pi's `/media/tangbox/AppleKids/`. The drive is
     mounted **read-only** on the Pi on purpose; Brian chose "remount
     read-write over SSH, copy, remount read-only" as the method when asked.
   - `media-tools/organize-channels.py` and `media-tools/shows.json` already
     have **uncommitted** local edits from before this session adding this
     show to the `AppleKids` channel mapping — don't redo that work, just
     verify it still matches once the folder is renamed, then commit.
   - Run `scripts/warm-duration-cache.py` on the Pi afterward (with the
     service **stopped** this time) so this new content doesn't cause a
     freeze on its first tune-in.

2. Carried over from the previous wrap, not this session's work: the
   MacBook (`Blue-Tangium`) rename / three-agent parity task in
   `docs/macbook-catch-up.md` is still open. Whoever is next on that machine
   should run it.

## Files touched this session
- `docs/lessons.md` — new section: the full deploy sequence, and the
  stop-the-service-first lesson.
- `scripts/warm-duration-cache.py` — new. Pre-warms the episode-duration
  cache for every configured channel; safe to re-run any time.
- `/home/brian/TangBox/config.yaml` (on the Pi, not in git) — channels
  block replaced to match `config.pi.yaml`'s reorg; `weighted_replay: true`
  added. Backed up automatically to `config.yaml.bak-20260912-231846` on
  the Pi before editing.

## Decisions made
- Config deploys to the Pi from now on always splice just the `channels:`
  block (and any new global settings) out of `config.pi.yaml`, never copy
  the whole file — everything else in the live config is machine-local.
- Cache-warming always runs with `tangbox.service` stopped.

## Open questions / blockers
- Shape Island copy is blocked on Brian finishing the episodes (see above).

## How to resume
Start a fresh session (don't click "Keep full session"). Then say:
> "read tang-box/SESSION-WRAP.md and continue."
