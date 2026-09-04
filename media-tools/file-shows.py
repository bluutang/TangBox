#!/usr/bin/env python3
r"""Move finished episodes out of _staging into Season folders.

This is the "name" step of  download -> split/join -> name -> file.
organize-channels.py deliberately refuses to move a show while _staging still
holds anything, because the splitting tools look for ROOT/<show>/_staging and
filing early would hide their input. So this has to happen first.

Every show names its files differently, so each gets its own rule. Anything
whose season/episode cannot be read is LEFT ALONE rather than guessed - a wrong
episode number is worse than an unfiled file, which is the lesson from the 246
mis-titled files.

    python3 _tools/file-shows.py            # dry run
    python3 _tools/file-shows.py --apply
"""
from __future__ import annotations
import re, sys, unicodedata
import subprocess
from pathlib import Path

ROOT = Path("/Users/briantang/Downloads/Converted")

# Nothing longer than this files itself. Dora's six "COMPLETOS" marathons - one
# of them 4 hours 26 minutes - were filed into NickJr as single episodes because
# their FILENAMES matched the normal pattern and nothing looked at the runtime.
# A show whose episodes are genuinely this long (Journey to the West at 42-44
# min, the Sailor Moon films at 60) is listed in LONG_OK below.
MAX_EPISODE_MIN = 45.0
LONG_OK = {"Journey to the West", "Sailor Moon", "Aprende Peque con Isa", "Ms. Nenna"}


def minutes(p: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout.strip()
    try:
        return float(out) / 60
    except ValueError:
        return 0.0
BAD = {'"': "'", "*": "+", "/": "-", ":": " -", "<": "(", ">": ")",
       "?": "", "\\": "-", "|": "｜"}

def safe(t: str) -> str:
    t = unicodedata.normalize("NFC", t)
    for k, v in BAD.items():
        t = t.replace(k, v)
    return re.sub(r"\s+", " ", t).strip(" -").rstrip(".")[:110]

def strip_prefix(stem: str) -> str:
    """Drop the download bookkeeping: '007-AbCdEf12345 - Real Title'."""
    m = re.match(r"^\d{3}-[A-Za-z0-9_-]{11}\s*-\s*(.+)$", stem)
    return m.group(1) if m else stem

# ---- per-show rules: return (season, episode, title) or None to skip ---------
def r_sxxexx(stem):                       # Rocket Power, Street Sharks
    m = re.search(r"S(\d+)E(\d+)", stem, re.I)
    if not m: return None
    rest = re.sub(r"^.*?S\d+E\d+[\s-]*", "", strip_prefix(stem), flags=re.I)
    rest = re.sub(r"^.*?\bS\d+E\d+\b", "", rest, flags=re.I)
    return int(m.group(1)), int(m.group(2)), safe(rest)

def r_arthur(stem):                       # "Arthur T01E23"
    m = re.search(r"T(\d+)E(\d+)", stem, re.I)
    return (int(m.group(1)), int(m.group(2)), "") if m else None

def r_dbz(stem):                          # "... - Episode 001"
    m = re.search(r"Episode\s+(\d+)", stem, re.I)
    return (1, int(m.group(1)), "") if m else None

def r_bear(stem):                         # "102. Water, Water Everywhere"
    m = re.match(r"^(\d)(\d\d)\.\s*(.*)$", stem)
    if not m: return None
    return int(m.group(1)), int(m.group(2)), safe(m.group(3))

def r_plain(stem):                        # "01"
    m = re.match(r"^(\d+)$", stem.strip())
    return (1, int(m.group(1)), "") if m else None

def r_index_title(stem):                  # "007-AbCdEf12345 - Some Title"
    m = re.match(r"^(\d{3})-[A-Za-z0-9_-]{11}\s*-\s*(.+)$", stem)
    return (1, int(m.group(1)), safe(m.group(2))) if m else None

def r_gargoyles(stem):
    """archive.org stores these as "Gargolas/CapGarg41.mp4"; get-archive.py's
    exFAT sanitiser turns the "/" into "-", so the stem is "Gargolas-CapGarg41".
    The source numbers 1-78 straight through with no season breaks, so they are
    kept that way rather than split on season boundaries I would have to invent."""
    m = re.search(r"CapGarg(\d+)", stem, re.I)
    return (1, int(m.group(1)), "") if m else None


_ROLIE = {"n": 0}
def r_rolie(stem):
    """The cut pieces are "001 - pt02"; numbering runs sequentially across all
    eight compilations, since these are ~22-minute episodes with no broadcast
    numbers to honour."""
    if not re.match(r"^\d{3} - pt\d+$", stem):
        return None
    _ROLIE["n"] += 1
    return (1, _ROLIE["n"], "")


RULES = {
    "Gargoyles": r_gargoyles,
    "Rolie Polie Olie": r_rolie,
    "Rocket Power": r_sxxexx, "Street Sharks": r_sxxexx,
    "Arthur": r_arthur, "Dragon Ball Z": r_dbz,
    "Bear in the Big Blue House": r_bear,
    "Journey to the West": r_plain,
    "Uncle Calvin": r_index_title, "Aprende Peque con Isa": r_index_title,
    "Clifford": r_index_title, "El Autobús Mágico": r_index_title,
    "Cosmic Kids Yoga": r_index_title, "Spanish Basics": r_index_title,
    "Dora la Exploradora": r_index_title,
}

def main() -> int:
    apply = "--apply" in sys.argv
    grand = skipped_total = 0
    for show, rule in RULES.items():
        base = ROOT / show
        stage = base / "_staging"
        if not stage.is_dir():
            continue
        files = sorted(stage.glob("*.mp4"))
        if not files:
            continue
        moves, skipped = [], []
        toolong = []
        for p in files:
            if show not in LONG_OK:
                m = minutes(p)
                if m > MAX_EPISODE_MIN:
                    toolong.append((p.name, m)); continue
            got = rule(p.stem)
            if not got:
                skipped.append(p.name); continue
            s, e, title = got
            name = f"{show} - S{s:02d}E{e:02d}" + (f" - {title}" if title else "") + ".mp4"
            moves.append((p, base / f"Season {s:02d}" / name))
        dsts = [d for _, d in moves]
        dupes = {d for d in dsts if dsts.count(d) > 1}
        flag = f"  !! {len(dupes)} COLLISIONS - skipping this show" if dupes else ""
        print(f"  {show[:32]:34s} {len(moves):4d} to file, {len(skipped):3d} unreadable, "
              f"{len(toolong):2d} too long{flag}")
        for n, m in toolong[:3]:
            print(f"      HELD {m:6.1f} min  {n[:58]}  (needs splitting first)")
        if moves and not dupes:
            print(f"      e.g. {moves[0][1].parent.name}/{moves[0][1].name[:64]}")
        if skipped[:2]:
            print(f"      skipped e.g. {skipped[0][:60]}")
        if dupes:
            continue
        grand += len(moves); skipped_total += len(skipped)
        if apply:
            for s_, d in moves:
                d.parent.mkdir(parents=True, exist_ok=True)
                if not d.exists():
                    s_.rename(d)
    print(f"\n  total: {grand} to file, {skipped_total} left in _staging")
    if not apply:
        print("  (dry run - pass --apply)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
