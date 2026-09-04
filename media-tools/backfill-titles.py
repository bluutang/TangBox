#!/usr/bin/env python3
r"""Add the video title to files downloaded before the template carried one.

get-playlist.sh wrote "%(playlist_index)03d-%(id)s.%(ext)s" until 2026-08-30, so
anything fetched before then is a bare index and id. The id makes the title
recoverable, so this is a rename, not a re-download.

These are YouTube's own titles, shipped with the video - the safe kind. The rule
against titles in filenames covers LOOKED-UP database titles matched to episodes
by number, which is what put wrong names on 246 files.

    python3 _tools/backfill-titles.py "Uncle Calvin" _tools/uncle-calvin-titles.json
    python3 _tools/backfill-titles.py "Uncle Calvin" ... --apply
"""
from __future__ import annotations
import json, re, sys, unicodedata
from pathlib import Path

ROOT = Path("/Users/briantang/Downloads/Converted")
BAD = {'"': "'", "*": "+", "/": "-", ":": " -", "<": "(", ">": ")",
       "?": "", "\\": "-", "|": "｜"}

def safe(t: str) -> str:
    t = unicodedata.normalize("NFC", t)
    for k, v in BAD.items():
        t = t.replace(k, v)
    return re.sub(r"\s+", " ", t).strip().rstrip(".")[:110]

def main() -> int:
    show, mapfile = sys.argv[1], sys.argv[2]
    apply = "--apply" in sys.argv
    titles = json.loads(Path(mapfile).read_text())
    stage = ROOT / show / "_staging"
    moves, missing, already = [], [], 0
    for p in sorted(stage.glob("*.mp4")):
        m = re.match(r"^(\d{3})-([A-Za-z0-9_-]{11})$", p.stem)
        if not m:
            already += 1          # already has a title, or a different shape
            continue
        idx, vid = m.group(1), m.group(2)
        if vid not in titles:
            missing.append(p.name); continue
        moves.append((p, p.with_name(f"{idx}-{vid} - {safe(titles[vid])}.mp4")))

    print(f"  {len(moves)} to rename, {already} already titled, {len(missing)} no title found")
    # two files must never collide into one name - that would delete an episode
    dsts = [d for _, d in moves]
    dupes = {d for d in dsts if dsts.count(d) > 1}
    if dupes:
        print(f"  !! {len(dupes)} NAME COLLISIONS - refusing"); return 1
    for s, d in moves[:4]:
        print(f"    {s.name}\n      -> {d.name}")
    if missing[:3]:
        print("  no title for:", ", ".join(missing[:3]))
    if not apply:
        print("\n  (dry run - pass --apply)")
        return 0
    for s, d in moves:
        s.rename(d)
    print(f"\n  renamed {len(moves)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
