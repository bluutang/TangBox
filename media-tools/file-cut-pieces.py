#!/usr/bin/env python3
r"""File the finished cut/bundled pieces for Daniel Tigre, Dora and Pistas.

file-shows.py cannot do this job: it reads from _staging, expects the show at
the top level (Dora lives in NickJr/), and has no rule for Daniel or Pistas.
Its 45-minute guard is also the thing that caught Dora's 4h26m "episode", so it
is left alone rather than widened.

Numbering: pieces carry on PAST the highest existing episode. These shows number
by DOWNLOAD INDEX, not broadcast order, so the gaps are not real positions - a
gap at Daniel E03 exists BECAUSE source 003 was cut into four. Filling it would
put unrelated video there. (Decided 2026-08-31; the opposite call to Ms. Nenna,
where the gaps genuinely were the episodes' places.)

    python3 _tools/file-cut-pieces.py            # dry run
    python3 _tools/file-cut-pieces.py --apply
"""
from __future__ import annotations
import re, subprocess, sys, unicodedata
from pathlib import Path

ROOT = Path("/Users/briantang/Downloads/Converted")


def find_dir(rel: str) -> Path:
    """Match a folder by NFC-normalised name. 'Pistas de Blue y tu' is stored
    DECOMPOSED on this disk, so a literal path with a precomposed u-acute misses
    it entirely and every glob silently returns nothing."""
    want = unicodedata.normalize("NFC", rel)
    for p in ROOT.rglob("*"):
        if p.is_dir() and unicodedata.normalize("NFC", str(p.relative_to(ROOT))) == want:
            return p
    raise SystemExit(f"  !! folder not found: {rel}")


def minutes(p: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout.strip()
    try:
        return float(out) / 60
    except ValueError:
        return 0.0


def highest_ep(season: Path) -> int:
    hi = 0
    if season.is_dir():
        for f in season.glob("*.mp4"):
            m = re.search(r"S(\d+)E(\d+)", f.name)
            if m:
                hi = max(hi, int(m.group(2)))
    return hi


# ---------------------------------------------------------------- per show ---
def plan_pistas():
    """Already named 'Pistas de Blue y tu - S01E01.mp4'. Pure move, no renumber."""
    show = find_dir("Pistas de Blue y tú")
    src = show / "_bundled"
    moves = [(f, show / "Season 01" / f.name) for f in sorted(src.glob("*.mp4"))]
    return "Pistas de Blue y tú", moves


def plan_daniel(start: int | None = None):
    """Two inputs. _staging holds 17 sources: the 12 that were cut (whose pieces
    are in _reenc) and 5 left whole. The whole ones are found by SUBTRACTION -
    a source with no piece in _reenc was never cut - rather than hardcoded, so
    the script cannot quietly file a source whose pieces went missing."""
    show = find_dir("Daniel Tigre")
    season = show / "Season 01"

    # Aug-29 leftovers: '003-<id> - pt01.mp4' with NO title. Same content as the
    # Aug-31 set at 2670 kbps vs the library's usual ~970. Excluded, not deleted.
    dupe = re.compile(r"^\d{3}-[A-Za-z0-9_-]{11} - pt\d+$")
    piece = re.compile(r"^(\d{3})-([A-Za-z0-9_-]{11}) - (.+) - pt(\d+)$")

    pieces, skipped_dupes = [], []
    for f in sorted((show / "_reenc").glob("*.mp4")):
        if dupe.match(f.stem):
            skipped_dupes.append(f.name); continue
        m = piece.match(f.stem)
        if not m:
            print(f"    ?? unreadable piece name: {f.name}"); continue
        pieces.append((int(m.group(1)), int(m.group(4)), m.group(3), f))
    pieces.sort(key=lambda t: (t[0], t[1]))

    cut_sources = {p[0] for p in pieces}
    whole = []
    for f in sorted((show / "_staging").glob("*.mp4")):
        m = re.match(r"^(\d{3})-[A-Za-z0-9_-]{11} - (.+)$", f.stem)
        if m and int(m.group(1)) not in cut_sources:
            whole.append((int(m.group(1)), m.group(2), f))

    moves = []
    for idx, title, f in whole:                      # keep their own index
        moves.append((f, season / f"Daniel Tigre - S01E{idx:02d} - {title}.mp4"))
    n = start if start is not None else highest_ep(season)
    for _, pt, title, f in pieces:
        n += 1
        moves.append((f, season / f"Daniel Tigre - S01E{n:02d} - {title} - pt{pt:02d}.mp4"))

    print(f"    {len(whole)} whole file(s) keep their own index: "
          f"{', '.join(f'E{i:02d}' for i, _, _ in whole)}")
    print(f"    {len(pieces)} cut piece(s) numbered from E{(start if start is not None else highest_ep(season))+1:02d}")
    if skipped_dupes:
        print(f"    {len(skipped_dupes)} Aug-29 duplicate(s) of 003 LEFT IN _reenc, not filed")
    return "Daniel Tigre", moves


def plan_dora():
    """_reenc names are already 'Dora la Exploradora - S01E02 - <title> - pt01.mp4'
    where 02 is the SOURCE index. Renumber the SxxExx, keep everything else."""
    show = find_dir("NickJr/Dora la Exploradora")
    season = show / "Season 01"
    pat = re.compile(r"^Dora la Exploradora - S(\d+)E(\d+) - (.+) - pt(\d+)$")

    pieces = []
    for f in sorted((show / "_reenc").glob("*.mp4")):
        m = pat.match(f.stem)
        if not m:
            print(f"    ?? unreadable piece name: {f.name}"); continue
        pieces.append((int(m.group(2)), int(m.group(4)), m.group(3), f))
    pieces.sort(key=lambda t: (t[0], t[1]))

    n = highest_ep(season)
    print(f"    {len(pieces)} cut piece(s) numbered from E{n+1}")
    moves = []
    for _, pt, title, f in pieces:
        n += 1
        moves.append((f, season / f"Dora la Exploradora - S01E{n:02d} - {title} - pt{pt:02d}.mp4"))
    return "Dora la Exploradora", moves


# -------------------------------------------------------------------- main ---
def main() -> int:
    apply = "--apply" in sys.argv
    grand = 0
    for planner in (plan_pistas, plan_daniel, plan_dora):
        print(f"\n  === {planner.__name__.replace('plan_', '').upper()} ===")
        name, moves = planner()
        if not moves:
            print("    nothing to file"); continue

        # --- refuse to guess. Every one of these has burned a session before.
        bad = False
        dsts = [d for _, d in moves]
        if len(set(dsts)) != len(dsts):
            print("    !! two files want the same name - SKIPPING SHOW"); bad = True
        for d in dsts:
            if d.exists():
                print(f"    !! destination already exists: {d.name} - SKIPPING SHOW"); bad = True; break

        tin = tout = 0.0
        longest = 0.0
        for s, _ in moves:
            m = minutes(s)
            tin += m
            longest = max(longest, m)
        if longest > 45:
            over = [(s.name, minutes(s)) for s, _ in moves if minutes(s) > 45]
            print(f"    note: {len(over)} file(s) over 45 min (approved 2026-08-31), "
                  f"longest {longest:.1f} min")
        if bad:
            continue

        print(f"    {len(moves)} file(s), {tin/60:.3f} h")
        print(f"    first: {moves[0][1].name[:78]}")
        print(f"    last:  {moves[-1][1].name[:78]}")

        if apply:
            for s, d in moves:
                d.parent.mkdir(parents=True, exist_ok=True)
                s.rename(d)
            for _, d in moves:
                tout += minutes(d)
            gap = abs(tin - tout) * 60
            print(f"    MOVED. in {tin/60:.3f} h -> out {tout/60:.3f} h  (diff {gap:.1f} s)")
            if gap > 2:
                print("    !! DURATION MISMATCH - investigate before trusting this")
        grand += len(moves)

    print(f"\n  total: {grand} file(s) {'filed' if apply else 'to file'}")
    if not apply:
        print("  (dry run - pass --apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
