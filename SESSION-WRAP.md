# Session Wrap — 2026-09-07 (evening)
> Written by: Claude Code (Opus 5) · Scope: tang-box

## ▶ READ THIS FIRST — the box is BACK ON THE AIR

The drive is in the Pi, the library is complete, TangBox is running and Brian put
it on **standby**. Nothing is owed. There is no blocker.

* USB drive reattached to the Pi and mounted at `/media/tangbox` (read-only).
* `tangbox.service` is **active** — 23 channels, 4,031 episodes, no errors.
* Mac and drive are now **byte-for-byte in agreement**: 70 shows, 4,031 episodes.

🔑 **Hot-plugging the drive does NOT mount it.** `/etc/fstab` has the entry
(`UUID=6A9A-7E45 → /media/tangbox`, `ro,nofail`) but fstab only runs at boot, and
the Pi had been up 13 days. After plugging the drive into a running Pi:

```sh
ssh brian@192.168.1.41 'sudo mount /media/tangbox && sudo systemctl start tangbox.service'
```

Check the UUID matches before mounting: `sudo blkid /dev/sda2`.

## 🔴 The correction that matters most

**The Mac is the source of truth for what the library ACTUALLY contains.** Brian
curates the channel folders in `~/Downloads/Converted` by hand — adding, pruning
and swapping versions. The Google Sheet is the *shopping list* (what it should
contain) and it lags, sometimes badly.

This is now written up in `docs/lessons.md` (commit `d3edf9b`, pushed) along with
its limit: absence on the Mac is not on its own grounds to delete from the drive.
**Ask Brian what an absence means before removing anything** — external-drive
deletions skip the Trash.

An earlier version of this session got that backwards, proposed deletions from a
disk-only inference, and had to be corrected. Read the lesson before syncing.

## What changed on the drive

| Show | Change |
|---|---|
| Pocoyo | **+62 eps** (new, 2.9 GB) |
| Puffin Rock | **+26 eps** (new, 1.9 GB) |
| Patoaventuras | 48 → **97 eps** — the 1987 original REPLACED the 2017 reboot rip entirely |
| Coraje El Perro Cobarde | **removed**, 48 eps — English audio (see `docs/lessons.md`) |
| Dora la Exploradora | 61 → **35** — the 26 removed were the **3D reboot**; the classic 2D is what is wanted |
| Los Padrinos Mágicos | 120 → **116** — 4 oversized S06 files dropped |
| Jorge el Curioso | `_unsplit/` working folder removed (224 MB) |

Every removal is logged in **`_removed-2026-09-07.json` at the drive root**, with
sizes and, for Dora, the YouTube IDs.

Patoaventuras was a true replacement: no shared filename was byte-identical and
the originals are consistently larger at the same episode number, so the two rips
were never mixed.

## The Google Sheet is now reconciled

It was far more out of date than anyone knew. Fixed this session:

* **24 episode counts corrected** — Dragon Ball Z said 1, disk had 291; Bluey 1 vs 150; KND 1 vs 71; Spidey 1 vs 85
* **8 rows flipped Wanted → HAVE** that already had files, incl. Los Padrinos (116) and Jackie Chan (73 — its note still claimed the show was undownloadable)
* **5 rows set back to Wanted** — Snoopy Show, Maya y los tres, Tibucán, Spider-Man, Escandalosos. Their "pilot only" file exists on neither drive nor Mac; nobody recorded when it went
* **26 shows ADDED that had no row at all** — 1,227 episodes, incl. Arthur 65, Clifford 79, Octonautas 85, Digimon 104, Uncle Calvin 102

Writing to the sheet needs `workspace-mcp`, which connected fine this session.

## The button-cascade fix is intact

Brian saw presses cascade again mid-session. **Not a regression.** The duration
cache (`~/.cache/tangbox/durations.json`, commit `57f2650`) validates on size and
mtime, and this session handed the box 185 files it had never seen — Patoaventuras
97 (all new, even same-named files), Pocoyo 62, Puffin Rock 26. First tune-in to
Disney Aventura cost ~11 s and Netflix Jr ~10 s, while concurrent SSH `find` runs
competed for the same USB bus.

Now fully warm and tidied:

```
cache entries : 4177   (4031 episodes + 146 commercials; all point at real files)
WOULD RE-PROBE: 0
```

128 dead entries from today's deletions were pruned (backup at
`durations.json.bak`). ⚠️ The running process still holds the pre-prune copy in
memory; if it probes anything new before its next restart it will write those
dead entries back. Harmless, and it becomes permanent at the next restart.

## Smaller open items

* **Sheet: the 26 new rows have no Seasons or Total episodes**, so their progress
  bars are blank. Deliberate — never write a count from memory (the Rugrats
  lesson). They need a real lookup.
* **Sheet row 76 duplicates row 52** (both "Pistas de Blue y tú"; row 52 holds the
  real 43 episodes). Left in place because deleting a row shifts the ARRAYFORMULA
  range in column R.
* **`_removed-2026-09-07.json` on the drive still frames the Dora removal as an
  error.** It was not — Brian removed the 3D reboot deliberately. One-line fix
  next time the drive is on the Mac, so it stops contradicting the sheet.
* **Remote responsiveness is unverified by Brian** since the cache warmed. If it
  still stutters, the cause is NOT probing — investigate properly, do not guess.
* 4 Pocoyo uploads unfetched (YouTube rate-limited); worth ~2 episodes.
* Guardaespíritus S02E28 is missing from its source, not a failed download.
* Trash Truck still unfetchable — its only sources sit behind Cloudflare anti-bot
  and need resolved stream URLs, as Puffin Rock's did.

## How to resume

Start a fresh session and say:
> "read tang-box/SESSION-WRAP.md and continue."

Nothing is urgent. The likeliest next job is looking up seasons/total episodes for
the 26 newly added shows so the sheet's progress bars work again.
