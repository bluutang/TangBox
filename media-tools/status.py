#!/usr/bin/env python3
"""Render a self-refreshing download status page to _status.html.

Reads three things per show: _archive.txt (one line per FINISHED video, the
only trustworthy "done" count), the _staging folder size, and the tail of
_download.log for whatever yt-dlp is chewing on right now. Speed is measured
by remembering the previous sample in .status-state.json and dividing the
byte delta by the elapsed time, so it reflects real throughput rather than
whatever yt-dlp last printed.
"""
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

ROOT = Path("/Users/briantang/Downloads/Converted")
TOOLS = ROOT / "_tools"
OUT = ROOT / "_status.html"
STATE = TOOLS / ".status-state.json"
# Average throughput over this many seconds; ignore any ETA longer than MAX_ETA.
# An ETA beyond a day is arithmetic on a stalled download, not a real forecast,
# and printing "55142h" makes the whole page look broken when only one number is.
HIST_WINDOW = 120.0
MAX_ETA = 24 * 3600
REFRESH = 15

PROG = re.compile(r"\[download\]\s+([\d.]+)%\s+of\s+~?\s*([\d.]+\w+)(?:\s+at\s+([\d.]+\w+/s))?")
DEST = re.compile(r"\[download\] Destination:\s*(.+)")


def human(n: float) -> str:
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            return f"{n:.1f} {u}" if u != "B" else f"{int(n)} B"
        n /= 1024
    return ""


def hms(s: float) -> str:
    if s <= 0 or s != s or s == float("inf"):
        return "--"
    s = int(s)
    if s >= 3600:
        return f"{s // 3600}h {(s % 3600) // 60:02d}m"
    return f"{s // 60}m {s % 60:02d}s"


_DIR_CACHE: dict = {}

def show_dir(name: str) -> Path:
    """Where a show lives - top level, or inside its channel folder.

    organize-channels.py moves each show into the channel folder the box
    expects (NickJr/Franklin/...), so a show is at ROOT/name before the move
    and ROOT/<channel>/name after it. Looking only at the top level made every
    moved show read "not started" with its episodes intact on disk.
    """
    if name in _DIR_CACHE:
        return _DIR_CACHE[name]
    direct = ROOT / name
    found = direct
    if not (direct / "_archive.txt").exists() and not direct.exists():
        for chan in ROOT.iterdir():
            if chan.is_dir() and not chan.name.startswith("_") and (chan / name).exists():
                found = chan / name
                break
    elif not (direct / "_archive.txt").exists():
        for chan in ROOT.iterdir():
            if chan.is_dir() and not chan.name.startswith("_") and (chan / name / "_archive.txt").exists():
                found = chan / name
                break
    _DIR_CACHE[name] = found
    return found


def dir_bytes(p: Path) -> int:
    if not p.exists():
        return 0
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def processing_shows() -> set[str]:
    """Shows an ffmpeg is currently working on.

    Downloading is not the only slow thing that happens to a show: splitting a
    45-minute compilation into episodes re-encodes for half an hour and moves no
    bytes over the network. Without this the page showed such a show as idle -
    Brian asked "so downloads are occurring right now? the tracker is unclear"
    while Rolie Polie Olie was 5/29 of the way through being cut.

    The show name is matched against ffmpeg's command line, which carries the
    input path.
    """
    try:
        out = subprocess.run(["ps", "-Ao", "args="], capture_output=True, text=True).stdout
    except Exception:
        return set()
    busy = set()
    for line in out.splitlines():
        # Skip orchestration shells. A `bash -c` wrapper that runs three shows in
        # sequence names ALL of them on one command line, so matching it marks
        # every one as busy - which is exactly what happened when Rolie Polie
        # Olie was being cut and Gargoyles and Mighty Ducks had not started.
        # Only real workers count: ffmpeg, curl, yt-dlp, get-archive.
        if line.lstrip().startswith(("bash", "/bin/bash", "sh ", "/bin/sh", "nohup", "zsh", "/bin/zsh")):
            continue
        if "ffmpeg" not in line or "shell-snapshots" in line or "grep" in line:
            continue
        for name in SHOWS:
            if name in line:
                busy.add(name)
    return busy


def _cwd_of(pid: str) -> str:
    """A worker's working directory, which often names the show when its command
    line does not."""
    try:
        out = subprocess.run(["lsof", "-a", "-p", pid, "-d", "cwd", "-Fn"],
                             capture_output=True, text=True, timeout=5).stdout
    except Exception:
        return ""
    for line in out.splitlines():
        if line.startswith("n"):
            return line[1:]
    return ""


def running_shows() -> set[str]:
    try:
        out = subprocess.run(["ps", "-Ao", "pid=,args="], capture_output=True, text=True).stdout
    except Exception:
        return set()
    live = set()
    for raw in out.splitlines():
        raw = raw.strip()
        pid, _, line = raw.partition(" ")
        # Not just yt-dlp: the archive.org shows (Arthur, Dragon Ball Z, Bear)
        # are fetched by get-archive.py driving curl, with no yt-dlp anywhere.
        # Matching only "yt-dlp" meant they could never be seen as running, so
        # the page labelled Bear "stopped early" while it was downloading at
        # 12 MB/s. Both the curl and the python line carry the show name - curl
        # through its -o output path.
        # THREE downloaders now, not one: yt-dlp for YouTube, get-archive.py for
        # archive.org, and plain curl for tokyvideo. Each time a new one was added
        # this check went stale and the page showed a live download as "stopped".
        # Match any of them, then skip our own diagnostic shells so a command that
        # merely mentions a show name is not mistaken for a download.
        if not any(k in line for k in ("yt-dlp", "get-archive", "tokyvideo", "curl ")):
            continue
        if "shell-snapshots" in line or "grep" in line:
            continue
        # same wrapper problem as above
        if line.lstrip().startswith(("bash", "/bin/bash", "sh ", "/bin/sh", "nohup", "zsh", "/bin/zsh")):
            continue
        hit = False
        for name in SHOWS:
            if name in line:
                live.add(name); hit = True
        if not hit:
            # A job that cd's into the show folder and uses a relative -o path
            # never names the show on its command line. Ms. Nenna downloaded for
            # twenty minutes looking idle for exactly this reason.
            cwd = _cwd_of(pid)
            if cwd:
                for name in SHOWS:
                    if name in cwd:
                        live.add(name)
    return live


def tail_log(p: Path, n: int = 40000) -> str:
    if not p.exists():
        return ""
    with p.open("rb") as fh:
        try:
            fh.seek(-n, 2)
        except OSError:
            fh.seek(0)
        return fh.read().decode("utf-8", "replace").replace("\r", "\n")


SHOWS = json.loads((TOOLS / "shows.json").read_text())


def queue_order() -> list:
    """(show, source) in the order the queue will actually fetch them.

    Read from the newest run-queue script rather than kept as a second list, so
    the page can never disagree with what is really going to happen. Shows named
    twice (Dora is fetched in two passes) keep their first position.
    """
    # Newest by MODIFICATION TIME, not by digits in the name. Sorting on digits
    # made "run-queue15.sh" (the original) beat "run-queue-rest2.sh" (the one
    # actually running), so the page showed a stale order and every show added
    # after run-queue15 was written had no source at all.
    scripts = sorted(TOOLS.glob("run-queue*.sh"), key=lambda f: f.stat().st_mtime)
    if not scripts:
        return [(n, "?") for n in SHOWS]
    text = scripts[-1].read_text()
    seen, out = set(), []
    for kind, name in re.findall(r'^run_(show|archive)\s+"([^"]+)"', text, re.M):
        if name in seen:
            continue
        seen.add(name)
        out.append((name, "YouTube" if kind == "show" else "archive.org"))
    # Anything not named in the queue script goes last, but still shows where it
    # comes from: shows.json carries a "source" for anything started by hand
    # (Journey to the West, the Digimon items) so the page never prints a bare
    # dash and leaves the reader guessing.
    for n in SHOWS:
        if n not in seen:
            out.append((n, SHOWS[n].get("source", "-")))
    return out


def gather():
    now = time.time()
    prev = {}
    if STATE.exists():
        try:
            prev = json.loads(STATE.read_text())
        except Exception:
            prev = {}
    live = running_shows()
    busy = processing_shows()
    # A rolling history, not just the previous sample. Speed used to be one
    # 15-second derivative, so a pause between files read as ~0 B/s and the ETA
    # divided by it - the page showed "170 B/s / about 55142h remaining" while
    # downloads were merely stalled. Averaging over ~2 minutes rides out the gaps.
    hist = [h for h in prev.get("hist", []) if now - h[0] <= HIST_WINDOW]
    rows, state = [], {"t": now, "shows": {}, "hist": hist}
    tot_done = tot_exp = tot_bytes = tot_est = 0

    for name, source in queue_order():
        meta = SHOWS.get(name)
        if meta is None:
            continue
        show = show_dir(name)
        arch = show / "_archive.txt"
        done = len(arch.read_text().splitlines()) if arch.exists() else 0
        by = dir_bytes(show / "_staging") or dir_bytes(show)
        state["shows"][name] = by

        # The baked-in estimate (525 MB per hour, measured off Plaza Sesamo) is a
        # poor guide: Franklin encodes at roughly 206 MB/h, so its total was being
        # overstated 2.4x and the page implied gigabytes still to come when only a
        # few episodes remained. Once enough videos have landed, re-estimate from
        # what THIS show actually weighs per video.
        est = meta["est_bytes"]
        # Correct from two finished videos rather than five: a 3-item show like
        # the Sailor Moon films never reached the old threshold, so it kept a
        # guess that was three times too small and read "1.0 GB of ~716.8 MB".
        if done >= 2 and by > 0:
            est = int(by / done * meta["videos"])
        # Whatever the estimate says, it cannot be less than what is already on
        # disk - otherwise the bar overflows and the ETA goes negative.
        est = max(est, by)

        # Oldest sample still inside the window gives the longest baseline, so a
        # single quiet interval cannot drag the rate to zero.
        base = next(((t, sh.get(name)) for t, sh in hist if sh.get(name) is not None), None)
        if base is None:
            pb, dt = prev.get("shows", {}).get(name), now - prev.get("t", now)
        else:
            pb, dt = base[1], now - base[0]
        speed = (by - pb) / dt if (pb is not None and dt > 2 and by > pb) else 0.0

        log = tail_log(show / "_download.log")
        # yt-dlp prints this once it has walked the whole playlist. Its presence
        # is what separates "finished, some videos would not come down" from
        # "the run died partway" - the two look identical by episode count alone.
        finished = "Finished downloading playlist" in log
        cur, pct = "", None
        d = DEST.findall(log)
        if d:
            cur = Path(d[-1].strip()).name
        m = PROG.findall(log)
        if m:
            pct = float(m[-1][0])

        started = show.exists() and (by > 0 or done > 0)
        if name in live:
            status = "running"
        elif name in busy:
            status = "processing"
        elif done >= meta["videos"]:
            status = "done"
        elif finished:
            status = "incomplete"      # walked the whole playlist, some failed
        elif started:
            status = "stopped"         # really did stop early
        else:
            status = "waiting"
        eta = (est - by) / speed if speed > 0 else 0

        # The channel a show sits in, and whether it has the tile picture the
        # guide draws. Both show as colour tags in Finder; the page should not
        # disagree with what the folders say.
        chan = show.parent.name if show.parent != ROOT else ""
        art = (show / "tile.jpg").exists() or (show / "tile.png").exists()
        rows.append(dict(channel=chan, art=art,
                         name=name, done=done, total=meta["videos"], bytes=by,
                         est=est, speed=speed, cur=cur, pct=pct,
                         status=status, eta=eta, source=source,
                         missing=max(0, meta["videos"] - done),
                         frac=min(1.0, done / meta["videos"]) if meta["videos"] else 0))
        tot_done += done; tot_exp += meta["videos"]; tot_bytes += by; tot_est += est

    # Whole-catalogue size against the 1 TB USB drive - staging AND finished
    # episodes, since both end up on the drive.
    cat = sum(f.stat().st_size for f in ROOT.rglob("*.mp4") if f.is_file())
    state["hist"] = hist + [[now, dict(state["shows"])]]
    STATE.write_text(json.dumps(state))
    tot_speed = sum(r["speed"] for r in rows)
    return rows, dict(catalogue=cat, drive=1_000_000_000_000,
                      done=tot_done, total=tot_exp, bytes=tot_bytes, est=tot_est,
                      speed=tot_speed,
                      # A show can be running hard while moving zero bytes: yt-dlp
                      # spends long stretches fetching video info, one second apart,
                      # and skipping unavailable videos. Speed alone therefore cannot
                      # answer "is anything happening" - ask the process list.
                      running=any(r["status"] == "running" for r in rows),
                      eta=(tot_est - tot_bytes) / tot_speed if tot_speed > 0 else 0)


DOT = {"running": ("#2f8f5b", "downloading"), "done": ("#3a6ea5", "complete"),
       "incomplete": ("#3a6ea5", "finished"), "stopped": ("#b06a2c", "stopped"),
       "waiting": ("#9a9a94", "not started"),
       # amber: being cut or re-encoded, not downloading and not stalled
       "processing": ("#8a6bbf", "splitting")}


def render(rows, tot) -> str:
    cards = []
    for r in rows:
        col, label = DOT[r["status"]]
        pctnum = r["frac"] * 100
        line = ""
        if r["status"] == "running" and r["cur"]:
            p = f' &middot; {r["pct"]:.0f}%' if r["pct"] is not None else ""
            line = f'<div class="cur">now: <code>{r["cur"]}</code>{p}</div>'
        elif r["status"] == "incomplete":
            line = (f'<div class="cur">finished the whole playlist; <b>{r["missing"]}</b> '
                    f'could not be downloaded. Re-running fetches only those.</div>')
        elif r["status"] == "stopped":
            line = '<div class="cur warn">stopped early &mdash; re-run the script to resume</div>'
        spd = f'{human(r["speed"])}/s' if r["speed"] > 0 else "&mdash;"
        cards.append(f"""
      <div class="show">
        <div class="head">
          <span class="dot" style="background:{col}"></span>
          <h2>{r["name"]}</h2>
          <span class="tag">{(r["channel"] + " &middot; ") if r["channel"] else ""}{r["source"]} &middot; {label}</span>
          {'<span class="flag flag-art">no tile</span>' if not r["art"] else ""}
          {'<span class="flag flag-inc">incomplete</span>' if r["done"] < r["total"] else ""}
        </div>
        <div class="bar"><span style="width:{pctnum:.1f}%;background:{col}"></span></div>
        <div class="stats">
          <div><b>{r["done"]}</b> / {r["total"]} episodes</div>
          <div>{human(r["bytes"])} <span class="dim">of ~{human(r["est"])}</span></div>
          <div>{spd}</div>
          <div class="dim">{("ETA " + hms(r["eta"])) if 0 < r["eta"] <= MAX_ETA else ("stalled" if r["status"] == "running" and r["speed"] <= 0 else "")}</div>
        </div>
        {line}
      </div>""")

    overall = tot["done"] / tot["total"] * 100 if tot["total"] else 0
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="{REFRESH}">
<title>TangBox downloads</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Jost:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  :root {{ color-scheme: light; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; padding:56px 24px 80px; background:#faf9f6; color:#2b2a27;
         font-family:'Jost',-apple-system,BlinkMacSystemFont,'Helvetica Neue',sans-serif;
         font-weight:300; display:flex; justify-content:center; }}
  .wrap {{ width:100%; max-width:660px; }}
  h1 {{ font-size:1.5rem; font-weight:400; margin:0 0 4px; letter-spacing:.01em; }}
  .sub {{ color:#82807a; font-size:.85rem; margin-bottom:34px; }}
  .total {{ background:#fff; border:1px solid #ebe8e1; border-radius:12px;
            padding:22px 24px; margin-bottom:30px; }}
  .total .big {{ font-size:2rem; font-weight:400; }}
  .total .row {{ display:flex; justify-content:space-between; align-items:flex-end;
                 margin-bottom:14px; }}
  .show {{ background:#fff; border:1px solid #ebe8e1; border-radius:12px;
           padding:20px 24px; margin-bottom:14px; }}
  .head {{ display:flex; align-items:center; gap:10px; margin-bottom:14px; }}
  h2 {{ font-size:1rem; font-weight:500; margin:0; flex:1; }}
  .dot {{ width:9px; height:9px; border-radius:50%; flex:none; }}
  .tag {{ font-size:.72rem; color:#82807a; }}
  .bar {{ height:6px; background:#f0eee8; border-radius:3px; overflow:hidden; margin-bottom:13px; }}
  .bar span {{ display:block; height:100%; border-radius:3px; transition:width .4s ease; }}
  .stats {{ display:grid; grid-template-columns:repeat(4,1fr); gap:8px;
            font-size:.82rem; color:#4b4945; }}
  .stats b {{ font-weight:500; }}
  .dim {{ color:#9a9891; }}
  /* these match the Finder tags: purple = no tile, red = incomplete */
  .flag {{ font-size:.62rem; padding:2px 7px; border-radius:9px; margin-left:6px;
           vertical-align:middle; white-space:nowrap; }}
  .flag-art {{ background:#8a6bbf22; color:#8a6bbf; border:1px solid #8a6bbf55; }}
  .flag-inc {{ background:#b0432c22; color:#b0432c; border:1px solid #b0432c55; }}
  .cur {{ margin-top:12px; font-size:.76rem; color:#82807a;
          overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
  .cur code {{ font-family:ui-monospace,Menlo,monospace; font-size:.72rem; color:#5c5a55; }}
  .warn {{ color:#b06a2c; }}
  footer {{ margin-top:28px; text-align:center; color:#a5a39c; font-size:.74rem; }}
  @media (max-width:520px) {{ .stats {{ grid-template-columns:repeat(2,1fr); }} }}
</style></head><body><div class="wrap">
  <h1>TangBox downloads</h1>
  <div class="sub">refreshes every {REFRESH} seconds on its own</div>
  <div class="total">
    <div class="row">
      <div><div class="big">{tot["done"]} <span class="dim" style="font-size:1rem">/ {tot["total"]} episodes</span></div></div>
      <div style="text-align:right">
        <div style="font-size:1.05rem">{human(tot["speed"])}/s</div>
        <div class="dim" style="font-size:.78rem">{human(tot["bytes"])} of ~{human(tot["est"])}</div>
      </div>
    </div>
    <div class="bar"><span style="width:{overall:.1f}%;background:#2f8f5b"></span></div>
    <div class="dim" style="font-size:.78rem;margin-top:11px">
      {("about " + hms(tot["eta"]) + " remaining")
        if 0 < tot["eta"] <= MAX_ETA else
        ("still downloading, but too slow to estimate &mdash; usually YouTube "
         "throttling or a stalled show"
         if tot["running"] and tot["speed"] > 0 else
        ("downloading &mdash; fetching video info, no data moving this second"
         if tot["running"] else "nothing downloading right now"))}
    </div>
  </div>
  {"".join(cards)}
  <div class="total" style="margin-top:6px">
    <div class="row">
      <div><div style="font-size:1.05rem">{human(tot["catalogue"])} <span class="dim" style="font-size:.85rem">on the USB drive</span></div></div>
      <div style="text-align:right" class="dim">{tot["catalogue"]/tot["drive"]*100:.1f}% of 1 TB &middot; {human(tot["drive"]-tot["catalogue"])} free</div>
    </div>
    <div class="bar"><span style="width:{min(100,tot["catalogue"]/tot["drive"]*100):.1f}%;background:#3a6ea5"></span></div>
  </div>
  <footer>updated {time.strftime("%H:%M:%S")}</footer>
</div></body></html>"""


if __name__ == "__main__":
    rows, tot = gather()
    OUT.write_text(render(rows, tot), encoding="utf-8")
    print(f"{OUT}  ({tot['done']}/{tot['total']} episodes, {human(tot['speed'])}/s)")
