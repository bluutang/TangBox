# Session Wrap — 2026-09-11 (night)
> Written by: Claude Code (Sonnet 5) · Scope: tang-box

## ▶ READ THIS FIRST

**The USB drive is fully synced and verified — this is the good news to lead
with.** Everything the previous wrap (`4a307de`) flagged as pending is now
done. The drive was plugged into this Mac, compared directly against
`Converted/` (not reconstructed from records this time), and brought to an
exact match: **4,490 episodes across 74 shows, identical on both sides, every
show in its correct channel folder.** The drive is back in Brian's hands to
put back in the box.

## What this session did

**1. Verified drive-vs-Mac with a real script, not guesswork.** Wrote
`compare_drive.py` (scratchpad, not committed - one-off tool) to walk both
trees by show name and diff channel path + episode count. First pass looked
alarming - every show showed the drive at exactly 2x the Mac's count - which
turned out to be a script bug, not a real problem: the exFAT drive carries a
hidden `._<name>.mp4` AppleDouble shadow file next to every real one, and
Python's `rglob("*.mp4")` matches those too (unlike a shell glob, which skips
dotfiles by default). Excluding `._`-prefixed names fixed it, and the real
result was reassuring: **every show untouched by this session already
matched exactly** - only this session's own changes had actually drifted.

**2. Synced the drive**, in two parts:
- **Moved 9 shows already on the drive** into their new channel folders
  (same content, same episode counts both sides - Bear in the Big Blue
  House, the 6 Apple shows, Puffin Rock, Numberblocks). Fast, same-volume
  renames, no data copied.
- **Copied ~51 GB of genuinely new/missing content** via `rsync -a`:
  Colourblocks (174 eps, 22 GB), Tumble Leaf (52 eps, 10 GB), Numberblocks's
  missing 145 episodes (12.5 GB, `--ignore-existing` so the 47 already-there
  files were left alone), Sonic X (73 eps, 5.6 GB), Sea of Love (15 eps,
  1 GB).
- Also renamed one drive folder to match the Mac exactly: "¿Qué hay de nuevo,
  Scooby-Doo**?**" → "¿Qué hay de nuevo, Scooby-Doo" (dropped the trailing
  `?` - same 42 episodes both sides, this was pure naming drift, not a real
  gap).
- Ran `check-exfat.py` against the source before any of this - came back
  clean, 4,877 files / 274 folders, no unsafe names.

🔴 Worth knowing if this ever needs redoing: macOS's `rsync` here is old BSD
rsync (2.6.9), not a modern one - `--info=progress2` doesn't exist and
aborts the whole run immediately (caught before anything was written,
re-ran with `--stats` instead). If scripting a drive sync again, check the
installed rsync's flags first rather than assuming GNU-rsync-style options.

## A dead end this session couldn't resolve

Brian asked to confirm a "Cosby commercial" was removed from the Pi's SD
card. **This session has no way to check that and never found any record of
it:**
- Commercials live at `~/tangbox-commercials` on the Pi's SD card,
  deliberately kept off the USB drive AND off this Mac (see the big comment
  block in `config.pi.yaml` around `commercials:` - "ON THE SD CARD,
  DELIBERATELY"). No local mirror exists on this Mac to check.
- No SSH access to the Pi from this session.
- Searched everything reachable from here - the Mac's own `_commercials/`
  folder, this repo's full git history, every doc in the workspace - zero
  hits for "cosby" anywhere.

Whoever picks this up next: either Brian checks `~/tangbox-commercials` on
the Pi directly over SSH, or SSH access needs setting up for an agent to
check it. Worth asking Brian what he actually remembers about this clip
(when it was added, why it was flagged) since there's no paper trail at all
right now.

## How to resume

Start a fresh session and say:
> "read tang-box/SESSION-WRAP.md and continue."

The drive/library side of things is fully caught up and verified - nothing
pending there. The only open thread is the Cosby-commercial question above,
and it needs either Brian's own SSH check or a decision about giving an
agent SSH access to the Pi.
