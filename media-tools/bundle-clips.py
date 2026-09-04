#!/usr/bin/env python3
r"""Bundle Pistas de Blue's short clips into ~22-minute episode blocks.

The show came down as 60 standalone 4-5 minute clips - each with its own title
and story - plus a handful of 30-minute compilations. Nothing in the download is
an episode. Brian's call: bundle the clips into episode-length blocks and leave
the 30-minute ones whole.

Bundling is by PLAYLIST ORDER, which is the uploader's own sequencing, so
related clips stay together rather than being shuffled by duration. A block is
closed once it reaches the target, so blocks land a little over rather than a
little under - a 22-minute target with 5-minute clips gives blocks of ~22-25.

Concatenated with -c copy where the encodes match, which is lossless and takes
seconds. Any clip whose encode differs is bundled separately at the end, since
concat cannot stream-copy across a format change.

    python3 _tools/bundle-clips.py            # dry run
    python3 _tools/bundle-clips.py --apply
"""
from __future__ import annotations
import argparse, re, subprocess, sys, tempfile
from pathlib import Path

# Generalised 2026-08-31 for the two 123 Andrés shows, whose clips are ~2 min
# rather than Pistas' ~5. Defaults are unchanged, so a bare run still does
# exactly what it did for Pistas.
ROOT = Path("/Users/briantang/Downloads/Converted")
SHOW = ROOT / "Pistas de Blue y tú"
TARGET = 22 * 60
MAX_CLIP = 12 * 60          # anything longer is a compilation, left alone


def probe(p: Path):
    v = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=codec_name,width,height,r_frame_rate",
                        "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout.strip()
    d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout.strip()
    return v, (float(d) if d else 0.0)


def main() -> int:
    global SHOW, TARGET, MAX_CLIP
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", help="show folder, relative to Converted/")
    ap.add_argument("--target", type=float, help="block length in minutes")
    ap.add_argument("--max-clip", type=float, help="clips longer than this are left alone")
    ap.add_argument("--no-group", action="store_true",
                    help="bundle in PLAYLIST ORDER even across encode changes. "
                         "Mixed blocks are joined with ffmpeg's concat FILTER, "
                         "which re-times properly; the demuxer cannot.")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if a.show:     SHOW = ROOT / a.show
    if a.target:   TARGET = a.target * 60
    if a.max_clip: MAX_CLIP = a.max_clip * 60
    apply = a.apply
    print(f"  {SHOW.name}: target {TARGET/60:.0f} min, max clip {MAX_CLIP/60:.0f} min")
    stage = SHOW / "_staging"
    clips = []
    for p in sorted(stage.glob("*.mp4")):
        v, d = probe(p)
        if d and d <= MAX_CLIP:
            idx = int(p.name[:3]) if p.name[:3].isdigit() else 999
            clips.append((idx, p, d, v))
    clips.sort()
    # GROUP BY ENCODE FIRST. These clips are identical except for frame rate -
    # 61 at 23.976 and 20 at 25 - and concat cannot stream-copy across that
    # change. Bundling within each group keeps every block lossless; mixing them
    # would have forced a re-encode on 9 of 13 blocks for no gain.
    # 123 Andrés' alphabet playlist is IN ALPHABETICAL ORDER but its 41 clips
    # carry 8 different encodes, interleaved across 20 runs. Grouping by encode
    # would put D, W, X and Z in one block and A, B, C, E in another - which
    # destroys the one thing the ordering was for. --no-group keeps playlist
    # order and pays for it with a re-encode on the mixed blocks.
    groups: dict[str, list] = {}
    if a.no_group:
        groups["(playlist order)"] = clips
    else:
        for c in clips:
            groups.setdefault(c[3], []).append(c)
    print(f"  {len(clips)} clips under {MAX_CLIP//60} min, "
          f"{len(groups)} encode group(s): "
          + ", ".join(f"{len(v)} @ {k.split(',')[-1]}" for k, v in groups.items()))

    blocks = []
    for v, items in groups.items():
        cur, tot = [], 0.0
        for idx, p, d, vv in items:
            cur.append((p, d, vv)); tot += d
            if tot >= TARGET:
                blocks.append((cur, tot)); cur, tot = [], 0.0
        if cur:
            blocks.append((cur, tot))

    print(f"  -> {len(blocks)} blocks\n")
    for i, (items, secs) in enumerate(blocks, 1):
        mixed = len({v for _, _, v in items}) > 1
        print(f"    block {i:02d}  {secs/60:5.1f} min  {len(items)} clips"
              + ("   MIXED ENCODES - will re-encode" if mixed else ""))
    if not apply:
        print("\n  (dry run - pass --apply)")
        return 0

    out = SHOW / "_bundled"; out.mkdir(exist_ok=True)
    for i, (items, secs) in enumerate(blocks, 1):
        dst = out / f"{SHOW.name} - S01E{i:02d}.mp4"
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            for p, _, _ in items:
                # ESCAPE THE APOSTROPHE. The concat list format is file '...',
                # so a path containing ' ends the string early and ffmpeg stops
                # reading the list - silently, exit code 0, valid short file.
                # Three clips here are titled "Blue's Clues & You!" and they are
                # exactly the ones that broke two of the thirteen blocks.
                fh.write("file '%s'\n" % str(p.resolve()).replace("'", r"'\''"))
            lst = fh.name
        mixed = len({v for _, _, v in items}) > 1
        if mixed:
            # CONCAT FILTER, not the demuxer. The demuxer assumes every input
            # shares a timebase; across 23.976/24/29.97/30 it produces drifting
            # audio sync that no duration check would catch. The filter decodes
            # and re-times each input, so the join is correct by construction.
            cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
            for pth, _, _ in items:
                cmd += ["-i", str(pth)]
            n = len(items)
            fc = "".join(f"[{i}:v:0][{i}:a:0]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a]"
            cmd += ["-filter_complex", fc, "-map", "[v]", "-map", "[a]",
                    "-r", "30000/1001",
                    "-c:v", "h264_videotoolbox", "-b:v", "1500k",
                    "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2"]
            subprocess.run(cmd + [str(dst)])
        else:
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                            "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", str(dst)])
        # VERIFY, then re-encode if short. ffmpeg's concat demuxer truncates
        # silently on some inputs: it drops the rest of the list, writes a valid
        # file and exits 0. Two of thirteen blocks lost 4.7 and 14.2 minutes that
        # way, and only duration arithmetic caught it. Re-encoding does not use
        # the demuxer's stream-copy path and gets the whole thing.
        got = probe(dst)[1] if dst.exists() else 0.0
        if abs(got - secs) > 5:
            # WORDING, not logic: the abs() above already catches a block that
            # came out too LONG, but this line used to say "short by" either
            # way, which reads as though only truncation is checked. A block
            # can be over - concat of mixed RESOLUTIONS time-stretches rather
            # than truncating - and calling that "short" hid it in the log.
            how = "short" if got < secs else "LONG"
            print(f"    {how} by {abs(secs-got):.0f}s - re-encoding {dst.name}")
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                            "-f", "concat", "-safe", "0", "-i", lst,
                            "-c:v", "h264_videotoolbox", "-b:v", "1500k",
                            "-c:a", "aac", "-b:a", "160k", str(dst)])
            got = probe(dst)[1] if dst.exists() else 0.0
        Path(lst).unlink(missing_ok=True)
        ok = dst.exists() and abs(got - secs) <= 5
        print(f"    {'ok  ' if ok else 'FAIL'} {dst.name}  {got/60:.1f} min"
              + ("" if ok else f"   WRONG LENGTH (wanted {secs/60:.1f})"))

    # END-TO-END TOTAL, re-probed from disk after every block is written.
    # The per-block check above passes at the moment it runs and cannot know
    # what happens to the file afterwards: an orphaned ffmpeg from an earlier
    # killed run once overwrote finished blocks, so they verified clean and
    # were corrupt minutes later. One Octonautas block ended up 144 minutes
    # from an intended 20 and nothing in this script noticed. Only comparing
    # minutes-in against minutes-out caught it, so that comparison lives here
    # now instead of in somebody's head.
    want = sum(secs for _, secs in blocks)
    have = sum(probe(p)[1] for p in sorted(out.glob("*.mp4")))
    drift = have - want
    print(f"\n  wrote {len(blocks)} blocks to _bundled/ - clips untouched")
    print(f"  minutes in {want/60:.1f}  ->  out {have/60:.1f}"
          f"   {'MATCH' if abs(drift) <= 10 else f'MISMATCH {drift/60:+.1f} min'}")
    if abs(drift) > 10:
        print("  🔴 DO NOT FILE THESE. Check for a stray ffmpeg "
              "(ps -eo command | grep ffmpeg) and rebuild.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
