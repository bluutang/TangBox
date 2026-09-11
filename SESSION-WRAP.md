# Session Wrap — 2026-09-11 (late night)
> Written by: Claude Code (Sonnet 5) · Scope: tang-box

## ▶ READ THIS FIRST

Nothing urgent. The drive is synced and back with Brian (see the previous
wrap for that work — still accurate). This tail end of the session was SSH
access to the Pi: set up, tested, and documented.

## What this session did

**SSH access to the Pi (`tangbox.local`) is live from `Tangcito`.** Turned
out nothing needed generating — this Mac's existing key was already trusted
on the Pi — so it was just adding a `Host tangbox` shortcut to
`~/.ssh/config`. Confirmed working (`ssh tangbox`), and used immediately to
resolve the open Cosby-commercial question from the previous wrap: searched
`~/tangbox-commercials` (146 files) and the whole Pi home directory,
confirmed clean — no trace of it there now.

**Runnable setup steps for any other Mac are in `docs/lessons.md`** (under
"The Pi"), written the same way `docs/macbook-catch-up.md` is: instructions
aimed at whichever agent is running there, not at Brian to type by hand.
`Blue-Tangium` does not have this alias yet - the next agent that runs there
and needs it should find and follow that block directly rather than asking
Brian to run commands.

**Clarified a real limit of the memory system, at Brian's prompting.** He
asked this session to "run [the MacBook catch-up] next time you're on the
macbook." Worth restating here because it will come up again: a Claude Code
session's memory is local to the machine it runs on
(`~/.claude/projects/...`), so a note saved on `Tangcito` is invisible to a
session running on `Blue-Tangium` - there is no cross-machine memory sync.
The thing that actually carries the instruction across machines is the repo
itself: `docs/macbook-catch-up.md` plus the 🔴 blocker already in the
workspace-root `SESSION-WRAP.md`, which any agent reads at the start of a
session per `AGENT-PROTOCOL.md`. Nothing further needed here - it was
already wired correctly before this session touched it.

## Still open (unchanged from before, not this session's job)

- **The MacBook rename + three-agent parity** (`docs/macbook-catch-up.md`)
  is still not done, per the workspace-root wrap. Whoever is next on
  `Blue-Tangium` should run it.
- Nothing new pending on TangBox itself - the drive/library sync from
  earlier this session is the current, verified state.

## How to resume

Start a fresh session and say:
> "read tang-box/SESSION-WRAP.md and continue."

If you're on a Mac other than `Tangcito` and need `ssh tangbox`, the exact
steps are in `docs/lessons.md` under "The Pi" - run them yourself rather
than asking Brian to type commands.
