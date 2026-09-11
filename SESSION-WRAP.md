# Session Wrap — 2026-09-11 (evening)
> Written by: Claude Code (Sonnet 5) · Scope: tang-box

## ▶ READ THIS FIRST

The box itself is untouched (still on standby, 2026-09-07 state: 23 channels,
4,031 episodes). Everything below happened on the Mac and in the repo. This
session picked up right after Antigravity's own wrap (`25965df`) and made
several more changes on top of it — **the channel folder layout on the Mac
has moved since Antigravity's wrap was written**, so read the "What changed"
section below before trusting anything Antigravity's wrap said about paths.

## What this session did

**1. Fixed the Numberblocks undercount.** It had 192 episodes on disk but the
Lineup sheet and a `config.pi.yaml` comment both still said ~47-48 (stuck at
the 2026-09-07 reconciliation figure). Corrected in both places
(`config.pi.yaml` line ~257ish, Lineup row 96).

**2. Built `weighted_replay`** (`nostalgiabox/playlist.py`,
`nostalgiabox/channel.py`, `nostalgiabox/config.py`) — a show with few
episodes now repeats sooner instead of finishing its whole run and sitting
quiet while a 150-episode show works through its first pass. Gentle tiers,
Brian's choice: under 20 episodes repeats 3x, 20-59 repeats 2x, 60+
unchanged. **Turned on globally** in `config.pi.yaml`.

🔴 Worth knowing if you touch scheduling code next: the box's live `tune_in`
mode is `broadcast`, which builds its own finite running order straight from
`Channel.episodes` and does **not** go through `ShuffleBag`/`ShowOrder` at
all. My first implementation attempt only touched those two classes and
would have been completely inert on the real box. The fix that actually
works: expand `self.episodes` itself (repeat a small show's list by its
weight) once, in `Channel.__init__`, before *any* mode — random, resume, or
broadcast — ever sees it. All new tests pass; full suite is unaffected
(same 8 pre-existing, unrelated failures as before this session, in
`test_crt_cycle.py` and `test_guide.py` — not something this session caused
or investigated).

**3. Reorganized channels** (Brian's calls, discussed and confirmed before
touching anything):
- Bear in the Big Blue House: Disney Jr → PBS Pequeños (mascot-suit shows
  together)
- Apple Snoopy + Apple Cuentos **merged into one "Apple Kids" channel** —
  that name was already the sub-channel several not-yet-downloaded Apple
  shows carried on the Lineup sheet, so this just caught the config up
- Blocks Universe moved to right after the PBS block
- Prime Kids moved to right after the Cartoon Network block

25 channels now (was 26 — the Apple merge is a net reduction of one). Numbers
2-26.

**On the Mac, folders actually moved**:
- `DisneyJr/Bear in the Big Blue House` → `PBSPequenos/Bear in the Big Blue House`
- `AppleSnoopy/*` + `AppleCuentos/*` (6 shows) → new `AppleKids/`, then the
  two old folders were deleted (only `.DS_Store` was left in them)

**Config and tooling updated to match**: `config.pi.yaml` fully renumbered
with fresh comments (two stale "THIN" comments on Nick Moderno and Disney Jr
also refreshed — neither channel is thin any more).
`media-tools/organize-channels.py`'s `CHANNELS` map updated for the same
moves, plus two not-yet-downloaded shows Brian named as next adds: Pete the
Cat (→ Prime Kids) and Shape Island (→ Apple Kids).

**Lineup sheet updated to match**: Bear's sub-channel, the two Snoopy shows'
sub-channel ("Apple Snoopy" → "Apple Kids"), Trash Truck's sub-channel fixed
(was mislabeled "Netflix Kids", now "Netflix Pequeños"), and a new `Wanted`
row added for Pete the Cat (2 seasons, 43 episodes + 4 specials per IMDb,
2017-2022, ended).

**4. Swept and removed a stray Sea of Love copy.** `~/Downloads/Cartoons/Sea_of_Love/`
(2 GB, 15 episodes) was the pre-downscale 4K original left behind by
Antigravity's recording pipeline after it filed the final 540p version into
`Converted/NetflixPequenos/Sea of Love/`. Verified identical duration on one
episode before deleting. Nothing else found anywhere else on the Mac (`~/Desktop`,
`~/Documents`, `~/Movies`, rest of `~/Downloads` all checked).
`~/Downloads/Cartoons/` is worth knowing about generally — it looks like
Antigravity's scratch folder for raw captures before downscaling, and may
leave similar leftovers after future recordings. Worth a periodic check,
not a one-time fix.

## 🔴 Antigravity's wrap is now stale on folder paths — read this before copying to the drive

Antigravity's wrap (`25965df`) listed folders to copy to the USB drive
(`PrimeKids/Tumble Leaf/`, `AppleSnoopy/`, `AppleCuentos/`,
`NetflixPequenos/`, `PBSKids/Jorge el Curioso`, `PBSPequenos/Teletubbies`,
`BlocksUniverse/Colourblocks`). **`AppleSnoopy/` and `AppleCuentos/` no
longer exist** — that content is now under `AppleKids/`. `PBSPequenos/` also
now includes `Bear in the Big Blue House`, which wasn't part of what
Antigravity downscaled but does need to reach the drive since it moved
channels.

The real "what's new for the drive" list, current as of this wrap:
- **Brand new shows, not on the drive at all**: Tumble Leaf (52 eps, Prime
  Kids), Colourblocks (174 eps total, Blocks Universe), Sea of Love (15 eps,
  Netflix Pequeños)
- **Moved to a new channel path** (drive may have the content under the OLD
  path): Numberblocks (NetflixJr → BlocksUniverse), Puffin Rock (NetflixJr →
  NetflixPequenos), Bear in the Big Blue House (DisneyJr → PBSPequenos), all
  6 Apple shows (AppleSnoopy/AppleCuentos → AppleKids)
- **Re-encoded at a new resolution** (same episode count, different bytes):
  Jorge el Curioso (480p), Camp Snoopy (480p), Snoopy en el espacio (480p),
  Frog and Toad (540p), Duck & Goose (540p), Teletubbies (17 of 26 → 720p)

This was never actually verified against the drive itself — it's built from
commit history and file records, same as it was last session. The drive
still is not plugged into this Mac.

## How to resume

Start a fresh session and say:
> "read tang-box/SESSION-WRAP.md and continue."

Next concrete action is almost certainly: connect the USB drive, run
`check-exfat.py` (or a similar direct comparison) against it for a real
verified list, then copy over what's actually missing/stale using the list
above as a starting point rather than gospel. Everything else from this
session is finished, tested where relevant, committed, and pushed.
