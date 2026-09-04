#!/usr/bin/env python3
r"""Cut a file at explicit timestamps, frame-accurately.

detect-breaks.py FINDS boundaries. This one is told them, for when detection got
it wrong and the right answer is already known - Jorge groups B and C, where the
fade detector picked a candidate up to 250 s away from the real episode start.

Always re-encodes. `-c copy` can only start a piece on a keyframe and rounds
BACKWARDS to reach one, silently, by up to ~5 s - which is the whole reason the
group A pieces opened on the previous episode's credits. Re-encoding with -ss
AFTER -i has no keyframe constraint, so the cut lands exactly where asked.

800k is ~2x these files' ~370k source: enough that a second generation of a
YouTube encode does not show, without inventing detail the source never had.

    python3 _tools/cut-at.py FILE --at 1342.30 --outdir _reenc
"""
from __future__ import annotations
import argparse, subprocess, sys
from pathlib import Path


def hms(s: float) -> str:
    return f"{int(s // 3600)}:{int(s % 3600 // 60):02d}:{s % 60:05.2f}"


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout.strip()
    return float(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file", type=Path)
    ap.add_argument("--at", type=float, nargs="+", required=True,
                    help="cut time(s) in seconds")
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--name", help="base name (default: input stem)")
    ap.add_argument("--bitrate", default="800k")
    args = ap.parse_args()

    if not args.file.exists():
        print(f"no such file: {args.file}", file=sys.stderr)
        return 1

    total = duration(args.file)
    bounds = [0.0] + sorted(args.at) + [total]
    args.outdir.mkdir(parents=True, exist_ok=True)
    base = args.name or args.file.stem

    print(f"{args.file.name}  ({hms(total)})")
    for i in range(len(bounds) - 1):
        a, b = bounds[i], bounds[i + 1]
        dst = args.outdir / f"{base} - pt{i + 1:02d}.mp4"
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
               "-i", str(args.file), "-ss", f"{a:.3f}", "-to", f"{b:.3f}",
               "-c:v", "h264_videotoolbox", "-b:v", args.bitrate,
               "-c:a", "aac", "-b:a", "160k", str(dst)]
        subprocess.run(cmd, check=True)
        print(f"  {dst.name}  {hms(a)} -> {hms(b)}  ({hms(b - a)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
