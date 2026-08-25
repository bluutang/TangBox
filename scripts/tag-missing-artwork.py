#!/usr/bin/env python3
"""Tag show folders that still need a tile.jpg, in Finder.

The channel guide draws a picture per show, found at
``<channel>/<show>/tile.jpg``. Neither child in this house can read, so that
picture is the only part of a tile they can use - which makes "which shows
still have none" a thing worth seeing at a glance in Finder rather than
counting by hand.

Run it whenever. It is a SYNC, not a one-off stamp: folders without artwork
get the tag, folders that have since gained a tile lose it again. So the
orange folders in Finder are always exactly the work left.

    python3 scripts/tag-missing-artwork.py [LIBRARY_DIR]

Defaults to ~/Downloads/Converted. macOS only - Finder tags are an extended
attribute that nothing else reads.
"""
from __future__ import annotations

import plistlib
import subprocess
import sys
from pathlib import Path

# Finder stores tags as "Name\n<colour index>". 0 none, 1 grey, 2 green,
# 3 purple, 4 blue, 5 yellow, 6 red, 7 orange.
TAG = "Orange\n7"
TAG_NAME = "Orange"
XATTR_KEY = "com.apple.metadata:_kMDItemUserTags"

TILE_NAMES = ("tile.jpg", "tile.png")
SKIP = {"_commercials"}


def read_tags(path: Path) -> list[str]:
    out = subprocess.run(
        ["xattr", "-p", "-x", XATTR_KEY, str(path)],
        capture_output=True, text=True,
    )
    if out.returncode != 0 or not out.stdout.strip():
        return []
    try:
        raw = bytes.fromhex(out.stdout.replace("\n", "").replace(" ", ""))
        return list(plistlib.loads(raw))
    except Exception:
        return []


def write_tags(path: Path, tags: list[str]) -> None:
    if not tags:
        subprocess.run(
            ["xattr", "-d", XATTR_KEY, str(path)],
            capture_output=True, text=True,
        )
        return
    blob = plistlib.dumps(tags, fmt=plistlib.FMT_BINARY)
    subprocess.run(
        ["xattr", "-w", "-x", XATTR_KEY, blob.hex(), str(path)],
        check=True, capture_output=True,
    )


def has_artwork(show: Path) -> bool:
    return any((show / name).is_file() for name in TILE_NAMES)


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else
                Path.home() / "Downloads" / "Converted")
    if not root.is_dir():
        print(f"no such library: {root}", file=sys.stderr)
        return 1

    tagged, cleared, already, fine = [], [], 0, 0
    for show in sorted(p for p in root.iterdir() if p.is_dir()):
        if show.name in SKIP:
            continue
        tags = read_tags(show)
        marked = TAG_NAME in tags or TAG in tags

        if has_artwork(show):
            fine += 1
            if marked:
                write_tags(show, [t for t in tags
                                  if t not in (TAG, TAG_NAME)])
                cleared.append(show.name)
        elif marked:
            already += 1
        else:
            write_tags(show, tags + [TAG])
            tagged.append(show.name)

    print(f"{fine} show(s) have artwork, {len(tagged) + already} still need it")
    for name in tagged:
        print(f"  tagged   {name}")
    for name in cleared:
        print(f"  cleared  {name}  (artwork added)")
    if already:
        print(f"  ({already} already tagged)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
