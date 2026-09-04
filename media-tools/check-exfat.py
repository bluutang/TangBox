#!/usr/bin/env python3
r"""Check every name under Converted/ against exFAT's rules before copying to USB.

The drive is exFAT (README Part E). exFAT rejects  " * / : < > ? \ |  outright,
plus control characters, and dislikes names that end in a space or a dot. A file
that breaks these cannot be copied at all - better to find them here than to
watch a copy fail partway.

Also reports unicode normalisation: macOS writes accents DECOMPOSED (NFD), which
is what config.pi.yaml warns about for channel `path:` values.
"""
from __future__ import annotations
import sys, unicodedata
from pathlib import Path
from collections import defaultdict

ROOT = Path("/Users/briantang/Downloads/Converted")
ILLEGAL = set('"*:<>?\\|')          # '/' cannot appear in a path component anyway

def main() -> int:
    issues = defaultdict(list)
    files = dirs = 0
    for p in ROOT.rglob("*"):
        name = p.name
        if p.is_dir(): dirs += 1
        else: files += 1
        rel = p.relative_to(ROOT)
        bad = sorted(set(name) & ILLEGAL)
        if bad: issues[f"illegal char {' '.join(repr(c) for c in bad)}"].append(rel)
        if any(ord(c) < 32 for c in name): issues["control character"].append(rel)
        if name != name.rstrip(" ."): issues["ends with space or dot"].append(rel)
        if name != name.lstrip(" "): issues["starts with space"].append(rel)
        if len(name) > 255: issues[f"name over 255 chars"].append(rel)
        if len(str(p)) > 4096: issues["path too long"].append(rel)

    print(f"scanned {files} files and {dirs} folders under {ROOT}\n")
    if not issues:
        print("  NO exFAT problems found - everything here can be copied to the drive.")
    for kind, items in sorted(issues.items()):
        print(f"  {kind}: {len(items)}")
        for i in items[:6]: print(f"      {i}")
        if len(items) > 6: print(f"      ... and {len(items)-6} more")

    # normalisation - affects config `path:` matching, not the box's file scan
    nfd = [p.relative_to(ROOT) for p in ROOT.iterdir()
           if p.is_dir() and unicodedata.normalize("NFC", p.name) != p.name]
    print(f"\n  top-level folders stored DECOMPOSED (NFD): {len(nfd)}")
    for n in nfd: print(f"      {n}")
    print("      (matters only for `path:` values in config.pi.yaml, not playback)")
    return 1 if issues else 0

if __name__ == "__main__":
    raise SystemExit(main())
