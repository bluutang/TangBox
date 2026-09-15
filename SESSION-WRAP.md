# Session Wrap — 2026-09-14

> Written by: Claude Code (Sonnet 5) · Scope: tang-box

## What we worked on

Started from "the controller seemed a little laggy" after Brian used the box.
Checked the Pi over SSH: service healthy, no crash, CPU idle, USB drive stable,
duration cache still warm from the 2026-09-12 fix — no active bug found, just
a plausible-not-confirmed lead (CEC handshake + a benign "no CUDA here" retry
on every episode/channel load). Logged in `docs/lessons.md` isn't needed for
this part; nothing was confirmed enough to be a lesson.

That turned into Brian wanting to unplug the box to take it to another house
to showcase. Walked through the safe way to do that (clean shutdown, not a
yank), and in verifying it were the real find of the session:

🔴 **The remote's POWER button does not shut the Pi down — hasn't since
2026-08-22 — and `docs/flirc-remote-mapping.md` said the opposite for three
weeks.** Brian pressed POWER, the picture collapsed like a shutdown, but the
box was still fully reachable over SSH minutes later. Traced it in git
history: `power_button: shutdown` (2026-08-20) was deliberately reversed to
`standby` two days later (`ba0418b`) so a halted Pi wouldn't strand the Flirc
receiver — but the comment explaining *why* never got reattached to the
setting, so the doc (and then me, reading it) kept stating the old behaviour
as current fact. Full writeup is now in `docs/lessons.md`, "The Pi" section.

## Status right now

**Done, committed, pushed (`e1e37fd`):**
- `docs/flirc-remote-mapping.md` — POWER button row and section corrected:
  it toggles standby, same as ✱/bedtime; real shutdown needs SSH or the
  onboard button.
- `config.pi.yaml` — the `power_button` comment rewritten to match what
  actually happened on 2026-08-22, instead of the pre-reversal rationale.
- `docs/lessons.md` — new entry under "The Pi": what was wrong, the exact
  commit trail, and the reusable lesson (read the code before repeating what
  a doc claims a button does, even confidently-written docs can be stale).

**Not done — blocked on the box being back online:**
- The live `/home/brian/TangBox/config.yaml` on the Pi has the *same* stale
  `power_button` comment `config.pi.yaml` had (value is already correct,
  `standby`, on both — this is a comment-only sync, no behaviour change).
  Couldn't reach it: `ssh tangbox` fails to resolve, because the Pi is
  properly powered off right now — Brian shut it down cleanly (confirmed via
  SSH going unreachable) to unplug it and take it to another house.

**Also cleanly powered off tonight, confirmed via SSH:** ran
`sudo systemctl poweroff` on Brian's behalf after establishing the remote
alone can't do a full shutdown. Verified off by hostname resolution and ping
both failing afterward — that is the check to use next time too, since a
timeout alone doesn't distinguish "off" from "network hiccup" as cleanly as
"can't even resolve the mDNS name."

## Next 1-2 steps

1. **Once the box is back on the network** (wherever it ends up — the other
   house, or back home), patch the same comment into the live
   `/home/brian/TangBox/config.yaml`. Do NOT copy the whole file (loses
   machine-local paths/media settings) — just replace the `power_button:`
   comment block, same text as what's now in `config.pi.yaml` lines ~577-588.
   Confirm `ssh tangbox` resolves again before attempting this.
2. Carried over, unchanged from the last wrap: **Shape Island** — 10 episodes
   Brian is still finishing. `media-tools/organize-channels.py` and
   `media-tools/shows.json` still have **uncommitted** local edits from
   before 2026-09-12 adding it to the `AppleKids` channel mapping — verify
   they still match once the folder is renamed
   (`Converted/AppleCuentos/La isla de las formas` → `Converted/AppleKids/`),
   then commit. Full steps in git history of this file if needed.

## Files touched this session
- `docs/flirc-remote-mapping.md`, `config.pi.yaml`, `docs/lessons.md` —
  committed in `e1e37fd`.
- `/home/brian/TangBox/config.yaml` (on the Pi, not in git) — **NOT yet
  touched**, see above.

## Decisions made
- None new. Confirmed the existing 2026-08-22 decision (POWER = standby, not
  shutdown) is still correct and intentional — just wasn't documented
  correctly.

## Open questions / blockers
- Live `config.yaml` comment sync is blocked on the Pi being reachable again.
- Shape Island copy still blocked on Brian finishing the episodes (unchanged
  from before).

## How to resume
Start a fresh session (don't click "Keep full session"). Then say:
> "read tang-box/SESSION-WRAP.md and continue."

If the ask is specifically the config.yaml sync: check `ssh tangbox "echo ok"`
first: if it fails to resolve, the box is still off/away, and there's nothing
to do yet but report that back.
