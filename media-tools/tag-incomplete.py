#!/usr/bin/env python3
r"""Colour-tag show folders in Finder by how complete they are.

  RED     under 25% - barely started
  ORANGE  25-99%    - partially downloaded
  (none)  complete  - any existing tag is cleared

Re-runnable: completeness moves as the download queue works, so run it again
whenever you want the tags refreshed.

macOS stores tags in the com.apple.metadata:_kMDItemUserTags extended attribute
as a binary plist of "Name\nColourIndex" strings. Python's os.setxattr is
Linux-only, so this shells out to /usr/bin/xattr. Spotlight may take a minute to
catch up, but Finder reads the attribute directly and shows the dot at once.

    python3 _tools/tag-incomplete.py           # show what it would do
    python3 _tools/tag-incomplete.py --apply
"""
from __future__ import annotations
import json, plistlib, re, subprocess, sys
from pathlib import Path

ROOT = Path("/Users/briantang/Downloads/Converted")
ATTR = "com.apple.metadata:_kMDItemUserTags"
RED, ORANGE = "Red\n6", "Orange\n7"

def find_dir(name: str) -> Path | None:
    d = ROOT / name
    if d.is_dir():
        return d
    for chan in sorted(ROOT.iterdir()):
        if chan.is_dir() and not chan.name.startswith("_") and (chan / name).is_dir():
            return chan / name
    return None

def set_tags(path: Path, tags: list[str]) -> None:
    if tags:
        blob = plistlib.dumps(tags, fmt=plistlib.FMT_BINARY).hex()
        subprocess.run(["xattr", "-w", "-x", ATTR, blob, str(path)], check=False)
    else:
        subprocess.run(["xattr", "-d", ATTR, str(path)],
                       check=False, stderr=subprocess.DEVNULL)

SEASONISH = re.compile(r"^(Season \d+|Movies|Temporada \d+|_.*)$")
FEW = 5          # an untracked show with this many episodes or fewer is a stub


def is_show(d: Path) -> bool:
    """A show folder holds episodes, or Season/Movies subfolders."""
    if any(d.glob("*.mp4")):
        return True
    return any(SEASONISH.match(c.name) for c in d.iterdir() if c.is_dir())


def episodes(d: Path) -> int:
    """Real episodes only - never the working folders."""
    return len([p for p in d.rglob("*.mp4")
                if not any(x.startswith("_") for x in p.relative_to(d).parts)])


def main() -> int:
    apply = "--apply" in sys.argv
    shows = json.loads((ROOT / "_tools" / "shows.json").read_text())

    # Every show folder on disk, whether or not shows.json knows about it. Most
    # of the library predates the registry, so tagging only registered shows
    # would leave 30-odd folders unjudged.
    found = []
    for chan in sorted(ROOT.iterdir()):
        if not chan.is_dir() or chan.name.startswith((".", "_")):
            continue
        if is_show(chan):
            found.append((None, chan))
            continue
        for sub in sorted(chan.iterdir()):
            if sub.is_dir() and not sub.name.startswith("_") and is_show(sub):
                found.append((chan, sub))

    per_channel = {}
    rows = []
    for chan, d in found:
        n = episodes(d)
        meta = shows.get(d.name)
        if meta and meta.get("videos"):
            tgt = meta["videos"]
            pct = n / tgt
            tag = RED if pct < 0.25 else (ORANGE if pct < 1.0 else None)
            why = f"{n}/{tgt}  {pct*100:3.0f}%"
        else:
            # no target recorded - judge on absolute count instead
            tgt, pct = 0, 1.0
            tag = RED if n <= FEW else None
            why = f"{n} eps (untracked)"
        rows.append((tag, d, chan, why))
        if chan is not None and tag is not None:
            cur = per_channel.get(chan)
            per_channel[chan] = RED if RED in (cur, tag) else ORANGE

    order = {RED: 0, ORANGE: 1, None: 2}
    rows.sort(key=lambda r: (order[r[0]], str(r[1])))
    print("  === SHOW folders ===")
    for tag, d, chan, why in rows:
        if tag is None:
            continue
        label = "RED" if tag == RED else "ORANGE"
        print(f"  {label:7s} {str(d)[:52]:54s} {why}")
        if apply:
            set_tags(d, [tag])
    if apply:
        for tag, d, chan, why in rows:
            if tag is None:
                set_tags(d, [])

    print(f"\n  === CHANNEL folders with an incomplete show ({len(per_channel)}) ===")
    for chan in sorted(ROOT.iterdir()):
        if not chan.is_dir() or chan.name.startswith((".", "_")) or is_show(chan):
            continue
        tag = per_channel.get(chan)
        if tag:
            bad = sum(1 for t, d, c, w in rows if c == chan and t is not None)
            print(f"  {'RED' if tag == RED else 'ORANGE':7s} {chan.name:22s} {bad} incomplete show(s)")
        if apply:
            set_tags(chan, [tag] if tag else [])
    if not apply:
        print("\n  (dry run - pass --apply)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
