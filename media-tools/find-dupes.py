#!/usr/bin/env python3
r"""Find episodes that already exist inside a show's long compilations.

Filenames are useless here: the compilations are THEMED ("¡Juguemos en el
parque!"), so nothing in the name says which episodes are inside. The content has
to be compared directly.

Method is the one that worked on Jorge, where files 012 and 013 turned out to
share an 11-minute story: reduce each video to one average colour per sampled
second, then slide the episode's signature along the compilation's and look for a
window where they line up. Average colour survives re-encoding and small
resolution differences, which a hash of the raw bytes would not.

A match is reported only when the mean per-sample difference is small AND the
match is clearly better than the file's typical alignment - a compilation of the
same show has a broadly similar palette throughout, so an absolute threshold
alone would flag everything.

    python3 _tools/find-dupes.py "Daniel Tigre"
"""
from __future__ import annotations
import subprocess, sys
from pathlib import Path

ROOT = Path("/Users/briantang/Downloads/Converted")
FPS = 0.5          # one sample every 2 seconds

def signature(path: Path) -> list[tuple[int, int, int]]:
    raw = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path),
         "-vf", f"fps={FPS},scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True).stdout
    return [(raw[i*3], raw[i*3+1], raw[i*3+2]) for i in range(len(raw)//3)]

def best_offset(ep: list, comp: list) -> tuple[float, int]:
    """Lowest mean absolute difference over all alignments, and where."""
    n, m = len(ep), len(comp)
    if n == 0 or m < n:
        return (999.0, -1)
    best, at = 999.0, -1
    step = max(1, n // 60)                      # coarse scan, then refine
    for s in range(0, m - n + 1, step):
        d = sum(abs(ep[i][0]-comp[s+i][0]) + abs(ep[i][1]-comp[s+i][1])
                + abs(ep[i][2]-comp[s+i][2]) for i in range(0, n, 4)) / (len(range(0, n, 4)) * 3)
        if d < best:
            best, at = d, s
    for s in range(max(0, at-step), min(m-n, at+step)+1):
        d = sum(abs(ep[i][0]-comp[s+i][0]) + abs(ep[i][1]-comp[s+i][1])
                + abs(ep[i][2]-comp[s+i][2]) for i in range(n)) / (n * 3)
        if d < best:
            best, at = d, s
    return best, at

def main() -> int:
    show = ROOT / sys.argv[1]
    filed = sorted(p for p in show.rglob("*.mp4")
                   if not any(x.startswith("_") for x in p.relative_to(show).parts))
    comps = sorted((show / "_staging").glob("*.mp4"))
    print(f"  {len(filed)} filed episodes vs {len(comps)} compilations", flush=True)

    print("  fingerprinting compilations...", flush=True)
    csig = {c: signature(c) for c in comps}
    print("  fingerprinting episodes...", flush=True)
    hits = 0
    for ep in filed:
        es = signature(ep)
        if not es:
            continue
        found = []
        for c in comps:
            d, at = best_offset(es, csig[c])
            if d < 12:                          # calibrated: identical content sits near 2-6
                found.append((d, at, c))
        if found:
            hits += 1
            d, at, c = sorted(found)[0]
            print(f"    DUPLICATE  {ep.name[:52]:54s}", flush=True)
            print(f"               inside {c.name[:44]:46s} at {at*2//60}:{at*2%60:02d}  (diff {d:.1f})",
                  flush=True)
    print(f"\n  {hits} of {len(filed)} filed episodes also appear in a compilation")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
