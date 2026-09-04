#!/usr/bin/env python3
r"""Download the tokyvideo plan, one file at a time, into the show's REAL folder.

Two traps this avoids, both found by inspection before anything was fetched:

1. THREE OF THESE SHOWS ALREADY EXIST, inside channel folders that
   organize-channels.py created - NickAccion/Avatar La Leyenda de Aang (13
   episodes, 3.7 GB), NickModerno/Bob Esponja, DisneyJr/Spidey... Writing to
   ROOT/<show> would have made a second copy of each show and re-fetched 4.5 GB
   that was already on disk.

2. THE EXISTING FILES ARE NAMED DIFFERENTLY - "Avatar La leyenda de Aang -
   S01E08.mp4", lower-case "leyenda" and no episode title - so a filename
   comparison finds nothing. Episodes are matched on the (season, episode)
   numbers parsed out of whatever the file happens to be called.

An episode already on disk is recorded in _archive.txt and skipped, so the
tracker counts it rather than reporting the show short forever.

curl gets -L (a missing -L silently wrote 65 empty files earlier) and -C - so an
interrupted download resumes.
"""
from __future__ import annotations
import json, re, subprocess, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path("/Users/briantang/Downloads/Converted")
PLAN = ROOT / "_tools" / "tokyvideo-plan.json"
LOG = ROOT / "_tokyvideo.log"
SE = re.compile(r"S(\d+)E(\d+)", re.I)

def say(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with LOG.open("a") as fh:
        fh.write(line + "\n")

def show_dir(name: str) -> Path:
    """Top level, or inside the channel folder the box uses."""
    direct = ROOT / name
    if direct.exists():
        return direct
    for chan in sorted(ROOT.iterdir()):
        if chan.is_dir() and not chan.name.startswith("_") and (chan / name).is_dir():
            return chan / name
    return direct

def on_disk(base: Path) -> set[tuple[int, int]]:
    got = set()
    for p in base.rglob("*.mp4"):
        m = SE.search(p.name)
        if m:
            got.add((int(m.group(1)), int(m.group(2))))
    return got

def main() -> int:
    plan = json.loads(PLAN.read_text())
    shows = sorted({p["show"] for p in plan})
    say(f"=== tokyvideo: {len(plan)} planned across {len(shows)} shows ===")
    for show in shows:
        base = show_dir(show)
        eps = [p for p in plan if p["show"] == show]
        have = on_disk(base)
        arch = base / "_archive.txt"
        done_urls = set(arch.read_text().split()) if arch.exists() else set()
        say(f">>> {show}  ({len(eps)} planned, {len(have)} already on disk) -> {base}")
        base.mkdir(parents=True, exist_ok=True)

        # FOUR AT A TIME. tokyvideo throttles per CONNECTION, not per IP -
        # measured: one connection 684 KB/s, three in parallel 672/790/761 KB/s
        # for 2.2 MB/s combined. Serially the remaining ~80 GB was a 39-hour job.
        # Four is deliberately modest; this is someone else's server.
        todo = []
        skipped = 0
        for p in eps:
            key = (p["season"], p["episode"])
            if key in have:
                if p["url"] not in done_urls:      # count it, do not re-fetch it
                    with arch.open("a") as fh: fh.write(p["url"] + "\n")
                    done_urls.add(p["url"])
                skipped += 1
            elif p["url"] in done_urls:
                skipped += 1
            else:
                todo.append(p)

        lock = threading.Lock()
        tally = {"ok": 0, "fail": 0}

        def fetch(p):
            dst = base / f"Season {p['season']:02d}" / p["file"]
            with lock:
                dst.parent.mkdir(parents=True, exist_ok=True)
            r = subprocess.run(["curl", "-sS", "--fail", "-L", "-C", "-",
                                "--retry", "10", "--retry-delay", "5",
                                "--connect-timeout", "30", "-o", str(dst), p["url"]])
            good = r.returncode == 0 and dst.exists() and dst.stat().st_size > 100_000
            with lock:                       # one writer at a time for the archive
                if good:
                    with arch.open("a") as fh: fh.write(p["url"] + "\n")
                    tally["ok"] += 1
                    say(f"  ok   {p['file'][:70]}  {dst.stat().st_size/1e6:.0f} MB")
                else:
                    tally["fail"] += 1
                    say(f"  FAIL {p['file'][:70]} (rc={r.returncode})")

        if todo:
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(fetch, todo))
        say(f"    {show}: {tally['ok']} fetched, {skipped} already had, {tally['fail']} failed")
    say("=== tokyvideo done ===")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
