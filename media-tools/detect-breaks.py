#!/usr/bin/env python3
"""Find episode boundaries inside a compilation video, and optionally cut it.

These YouTube compilations join several self-contained episodes end to end.
A join almost always shows up as a fade to black AND a drop to silence at the
same moment; a cut *within* an episode has one or the other, rarely both. So we
run one ffmpeg pass that reports both, then keep only the moments where they
coincide. That "black AND silent" rule is what separates a real episode
boundary from a dramatic pause or a dark scene.

The goal is a 20-25 minute episode, NOT the smallest possible story. Many of
these shows are two 11-minute shorts inside one 22-minute episode, and that is a
perfectly good unit to hand the box - so --min-episode stops the cutting there.
Walking the joins greedily at an 18-minute floor turns a 45-minute compilation
into two ~22 minute episodes and a 4-hour one into ~12, while leaving a genuine
22-minute episode untouched.

  detect                 python3 detect-breaks.py FILE.mp4
  cut into episodes      python3 detect-breaks.py FILE.mp4 --split --outdir DIR

Nothing is written without --split.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

BLACK = re.compile(r"black_start:([\d.]+)\s+black_end:([\d.]+)")
SILENCE_START = re.compile(r"silence_start:\s*(-?[\d.]+)")
SILENCE_END = re.compile(r"silence_end:\s*(-?[\d.]+)")


def hms(s: float) -> str:
    s = int(s)
    return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True,
    )
    return float(out.stdout.strip() or 0)


def scan(path: Path, black_d: float, silence_d: float, noise: str, pix_th: float = 0.10):
    """One ffmpeg pass. Returns (black intervals, silence intervals)."""
    cmd = [
        "ffmpeg", "-hide_banner", "-nostats",
        "-hwaccel", "videotoolbox",
        "-i", str(path),
        "-vf", f"scale=256:-2,blackdetect=d={black_d}:pix_th={pix_th}",
        "-af", f"silencedetect=noise={noise}:d={silence_d}",
        "-f", "null", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    log = proc.stderr

    blacks = [(float(a), float(b)) for a, b in BLACK.findall(log)]

    silences, open_start = [], None
    for line in log.splitlines():
        m = SILENCE_START.search(line)
        if m:
            open_start = float(m.group(1))
            continue
        m = SILENCE_END.search(line)
        if m and open_start is not None:
            silences.append((open_start, float(m.group(1))))
            open_start = None
    if open_start is not None:
        silences.append((open_start, duration(path)))
    return blacks, silences


def refine_past_credits(path: Path, cut: float, window: float = 90.0):
    """Move a cut forward past the credits to the title card that follows.

    The detector fires on the fade that ends a STORY. On Jorge the episode's
    credits and its yellow "next episode soon" cards come AFTER that fade, so
    cutting there hands the previous episode's credits to the next piece.

    The block that follows is strongly coloured - yellow cards, then a near-white
    title card - so the boundary is measurable rather than guessable. We sample
    the average frame colour forward from the cut and move it to the first
    sustained WHITE run, which is the new episode's title card.

    Returns the original cut unchanged when no title card is found, so a file
    that does not follow this pattern is left exactly as it was.
    """
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path),
         "-ss", f"{cut:.3f}", "-t", f"{window:.0f}",
         "-vf", "fps=2,scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, stdin=subprocess.DEVNULL)
    d = out.stdout
    white = [(d[i] > 200 and d[i+1] > 200 and d[i+2] > 200) for i in range(0, len(d) - 2, 3)]
    for i in range(len(white) - 3):
        if all(white[i:i + 3]):          # sustained, not a single bright frame
            return cut + i / 2.0
    return cut


def snap_to_keyframe(path: Path, cut: float, look: float = 12.0) -> float:
    """Move a cut FORWARD to the next keyframe.

    `-c copy` can only start a piece on a keyframe, so ffmpeg silently moves any
    other time to the previous one - backwards, by up to the keyframe interval
    (about 5 s here). That is what put the previous episode's interstitial back
    onto the head of a piece even after the cut point itself was right.

    Handing it a real keyframe removes the guesswork: there is nothing to snap.
    Forward rather than back, because overshooting trims a frame or two off the
    end of the previous episode, while undershooting drags its credits into the
    next one - and the first is invisible where the second is not.
    """
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-skip_frame", "nokey",
         "-show_entries", "frame=best_effort_timestamp_time", "-of", "csv=p=0",
         "-read_intervals", f"{max(0, cut - 1):.2f}%+{look:.0f}", str(path)],
        capture_output=True, text=True, stdin=subprocess.DEVNULL)
    times = []
    for line in out.stdout.splitlines():
        line = line.strip().rstrip(",")
        try:
            times.append(float(line))
        except ValueError:
            pass
    later = [t for t in times if t >= cut]
    return later[0] if later else cut


def candidates(blacks, silences, pad: float = 2.0, black_only: bool = False):
    """Black intervals that overlap a silence -> real episode joins.

    ``black_only`` drops the silence half of the test. Some uploaders fade the
    picture between episodes but run music straight across the join, so the two
    signals never coincide and the strict rule finds nothing but the intro and
    the end credits. Jorge el Curioso is one: its fades sit at 11:05, 22:10,
    33:27 and 44:32 - clean and evenly spaced - while the audio never drops.
    Only safe where the fades are that regular; check the proposed cuts.
    """
    if black_only:
        # Cut at the MIDDLE of the black. Cutting at its end reads better in
        # theory - the whole fade stays with the episode it closes - but it
        # lands between keyframes, and `-c copy` then snaps forward by ~4 s,
        # dropping the start of the next episode onto the end of this one.
        # Measured on Daniel Tigre: midpoint snaps 0.04-0.15 s, fade-end snaps
        # 4.09-4.17 s. The midpoint leaves about a second of the closing fade on
        # the next piece, which is the smaller of the two errors by far.
        return [{"start": b0, "end": b1, "cut": (b0 + b1) / 2,
                 "black": b1 - b0, "silence": 0.0} for b0, b1 in blacks]
    out = []
    for b0, b1 in blacks:
        mid = (b0 + b1) / 2
        for s0, s1 in silences:
            if s0 - pad <= mid <= s1 + pad:
                out.append({"start": b0, "end": b1, "cut": mid,
                            "black": b1 - b0, "silence": s1 - s0})
                break
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file", type=Path)
    ap.add_argument("--min-episode", type=float, default=1080.0,
                    help="never make a piece shorter than this (seconds). Default 18 min: a "
                         "20-25 min episode is a fine final unit even when it is really two "
                         "shorts joined, so we stop cutting there rather than atomising.")
    ap.add_argument("--credits-window", type=float, default=150.0,
                    help="candidates within this many seconds are one join; cut after the last "
                         "(i.e. after the credits roll rather than before it)")
    ap.add_argument("--black-d", type=float, default=0.35)
    ap.add_argument("--pix-th", type=float, default=0.20,
                    help="how dark counts as black, 0-1. Jorge's fades bottom out around "
                         "0.20 and are INVISIBLE at 0.10 - too strict a value finds only "
                         "the intro and the end credits and proposes no cuts at all.")
    ap.add_argument("--silence-d", type=float, default=0.35)
    ap.add_argument("--noise", default="-45dB")
    ap.add_argument("--past-credits", action="store_true",
                    help="move each cut forward to the title card after the credits")
    ap.add_argument("--black-only", action="store_true",
                    help="accept a fade to black without requiring silence too")
    ap.add_argument("--reencode", action="store_true",
                    help="re-encode instead of stream-copying, so the cut lands "
                         "exactly where asked rather than on the nearest keyframe")
    ap.add_argument("--split", action="store_true", help="actually cut the file")
    ap.add_argument("--outdir", type=Path)
    ap.add_argument("--name", help="base name for the pieces (default: input stem)")
    args = ap.parse_args()

    if not args.file.exists():
        print(f"no such file: {args.file}", file=sys.stderr)
        return 1

    total = duration(args.file)
    print(f"{args.file.name}\n  length {hms(total)}   scanning...", flush=True)

    blacks, silences = scan(args.file, args.black_d, args.silence_d, args.noise, args.pix_th)
    cands = candidates(blacks, silences, black_only=args.black_only)

    # An episode does not end at a single black frame. It ends:
    #     ...story... -> BLACK -> credits -> BLACK -> next episode
    # Both of those blacks are black-and-silent, so both look like joins. Cut on
    # the first and every episode inherits the previous one's credits on its
    # head. So: cluster candidates that sit within a credit-roll of each other
    # and keep the LAST of each cluster, which lands the cut after the credits
    # have finished - where a broadcaster would have gone to break.
    clusters = []
    for c in sorted(cands, key=lambda c: c["cut"]):
        if clusters and c["cut"] - clusters[-1][-1]["cut"] <= args.credits_window:
            clusters[-1].append(c)
        else:
            clusters.append([c])
    picked = [grp[-1] for grp in clusters]
    rolled = sum(1 for grp in clusters if len(grp) > 1)

    # Thin out cuts that sit too close together or to either end.
    cuts, last = [], 0.0
    for c in picked:
        if c["cut"] - last >= args.min_episode and total - c["cut"] >= args.min_episode:
            cuts.append(c)
            last = c["cut"]

    print(f"  black intervals {len(blacks)}   silences {len(silences)}"
          f"   coincide {len(cands)}   joins {len(picked)}"
          f"   ({rolled} with a credit roll)   kept {len(cuts)}\n")

    if args.past_credits:
        for c in cuts:
            moved = refine_past_credits(args.file, c["cut"])
            if moved != c["cut"]:
                print(f"  credits: cut {hms(c['cut'])} -> {hms(moved)} "
                      f"(+{moved - c['cut']:.1f}s, to the title card)")
            c["cut"] = moved
        for c in cuts:
            snapped = snap_to_keyframe(args.file, c["cut"])
            if abs(snapped - c["cut"]) > 0.01:
                print(f"  keyframe: {hms(c['cut'])} -> {hms(snapped)} "
                      f"({snapped - c['cut']:+.2f}s, so -c copy cannot drift back)")
            c["cut"] = snapped

    bounds = [0.0] + [c["cut"] for c in cuts] + [total]
    print(f"  would make {len(bounds) - 1} pieces:")
    for i in range(len(bounds) - 1):
        a, b = bounds[i], bounds[i + 1]
        edge = f"  cut at {hms(b)}" if i < len(bounds) - 2 else ""
        print(f"    {i + 1:2d}. {hms(a)} -> {hms(b)}   ({hms(b - a)}){edge}")

    if not args.split:
        print("\n  (detection only - pass --split to cut)")
        return 0

    outdir = args.outdir or args.file.parent / "_split"
    outdir.mkdir(parents=True, exist_ok=True)
    base = args.name or args.file.stem
    print(f"\n  writing to {outdir}")
    for i in range(len(bounds) - 1):
        a, b = bounds[i], bounds[i + 1]
        dst = outdir / f"{base} - pt{i + 1:02d}.mp4"
        if args.reencode:
            # `-c copy` can only START a piece on a keyframe, so ffmpeg moves any
            # other time to the nearest one - up to ~5 s away on these files,
            # which is what leaves the previous episode's credits on the head of
            # the next piece. Re-encoding removes that constraint entirely: the
            # cut lands exactly where the detector put it.
            #
            # `-ss` AFTER `-i` so the seek is frame-accurate, videotoolbox for
            # speed. 800k is ~2x the ~370k source: enough headroom that a second
            # generation of a YouTube encode does not show, without inventing
            # detail the source never had. 2500k was tried first and made the
            # files 5.6x the stream-copied size for no visible gain.
            cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                   "-i", str(args.file), "-ss", f"{a:.3f}", "-to", f"{b:.3f}",
                   "-c:v", "h264_videotoolbox", "-b:v", "800k",
                   "-c:a", "aac", "-b:a", "160k", str(dst)]
        else:
            cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                   "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", str(args.file),
                   "-c", "copy", "-avoid_negative_ts", "make_zero", str(dst)]
        subprocess.run(cmd, check=True)
        print(f"    {dst.name}  ({hms(b - a)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
