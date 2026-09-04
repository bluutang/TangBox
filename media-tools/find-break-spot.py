#!/usr/bin/env python3
r"""Find a good place to drop a commercial break inside a long episode.

Barney's compilations carry no boundary markers at all - two black frames in an
85-minute file, no credit roll, and the average colour either side of a known
episode boundary is identical. So the usual signals are useless here.

What IS available is how television itself decides: a break goes where the
picture cuts AND the sound drops. So this scores candidate moments on two
independent signals near the middle of the piece:

  * a scene change, from ffmpeg's `select=gt(scene,...)` - the picture changing
    wholesale rather than panning
  * a silence, from `silencedetect` - dialogue and music having stopped

A moment with both is a natural act break. One with only a scene change is a
plain cut mid-conversation, which is where a break would feel wrong.

    python3 _tools/find-break-spot.py FILE START END
"""
from __future__ import annotations
import re, subprocess, sys


def hms(s: float) -> str:
    return f"{int(s//3600)}:{int(s%3600//60):02d}:{int(s%60):02d}"


def scenes(path: str, start: float, span: float) -> list[float]:
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-ss", f"{start}", "-i", path,
         "-t", f"{span}", "-vf", "select='gt(scene,0.35)',showinfo",
         "-an", "-f", "null", "-"], capture_output=True, text=True)
    return [start + float(m) for m in
            re.findall(r"pts_time:([\d.]+)", r.stderr)]


def silences(path: str, start: float, span: float) -> list[tuple[float, float]]:
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-ss", f"{start}", "-i", path,
         "-t", f"{span}", "-af", "silencedetect=noise=-32dB:d=0.4",
         "-vn", "-f", "null", "-"], capture_output=True, text=True)
    outs, res = [], []
    for m in re.finditer(r"silence_start: ([\d.]+)", r.stderr):
        outs.append(start + float(m.group(1)))
    for i, m in enumerate(re.finditer(r"silence_end: ([\d.]+)", r.stderr)):
        if i < len(outs):
            res.append((outs[i], start + float(m.group(1))))
    return res


def main() -> int:
    path, a, z = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
    mid = (a + z) / 2
    win = min(300.0, (z - a) / 4)          # look within a few minutes of centre
    start, span = mid - win, win * 2
    sc = scenes(path, start, span)
    si = silences(path, start, span)
    print(f"  window {hms(start)} - {hms(start+span)}   midpoint {hms(mid)}")
    print(f"  {len(sc)} scene changes, {len(si)} silences")

    best = []
    for t in sc:
        near = [s for s in si if s[0] - 1.5 <= t <= s[1] + 1.5]
        if near:
            best.append((abs(t - mid), t, near[0]))
    if not best:
        print("  no scene change coincides with a silence - falling back to the")
        print("  scene change nearest the midpoint (a harder cut, but still a cut)")
        if not sc:
            print("  NOTHING FOUND"); return 1
        t = min(sc, key=lambda x: abs(x - mid))
        print(f"  SUGGEST {hms(t)}   ({t:.1f}s)  scene change only")
        return 0
    best.sort()
    for d, t, sil in best[:3]:
        print(f"    {hms(t)}  scene change inside a {sil[1]-sil[0]:.1f}s silence"
              f"   ({d:.0f}s from centre)")
    d, t, sil = best[0]
    print(f"  SUGGEST {hms(t)}   ({t:.1f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
