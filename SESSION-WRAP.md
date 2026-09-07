# Session Wrap — 2026-09-07
> Written by: Claude Code (Opus 5) · Scope: tang-box

## ▶ READ THIS FIRST — the box is DARK and the drive is out

The television is off and TangBox is not playing anything. This is deliberate,
not a fault, but it should not stay this way long.

* `tangbox.service` was **stopped** on 2026-09-07 so the USB drive could be
  removed safely (standby alone is not enough — it leaves the drive mounted, and
  exFAT has no journal, so pulling it mid-write can corrupt the filesystem).
* `/media/tangbox` was cleanly unmounted first.
* **The drive is physically plugged into the Mac right now**, mounted as
  `/Volumes/TANGBOX` — 920 GB exFAT, 698 GB used, 290 GB free.

To bring the box back after the drive is returned:

```sh
ssh brian@192.168.1.41 'sudo systemctl start tangbox.service'
```

⚠️ That wakes the television. Do it when that is welcome.

## 🔴 BLOCKER — macOS will not let the agent read the drive

`ls /Volumes/TANGBOX` returns **"Operation not permitted"**. The drive is
healthy; macOS gates removable media per-application and the terminal has not
been granted access.

The terminal here is **Ghostty** (`/Applications/Ghostty.app`).

**System Settings → Privacy & Security → Files and Folders → Ghostty → enable
"Removable Volumes"**. If Ghostty is not listed, add it under **Full Disk
Access** instead. Then **fully quit Ghostty (⌘Q) and reopen** — the permission
is read at launch.

Confirm with `ls /Volumes/TANGBOX | head`. Show or channel folders means it
worked.

## The job: align the drive with this Mac

~19 GB has never reached the box. All 70 shows now have `tile.jpg`, so the
library is otherwise ready.

| Show | Channel | Episodes |
|---|---|---|
| Patoaventuras (1987 original) | DisneyAventura | 97 |
| Pocoyo | NetflixJr | 62 |
| Puffin Rock | NetflixJr | 26 |

Order of work once the permission is granted:

1. **Survey both sides first.** Compare `/Volumes/TANGBOX` against
   `~/Downloads/Converted` show by show. The sync may not be one-directional —
   there may be shows on the drive that are not on this Mac. Do not assume.
2. **Run `media-tools/check-exfat.py`** before copying. exFAT rejects characters
   macOS allows, and a bad name fails the copy partway through 19 GB.
3. **Copy the three shows** with their `tile.jpg` files.
4. **Verify by file count and total size**, not by the copy command exiting.
5. Eject cleanly, reattach to the Pi, restart the service.

Nothing on the drive should be deleted without showing Brian first.

## Also worth knowing
* The Pi had been up **13 days** with the service running. An earlier wrap noted
  a restart was owed for stale Doug paths in Nick Clásico — this stop/start
  clears that, since the schedule rebuilds at startup.
* The running box reads `/home/brian/TangBox/config.yaml`, which is **gitignored
  and machine-local**. `config.pi.yaml` in this repo is a template the box never
  opens — pointing channels at the drive is a manual SSH edit.
* **The Google Sheet is behind**: Patoaventuras 97, Pocoyo 62, Puffin Rock 26 are
  new or changed; Coraje's row comes out; Los Padrinos is 116 not 120. Writing to
  it needs `workspace-mcp`, which would not connect on 2026-09-05/07.
* Read `docs/lessons.md` before any media work — codec pinning, truncation
  screening, and verifying spoken language rather than trusting tags.

## Smaller open items
* 4 Pocoyo uploads unfetched (YouTube rate-limited us); worth ~2 episodes. The
  resume command is in the workspace wrap.
* Guardaespíritus S02E28 is missing from its source, not a failed download.
* Trash Truck could not be fetched — its only sources sit behind Cloudflare
  anti-bot. It needs resolved stream URLs, as Puffin Rock's data had.

## How to resume
Start a fresh session and say:
> "read tang-box/SESSION-WRAP.md and continue."
