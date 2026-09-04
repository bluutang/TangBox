#!/usr/bin/env python3
r"""Reorganise Sailor Moon into one show with real seasons, plus the films.

Five season playlists were downloaded into ONE folder, so their playlist indices
collide - "001-" appears five times, once per season - and the only thing that
tells the seasons apart is the video id.

The mapping is taken from the PLAYLISTS THEMSELVES (_tools/sailor-seasons.json,
written by a --flat-playlist query), not from the download log. The log looked
usable but its segment boundaries bleed: it yielded 210 ids for 200 files, which
would have put episodes in the wrong season. That is the same failure mode as the
looked-up episode titles that had to be stripped from 246 files.

    python3 _tools/sailor-seasons.py            # dry run, prints the whole plan
    python3 _tools/sailor-seasons.py --apply
"""
from __future__ import annotations
import json, re, sys, unicodedata
from pathlib import Path

ROOT = Path("/Users/briantang/Downloads/Converted")
SHOW = ROOT / "Sailor Moon"
FILMS = ROOT / "Sailor Moon Películas"
MAP = ROOT / "_tools" / "sailor-seasons.json"
SEASON_NO = {"Primera Temporada": 1, "R": 2, "S": 3, "Super S": 4, "Sailor Stars": 5}

# exFAT rejects  " * / : < > ? \ |  - and the USB drive is exFAT. Replace the
# pipe with the FULLWIDTH form already used elsewhere in the library; drop the
# rest. Never silently truncate: a lost character makes two episodes collide.
BAD = {'"': "'", "*": "+", "/": "-", ":": " -", "<": "(", ">": ")",
       "?": "", "\\": "-", "|": "｜"}

def safe(t: str) -> str:
    t = unicodedata.normalize("NFC", t)
    for k, v in BAD.items():
        t = t.replace(k, v)
    t = re.sub(r"\s+", " ", t).strip().rstrip(".")
    return t[:120]

def main() -> int:
    apply = "--apply" in sys.argv
    seasons = json.loads(MAP.read_text())
    # id -> (season number, episode number, title)
    where: dict[str, tuple[int, int, str]] = {}
    for name, rows in seasons.items():
        n = SEASON_NO[name]
        for i, row in enumerate(rows, 1):
            vid, _, title = row.partition("|")
            where[vid] = (n, i, title)

    staged = sorted(p for p in (SHOW / "_staging").glob("*.mp4"))
    moves, unmapped = [], []
    for p in staged:
        m = re.match(r"^\d{3}-([A-Za-z0-9_-]{11})\.mp4$", p.name) or \
            re.match(r"^([A-Za-z0-9_-]{11})-", p.name)
        if not m or m.group(1) not in where:
            unmapped.append(p.name); continue
        s, e, title = where[m.group(1)]
        dst = SHOW / f"Season {s:02d}" / f"Sailor Moon - S{s:02d}E{e:02d} - {safe(title)}.mp4"
        moves.append((p, dst))

    # the two films go alongside the seasons, in their own folder
    for p in sorted(FILMS.glob("_staging/*.mp4")):
        moves.append((p, SHOW / "Movies" / f"Sailor Moon - {p.stem}.mp4"))

    print(f"{len(moves)} files to move, {len(unmapped)} unmapped")
    if unmapped:
        print("  UNMAPPED (left alone):")
        for u in unmapped[:10]: print("   ", u)
    per = {}
    for _, d in moves: per[d.parent.name] = per.get(d.parent.name, 0) + 1
    for k in sorted(per): print(f"  {k}: {per[k]} files")

    # a collision would silently destroy an episode - refuse before touching disk
    dsts = [d for _, d in moves]
    dupes = {d for d in dsts if dsts.count(d) > 1}
    if dupes:
        print(f"\n  !! {len(dupes)} DESTINATION COLLISIONS - refusing to move")
        for d in list(dupes)[:5]: print("    ", d.name)
        return 1

    print("\n  sample:")
    for s, d in moves[:4]:
        print(f"    {s.name}\n      -> {d.parent.name}/{d.name}")
    if not apply:
        print("\n  (dry run - pass --apply to move)")
        return 0
    for s, d in moves:
        d.parent.mkdir(parents=True, exist_ok=True)
        s.rename(d)
    print(f"\n  moved {len(moves)} files")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
