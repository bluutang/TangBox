#!/usr/bin/env python3
r"""Find episode starts by looking for the near-white title card.

Groups B and C of the Jorge repair are DETECTION failures, not seek failures, so
re-encoding cannot help them: the cut is at the wrong boundary and re-encoding
would only place a wrong cut precisely. This finds the right boundary by
measuring rather than reasoning - the mistake made twice on 2026-08-28.

The method is the one that worked when contact sheets misled: average pixel
colour. Calibrated on Jorge 006, where the answer was already known:

    yellow end credits   RGB 159,153, 62   <- blue channel collapses
    near-white title     RGB 236,236,237   <- all three channels high

So "all three channels above THRESH, held for at least MINLEN seconds" is a
title card, and a title card is where an episode starts.

    python3 _tools/find-title-cards.py FILE                 # whole file
    python3 _tools/find-title-cards.py FILE --from 1200 --to 1500

Sampling is one ffmpeg decode pass at FPS samples/sec, so a window costs far
less than a full blackdetect scan.
"""
from __future__ import annotations
import argparse, subprocess, sys
from pathlib import Path


def hms(s: float) -> str:
    return f"{int(s // 60):d}:{s % 60:05.2f}"


def sample(path: Path, t0: float, dur: float | None, fps: float):
    """Average colour of the frame, fps times a second. Returns [(t, r, g, b)].

    -ss goes BEFORE -i on purpose: this is a coarse survey and the speed matters
    far more than the ~keyframe of positioning error. Every timestamp it reports
    is therefore approximate; refine() re-measures accurately before answering.
    """
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error"]
    if t0:
        cmd += ["-ss", f"{t0:.3f}"]
    cmd += ["-i", str(path)]
    if dur is not None:
        cmd += ["-t", f"{dur:.3f}"]
    cmd += ["-vf", f"fps={fps},scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    return [(t0 + i / fps, raw[i * 3], raw[i * 3 + 1], raw[i * 3 + 2])
            for i in range(len(raw) // 3)]


def refine(path: Path, approx: float, thresh: int, window: float = 6.0):
    """Re-measure around a coarse hit with a frame-accurate seek (-ss AFTER -i)
    and return the first instant that is actually near-white."""
    t0 = max(0.0, approx - window / 2)
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path),
           "-ss", f"{t0:.3f}", "-t", f"{window:.3f}",
           "-vf", "fps=10,scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    for i in range(len(raw) // 3):
        r, g, b = raw[i * 3], raw[i * 3 + 1], raw[i * 3 + 2]
        if min(r, g, b) > thresh:
            return t0 + i / 10.0
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file", type=Path)
    ap.add_argument("--from", dest="t0", type=float, default=0.0)
    ap.add_argument("--to", dest="t1", type=float, default=None)
    ap.add_argument("--fps", type=float, default=2.0, help="coarse samples per second")
    ap.add_argument("--thresh", type=int, default=180,
                    help="every channel must exceed this to count as near-white")
    ap.add_argument("--minlen", type=float, default=1.0,
                    help="seconds the card must hold, to reject a stray bright frame")
    args = ap.parse_args()

    if not args.file.exists():
        print(f"no such file: {args.file}", file=sys.stderr)
        return 1

    dur = None if args.t1 is None else args.t1 - args.t0
    pts = sample(args.file, args.t0, dur, args.fps)
    if not pts:
        print("no frames sampled", file=sys.stderr)
        return 1

    # group consecutive near-white samples into runs
    runs, cur = [], []
    for t, r, g, b in pts:
        if min(r, g, b) > args.thresh:
            cur.append((t, r, g, b))
        else:
            if cur:
                runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    runs = [c for c in runs if c[-1][0] - c[0][0] >= args.minlen]

    print(f"{args.file.name}")
    print(f"  sampled {len(pts)} frames at {args.fps}/s "
          f"from {hms(args.t0)}{'' if args.t1 is None else ' to ' + hms(args.t1)}")
    if not runs:
        print(f"  NO title card found (nothing held all channels > {args.thresh} "
              f"for {args.minlen}s)")
        return 0
    print(f"  {len(runs)} title card(s):")
    for c in runs:
        exact = refine(args.file, c[0][0], args.thresh)
        r, g, b = c[0][1], c[0][2], c[0][3]
        shown = hms(exact) if exact is not None else hms(c[0][0]) + " (coarse)"
        print(f"    starts {shown}   holds {c[-1][0] - c[0][0]:5.1f}s   RGB {r},{g},{b}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
