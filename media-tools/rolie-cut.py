#!/usr/bin/env python3
r"""Cut Rolie Polie Olie's 8 compilations at Brian's marked timemarks.

The marks are EPISODE boundaries (~22.6 min), not the 7.52-minute segment grid I
measured - each episode is three segments, and 22.6 = 3 x 7.52 exactly, so the
two agree.

Two cuts were added after checking the arithmetic against real black gaps:
  Vol 5  1:08:37  - a measured gap 3.3s from the predicted boundary; without it
                    the tail was a single 30.5-minute piece
  Vol 8  1:31:11  - a measured gap; 1:08:25 -> 1:31:11 is 22.8 min, an episode

Vol 6 has 15 seconds of filler at 1:08:51 that Brian asked to discard, so that
piece is cut out and deleted rather than kept.

Re-encoded, not stream-copied: -c copy can only start a piece on a keyframe and
rounds BACKWARDS to reach one, by up to ~5s, which is what put the previous
episode's credits on the front of Jorge's pieces.

    python3 _tools/rolie-cut.py            # dry run
    python3 _tools/rolie-cut.py --apply
"""
from __future__ import annotations
import subprocess, sys
from pathlib import Path

SHOW = Path("/Users/briantang/Downloads/Converted/Rolie Polie Olie")
CUTS = {
    "001": [1414],
    "002": [1415],
    "003": [1375, 2764],
    "004": [1355, 2963],
    "005": [1413, 2767, 4117],                       # 4117 = 1:08:37, added
    "006": [1413, 2765, 4131, 4146, 5522, 6875],
    "007": [1414, 2767, 4119],
    "008": [1413, 2767, 4105, 5471],                 # 5471 = 1:31:11, added
}
DISCARD = {"006": {3}}          # 0-based piece index: the 15s of filler

def hms(s): return f"{int(s//60)}:{s%60:05.2f}"

def main() -> int:
    apply = "--apply" in sys.argv
    out = SHOW / "_reenc"
    n_keep = 0
    for key in sorted(CUTS):
        src = sorted((SHOW / "_staging").glob(f"{key}-*.mp4"))[0]
        dur = float(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(src)], capture_output=True, text=True).stdout)
        bounds = [0.0] + CUTS[key] + [dur]
        print(f"  {key}  {dur/60:.1f} min")
        ep = 0
        for i in range(len(bounds) - 1):
            a, b = bounds[i], bounds[i + 1]
            if i in DISCARD.get(key, set()):
                print(f"      skip  {hms(a)} -> {hms(b)}   {(b-a)/60:4.1f} min  (filler)")
                continue
            ep += 1
            n_keep += 1
            dst = out / f"{key} - pt{ep:02d}.mp4"
            print(f"      {dst.name}  {hms(a)} -> {hms(b)}   {(b-a)/60:4.1f} min")
            if apply:
                dst.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                                "-i", str(src), "-ss", f"{a:.3f}", "-to", f"{b:.3f}",
                                "-c:v", "h264_videotoolbox", "-b:v", "1200k",
                                "-c:a", "aac", "-b:a", "160k", str(dst)], check=True)
    print(f"\n  {n_keep} episodes" + ("" if apply else "   (dry run - pass --apply)"))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
