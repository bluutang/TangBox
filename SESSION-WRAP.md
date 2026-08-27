# Session wrap — five Spanish playlists (2026-08-27) — DOWNLOADS RUNNING

Five YouTube playlists queued into `/Users/briantang/Downloads/Converted/`.
**Nothing needs doing until the downloads finish.** They run without Claude —
closing Claude Code does not stop them. Only a shutdown or sleep does.

## Check progress without spending Claude usage

Open **`/Users/briantang/Downloads/Converted/_status.html`** in a browser. It
refreshes itself every 15s: episodes done, GB, live speed, ETA, and what is
downloading right now. A background loop regenerates it.

    running now   ps -Ao args= | grep -E '[g]et-playlist|[r]un-queue|[w]atch-status'
    queue log     tail -f "/Users/briantang/Downloads/Converted/_queue.log"
    stop all      pkill -f run-queue.sh; pkill -f get-playlist.sh
    resume        cd .../Converted && nohup ./_tools/run-queue.sh >> _queue.log 2>&1 &

Turning the VPN off mid-download is safe: yt-dlp retries the dropped connection
(`--retries 10`). The speed on the status page should jump ~20x within a minute,
which is the confirmation it worked.

Resuming is free: each show has `_archive.txt` listing finished video IDs, so
nothing is ever fetched twice.

## Order and totals (after the 1.5 h cap)

| # | Show | Videos | → Episodes | State |
|---|---|---:|---:|---|
| 1 | Daniel Tigre | 61 | ~83 | **downloading** |
| 2 | Franklin | 78 | 78 | paused at 7, queued |
| 3 | Barney el Dinosaurio | 41 | ~58 | queued (2 playlists → 1 folder) |
| 4 | Jorge el Curioso | 34 | ~73 | queued |
| 5 | Pistas de Blue y tú | 82 | ~52 | queued |
|   | **Total** | **296** | **~344** | ~67 GB, 314 GB free |

Episode counts are estimates from duration and are **before** content-dedupe.

## Decisions made this session

- **Discard anything over 1.5 hours.** Cut 32 videos and 108 GB → 67 GB, almost
  all from Daniel (47.7 → 14.9 GB). Those were themed compilations repackaging
  episodes that survive elsewhere in the same playlist.
- **A 20–25 min piece is a finished episode**, even when it is really two 11-min
  shorts joined. So Franklin is never split, and `--min-episode` is 18 min.
- **ProtonVPN ON for Daniel Tigre, then OFF.** It throttles to ~261 KB/s (from
  5.4 MB/s), but Daniel is region-blocked without it, so access beats speed for
  show 1. Brian plans to switch it off once Daniel finishes. The other four are
  not known to be blocked, and at full speed the remaining ~52 GB goes from
  ~60 h to roughly 3 h.
  **If episodes start failing after the VPN is off, turn it back on.**
  `get-playlist.sh` runs with `--ignore-errors`, so a geo-block is skipped
  quietly rather than shouting - watch the episode count on the status page,
  not the log. Anything skipped is re-fetched simply by re-running the queue.
- **Download everything, then split with ffmpeg** — Brian's call over a
  narrower recommendation to skip compilations entirely.

## Tools built (all in `Converted/_tools/`)

| File | Does |
|---|---|
| `get-playlist.sh` | `get-playlist.sh "Show" URL` → `_staging/`. H.264 only, ≤1.5 h, resumable. |
| `run-queue.sh` | Runs shows 2–5 sequentially once the current one ends. |
| `detect-breaks.py` | Finds episode joins in a compilation; `--split` cuts. |
| `status.py` / `watch-status.sh` | Regenerate `_status.html`. |
| `shows.json` | Expected videos/bytes per show, used by the status page. |

## Next, once downloads finish

1. **Detect** — run `detect-breaks.py` over every compilation and **show Brian
   the proposed cuts before cutting anything**. The rule is a heuristic.
2. **Split** — `--split` on the approved ones.
3. **Dedupe by content**, not title. Daniel especially: the same stories recur
   across themed compilations.
4. **Rename + move** into `Show/Season 01/`, then delete `_staging`, `_tools`,
   `_archive.txt`, `_download.log`.
5. **Update the spreadsheet** — `Lineup` col O, `Named`=0, and one `Episodes`
   row per file, preserving `Verified` / `Actually contains`.
6. **Move to the USB drive**, not the microSD.

## How `detect-breaks.py` works

One ffmpeg pass reports black frames and silences. A join is where **both**
happen at once — a dark scene or a dramatic pause has only one. Candidates
within 150 s are one join and the **last** is kept, so the cut lands *after* the
credits roll rather than before it (Brian caught this; cutting on the first
would put the previous episode's credits on the head of the next one).
Validated: a 23-min Franklin episode returns 1 piece, and its real 11:43
mid-episode story break is correctly ignored under the 18-min floor.
Scans at ~53× realtime.

## Naming — decide before renaming

Plaza Sésamo used **YouTube topical titles**, a deliberate exception to the
no-titles rule in CLAUDE.md (that rule targets *looked-up database* titles
landing on wrong files). These five are the same case, but split pieces have no
natural title. Suggest `Show - S01E07.mp4` numbering for split output.

## Gotchas

- **H.264 only.** yt-dlp's default "best" serves AV1 and the Pi 5 cannot
  hardware-decode it. The format string in `get-playlist.sh` pins avc1.
- `_archive.txt` only appears after the **first** video completes. Its absence
  early on is normal, not a failure.
- Barney's two playlists share 11 identical compilations; one folder and one
  archive dedupes them automatically (58 videos → 47 unique, 41 after the cap).
- Brian's earlier "split Jorge's 2-hour video at 55:33" is **moot** — the cap
  discards it. The remaining 34 Jorge videos are ~45 min and halve cleanly.
- Daniel's playlist has duplicate uploads of the same episode at both 22:47 and
  21:50 (5 confirmed by title). The content-dedupe pass must catch these.

## Carried over from the previous wrap — still outstanding

**Plaza Sésamo (80 episodes, 14 GB) has not been moved to the USB drive.** It is
complete and on the Mac at `Converted/Plaza Sésamo/Season 01/`, spreadsheet
already updated. Delete its `_tools/` and `_archive.txt` when moving. Also still
open from that session: `Lineup` L2/M2 hold *US Sesame Street* totals (56
seasons / 4662 episodes) so the progress bar reads 80/4662; and the
`Seasons breakdown` tab documented in CLAUDE.md does not exist in the
spreadsheet — worth checking version history for a deletion.

## Repo

`tang-box` working tree is clean apart from this file. Nothing was committed;
no box code was changed this session. All work landed in `~/Downloads/Converted/`.
