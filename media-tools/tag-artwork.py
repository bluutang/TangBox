#!/usr/bin/env python3
r"""Colour-tag folders whose show has no tile picture yet.

The guide draws one tile per channel and the picture comes from the playing
show's `tile.jpg` (or `.png`) - `<channel>/<show>/tile.jpg`. Neither child in
this house can read, so that picture is the whole tile to them: a show without
one is a blank on the dial.

PURPLE = no artwork. This ADDS to whatever tag the folder already carries, so a
show that is both incomplete and unillustrated shows red and purple rather than
losing one of them. A channel is tagged if any show inside it is missing one.

    python3 _tools/tag-artwork.py            # dry run
    python3 _tools/tag-artwork.py --apply
"""
from __future__ import annotations
import plistlib, re, subprocess, sys
from pathlib import Path

ROOT = Path("/Users/briantang/Downloads/Converted")
ATTR = "com.apple.metadata:_kMDItemUserTags"
PURPLE = "Purple\n3"
SEASONISH = re.compile(r"^(Season \d+|Movies|Temporada \d+|_.*)$")


def is_show(d: Path) -> bool:
    if any(d.glob("*.mp4")):
        return True
    return any(SEASONISH.match(c.name) for c in d.iterdir() if c.is_dir())


def get_tags(path: Path) -> list[str]:
    out = subprocess.run(["xattr", "-p", "-x", ATTR, str(path)],
                         capture_output=True, text=True)
    if out.returncode != 0 or not out.stdout.strip():
        return []
    try:
        return plistlib.loads(bytes.fromhex(out.stdout.replace(" ", "").replace("\n", "")))
    except Exception:
        return []


def set_tags(path: Path, tags: list[str]) -> None:
    if tags:
        blob = plistlib.dumps(tags, fmt=plistlib.FMT_BINARY).hex()
        subprocess.run(["xattr", "-w", "-x", ATTR, blob, str(path)], check=False)
    else:
        subprocess.run(["xattr", "-d", ATTR, str(path)],
                       check=False, stderr=subprocess.DEVNULL)


def has_art(d: Path) -> bool:
    return (d / "tile.jpg").exists() or (d / "tile.png").exists()


def main() -> int:
    apply = "--apply" in sys.argv
    missing, ok, chan_missing = [], [], {}
    for chan in sorted(ROOT.iterdir()):
        if not chan.is_dir() or chan.name.startswith((".", "_")):
            continue
        shows = [chan] if is_show(chan) else [
            s for s in sorted(chan.iterdir())
            if s.is_dir() and not s.name.startswith("_") and is_show(s)]
        for s in shows:
            (ok if has_art(s) else missing).append(s)
            if not has_art(s) and s is not chan:
                chan_missing.setdefault(chan, []).append(s)

    print(f"  {len(ok)} shows have artwork, {len(missing)} do not\n")
    print("  === SHOWS with no tile ===")
    for s in missing:
        print(f"    {s}")
        if apply:
            t = [x for x in get_tags(s) if not x.startswith("Purple")]
            set_tags(s, t + [PURPLE])
    if apply:                                   # clear purple from any that now have one
        for s in ok:
            t = get_tags(s)
            if any(x.startswith("Purple") for x in t):
                set_tags(s, [x for x in t if not x.startswith("Purple")])

    print(f"\n  === CHANNELS containing a show with no tile ({len(chan_missing)}) ===")
    for chan in sorted(ROOT.iterdir()):
        if not chan.is_dir() or chan.name.startswith((".", "_")) or is_show(chan):
            continue
        n = len(chan_missing.get(chan, []))
        if n:
            print(f"    {chan.name:22s} {n} show(s)")
        if apply:
            t = [x for x in get_tags(chan) if not x.startswith("Purple")]
            set_tags(chan, t + [PURPLE] if n else t)
    if not apply:
        print("\n  (dry run - pass --apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
