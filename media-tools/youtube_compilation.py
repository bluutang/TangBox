#!/usr/bin/env python3
"""Turn YouTube compilation uploads into TangBox-length episodes.

Kids' channels publish the same shorts over and over inside two-hour themed
compilations. Pocoyo's playlist is 88 hours of video holding roughly 245
distinct shorts - a 2.9x duplication factor. Downloading it as-is would give
you the same episode three times over, in files far too long for a channel
that plays one episode per tune-in.

So: download each compilation at 480p H.264, then take the LONGEST RUNS of
consecutive chapters not already used, and cut each run out whole as one
episode. A run is a contiguous slice of the original upload, so the joins
between its segments are the ones the uploader made - untouched, and
therefore incapable of being cut early or late. Only the two ends are cut.

Roughly 60% of episodes come out that way. What is left over is short
fragments stranded between repeats, and those are stitched together to fill
out the rest.

    python3 youtube_compilation.py --state work/state.json --dest OUT --ids ids.txt

Two things make this safe to leave running overnight:

* Every step is stream-copied. Nothing is re-encoded, so the picture is
  bit-for-bit what YouTube served and a 37-video run costs no quality.
* It is resumable. Progress is written to the state file after each video, so
  killing it and starting again picks up where it stopped rather than
  re-downloading what is already cut.

Sources are deleted as soon as they are cut, which is what keeps the peak disk
use near the size of the finished episodes rather than the 7.75 GB of source
that passes through.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

#: A chapter shorter than this is an intro card, not an episode; longer than
#: this is usually the whole compilation mislabelled as one chapter.
MIN_LEN, MAX_LEN = 180, 720

#: Close an episode once it reaches this. The other Netflix Jr shows run
#: 18-22 minutes, so four ~6 minute segments lands in the same place.
TARGET = 1200
#: A contiguous run this long is worth keeping as an episode of its own even
#: though it is under TARGET - better a slightly short episode with no internal
#: cuts than a full-length one stitched from pieces.
FLOOR = 780
#: A trailing bundle shorter than this is dropped rather than aired as a runt.
MIN_BUNDLE = 600

#: 480p H.264 + AAC. Pinned deliberately: YouTube also offers 480p in AV1
#: (format 397) and yt-dlp prefers it, but the Pi 5 has no AV1 hardware
#: decoder and would fall back to software.
FORMAT = ("135+140/bv*[height<=480][vcodec^=avc1]+ba[acodec^=mp4a]"
          "/b[height<=480][vcodec^=avc1]")


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def probe(path: Path) -> dict:
    """Codec parameters that have to agree before clips can be concatenated."""
    out = run(["ffprobe", "-v", "error", "-show_entries",
               "stream=codec_name,width,height,sample_rate,channels",
               "-of", "json", str(path)])
    try:
        streams = json.loads(out.stdout)["streams"]
    except (ValueError, KeyError):
        return {}
    v = next((s for s in streams if s.get("width")), {})
    a = next((s for s in streams if s.get("sample_rate")), {})
    return {"v": v.get("codec_name"), "w": v.get("width"), "h": v.get("height"),
            "a": a.get("codec_name"), "sr": a.get("sample_rate"),
            "ch": a.get("channels")}


#: A segment opens on a near-white title card: essentially unsaturated and
#: very bright. Content, even on Pocoyo's white backgrounds, always carries
#: some colour. Measured across sample shorts: cards sit at Y>=232 with
#: saturation under 1.0, content never below 2.8.
CARD_Y, CARD_SAT = 232.0, 1.2


def card_start(src: Path, near: float, back: float = 6.0,
               fwd: float = 12.0) -> float | None:
    """When does the title card opening this segment actually begin?

    YouTube chapter marks are typed by hand and often sit a few seconds early,
    so cutting on them alone leaves the tail of the PREVIOUS segment at the
    head of this one - visible in 3 of the first 5 shorts sampled. The card is
    a reliable landmark, so we find it rather than trusting the mark.
    """
    lo = max(0.0, near - back)
    out = run(["ffmpeg", "-v", "error", "-ss", f"{lo:.3f}", "-t",
               f"{back + fwd:.3f}", "-i", str(src), "-vf",
               "fps=4,signalstats,metadata=print:file=-", "-an", "-f", "null", "-"])
    t = y = None
    for line in out.stdout.splitlines():
        line = line.strip()
        if line.startswith("frame:"):
            for tok in line.split():
                if tok.startswith("pts_time:"):
                    t = float(tok.split(":", 1)[1])
        elif line.startswith("lavfi.signalstats.YAVG="):
            y = float(line.split("=", 1)[1])
        elif line.startswith("lavfi.signalstats.SATAVG=") and y is not None:
            sat = float(line.split("=", 1)[1])
            if y >= CARD_Y and sat <= CARD_SAT and t is not None:
                return lo + t
            y = None
    return None


def scene_start(src: Path, near: float, back: float = 6.0,
                fwd: float = 4.0) -> float | None:
    """Fall back to the visual cut when a segment opens with no title card.

    The two detectors are complementary, which is why both are here. Where a
    card exists the picture barely changes across the boundary - white card
    onto white background - so scene detection finds nothing. Where no card
    exists the cut is obvious and scores high. Measured on one compilation:
    card detection got 8 of 12 marks, scene detection got the other 4.
    """
    lo = max(0.0, near - back)
    out = run(["ffmpeg", "-v", "error", "-ss", f"{lo:.3f}", "-t",
               f"{back + fwd:.3f}", "-i", str(src), "-vf",
               "select='gt(scene,0.25)',metadata=print:file=-",
               "-an", "-f", "null", "-"])
    best, best_score, t = None, 0.0, None
    for line in out.stdout.splitlines():
        line = line.strip()
        if line.startswith("frame:"):
            for tok in line.split():
                if tok.startswith("pts_time:"):
                    t = float(tok.split(":", 1)[1])
        elif "scene_score=" in line and t is not None:
            score = float(line.split("=", 1)[1])
            if score > best_score:
                best, best_score = lo + t, score
    return best


def keyframe_at_or_after(src: Path, t: float) -> float:
    """Stream copy can only start on a keyframe; find the one to use."""
    out = run(["ffprobe", "-v", "error", "-select_streams", "v:0",
               "-skip_frame", "nokey", "-show_entries", "frame=pts_time",
               "-read_intervals", f"{max(0.0, t - 3):.3f}%+8",
               "-of", "csv=p=0", str(src)])
    ks = sorted({float(x) for x in out.stdout.replace(",", " ").split()
                 if x.replace(".", "", 1).isdigit()})
    after = [k for k in ks if k >= t - 0.35]
    return after[0] if after else t


def chapters(vid: str) -> tuple[str, list[dict]] | None:
    """Metadata for one video, or None if the fetch itself failed.

    The distinction matters. Returning an empty chapter list on failure makes a
    network blip look exactly like a video that genuinely has no chapters - the
    caller marks it done and it is never retried. Two videos with 20 and 21
    chapters were skipped that way before this returned None instead.
    """
    out = run(["yt-dlp", "--skip-download", "--no-warnings", "-J",
               f"https://www.youtube.com/watch?v={vid}"])
    if out.returncode != 0:
        return None
    try:
        d = json.loads(out.stdout)
    except ValueError:
        return None
    return d.get("title", ""), (d.get("chapters") or [])


def download(vid: str, dest: Path) -> Path | None:
    """Fetch one compilation, clearing any half-finished attempt first.

    yt-dlp stages each stream beside the target as ``<id>.f135.mp4`` and
    ``<id>.f140.m4a`` before merging. Interrupt it and those survive; the next
    attempt then tries to resume from the end of an already-complete stream and
    the server answers HTTP 416, which reads like a network fault but is
    entirely self-inflicted. Deleting them costs one re-download and removes a
    failure that would otherwise silently skip the video.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    for stale in dest.parent.glob(f"{vid}.f*"):
        stale.unlink(missing_ok=True)
    out = run(["yt-dlp", "--no-warnings", "-f", FORMAT,
               "--merge-output-format", "mp4", "-o", str(dest), "--no-part",
               f"https://www.youtube.com/watch?v={vid}"])
    if out.returncode != 0:
        print(f"    download failed: {out.stderr.strip()[:160]}", file=sys.stderr)
        return None
    return dest if dest.exists() else None


def cut(src: Path, dst: Path, start: float, end: float) -> bool:
    dst.parent.mkdir(parents=True, exist_ok=True)
    # -ss before -i seeks fast; -c copy keeps the original bytes.
    out = run(["ffmpeg", "-v", "error", "-ss", f"{start:.3f}", "-to", f"{end:.3f}",
               "-i", str(src), "-c", "copy", "-avoid_negative_ts", "make_zero",
               "-movflags", "+faststart", "-y", str(dst)])
    return out.returncode == 0 and dst.exists()


def concat(parts: list[Path], dst: Path, workdir: Path) -> bool:
    """Join clips through an MPEG-TS intermediate.

    Concatenating the .mp4 clips directly leaves two frames sharing a
    timestamp at every join - ffmpeg reports "non monotonically increasing
    dts" once per boundary, and a player can hiccup there. MPEG-TS carries
    its own continuous timing, so remuxing each clip through it and joining
    those produces a file with no timestamp collisions at all. Measured on a
    four-clip bundle: 3 warnings direct, 0 through TS, with the two durations
    agreeing to a quarter of a second.

    Still no re-encoding - both hops are stream copies.
    """
    stage = workdir / "_ts"
    stage.mkdir(parents=True, exist_ok=True)
    listing = stage / "concat.txt"
    lines = []
    try:
        for i, part in enumerate(parts):
            ts = stage / f"{i:04d}.ts"
            out = run(["ffmpeg", "-v", "error", "-i", str(part), "-c", "copy",
                       "-bsf:v", "h264_mp4toannexb", "-f", "mpegts",
                       "-y", str(ts)])
            if out.returncode != 0:
                print(f"    ts remux failed: {out.stderr.strip()[:160]}",
                      file=sys.stderr)
                return False
            lines.append(f"file '{ts.as_posix()}'\n")
        listing.write_text("".join(lines), encoding="utf-8")
        out = run(["ffmpeg", "-v", "error", "-f", "concat", "-safe", "0",
                   "-i", str(listing), "-c", "copy", "-bsf:a", "aac_adtstoasc",
                   "-movflags", "+faststart", "-y", str(dst)])
        if out.returncode != 0:
            print(f"    concat failed: {out.stderr.strip()[:160]}",
                  file=sys.stderr)
        return out.returncode == 0 and dst.exists()
    finally:
        for f in stage.glob("*"):
            f.unlink(missing_ok=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ids", required=True, type=Path, help="one video id per line")
    ap.add_argument("--work", required=True, type=Path)
    ap.add_argument("--dest", required=True, type=Path, help="Season folder")
    ap.add_argument("--show", default="Pocoyo")
    ap.add_argument("--limit", type=int, help="stop after N videos (for a trial)")
    ap.add_argument("--bundle-only", action="store_true",
                    help="skip fetching; bundle what is already cut")
    args = ap.parse_args()

    args.work.mkdir(parents=True, exist_ok=True)
    shorts_dir = args.work / "shorts"
    episodes_dir = args.work / "episodes"
    episodes_dir.mkdir(parents=True, exist_ok=True)
    state_path = args.work / "state.json"
    state = json.loads(state_path.read_text()) if state_path.is_file() \
        else {"done": [], "taken": [], "shorts": [], "whole": []}
    state.setdefault("whole", [])
    taken = set(state["taken"])

    ids = [l.strip() for l in args.ids.read_text().splitlines() if l.strip()]
    if args.limit:
        ids = ids[:args.limit]

    if not args.bundle_only:
        for n, vid in enumerate(ids, 1):
            if vid in state["done"]:
                continue
            meta = chapters(vid)
            if meta is None:
                print(f"[{n}/{len(ids)}] {vid}  metadata fetch failed, "
                      f"leaving for a retry", flush=True)
                continue
            title, chs = meta
            usable = [c for c in chs
                      if MIN_LEN <= (c["end_time"] - c["start_time"]) <= MAX_LEN]
            fresh = [c for c in usable
                     if c["title"].strip().casefold() not in taken]
            print(f"[{n}/{len(ids)}] {vid}  {len(fresh)} new of {len(chs)} chapters"
                  f"  {title[:44]}", flush=True)
            if not fresh:
                state["done"].append(vid)
                state_path.write_text(json.dumps(state))
                continue

            src = download(vid, args.work / f"{vid}.mp4")
            if src is None:
                continue

            # Resolve each chapter mark to where the segment really starts.
            marks = {}
            for c in chs:
                m = c["start_time"]
                marks[m] = m if m < 1.0 else (
                    card_start(src, m) or scene_start(src, m) or m)
            ordered = sorted(marks)

            def boundary(after: float) -> float:
                later = [x for x in ordered if x > after]
                return marks[later[0]] if later else 0.0

            # Walk the chapters in order, gathering consecutive unused ones.
            run: list[dict] = []

            def flush(run: list[dict]) -> None:
                """Emit a run: whole if it is long enough, else as fragments."""
                if not run:
                    return
                begin = keyframe_at_or_after(src, marks[run[0]["start_time"]])
                stop = boundary(run[-1]["start_time"]) or run[-1]["end_time"]
                length = stop - begin
                if length >= FLOOR:
                    out = episodes_dir / f"{vid}_{int(begin)}.mp4"
                    if cut(src, out, begin, stop):
                        state["whole"].append({"f": out.name, "d": length,
                                               "n": len(run)})
                        print(f"    whole  {length/60:5.1f} min from "
                              f"{len(run)} chapters, no internal cuts", flush=True)
                    return
                for c in run:                       # too short to stand alone
                    b = keyframe_at_or_after(src, marks[c["start_time"]])
                    e = boundary(c["start_time"]) or c["end_time"]
                    if e - b < MIN_LEN:
                        continue
                    out = shorts_dir / f"{len(state['shorts']):04d}.mp4"
                    if cut(src, out, b, e):
                        state["shorts"].append({"f": out.name, "d": e - b})

            for c in usable:
                key = c["title"].strip().casefold()
                if key in taken:
                    flush(run)
                    run = []
                    continue
                taken.add(key)
                state["taken"].append(key)
                run.append(c)
                if sum(x["end_time"] - x["start_time"] for x in run) >= TARGET:
                    flush(run)
                    run = []
            flush(run)

            src.unlink(missing_ok=True)
            state["done"].append(vid)
            state_path.write_text(json.dumps(state))
            print(f"    running total: {len(state['whole'])} whole episodes, "
                  f"{len(state['shorts'])} fragments", flush=True)

    # --- assemble ----------------------------------------------------------
    print(f"\n{len(state['whole'])} whole episodes cut; "
          f"{len(state['shorts'])} fragments left to stitch")

    # Fragments already folded into an episode must never be joined again.
    # Re-running assembly without this produced a second full set of joined
    # episodes - 85 files where 62 were real, every fragment used twice.
    consumed = set(state.setdefault("consumed", []))
    pending = [f for f in state["shorts"] if f["f"] not in consumed]
    if len(pending) < len(state["shorts"]):
        print(f"  skipping {len(state['shorts']) - len(pending)} fragments "
              f"already used in an earlier pass")

    if pending:
        # Some uploads are 854x468 rather than 854x480. Clips can only be
        # concatenated with others of identical parameters, so group by
        # signature and bundle within each group - refusing outright would
        # have thrown away every fragment from the odd-sized uploads.
        groups: dict[tuple, list[dict]] = {}
        for f in pending:
            key = tuple(sorted(probe(shorts_dir / f["f"]).items()))
            groups.setdefault(key, []).append(f)
        print(f"  fragments fall into {len(groups)} encoding group(s):")
        for k, v in groups.items():
            d = dict(k)
            print(f"    {len(v):>3} clips at {d.get('w')}x{d.get('h')}")

        for key, members in groups.items():
            bundle, acc = [], 0.0
            for f in members:
                bundle.append(shorts_dir / f["f"])
                acc += f["d"]
                if acc >= TARGET:
                    out = episodes_dir / f"joined_{len(state['whole']):03d}.mp4"
                    if concat(bundle, out, args.work):
                        state["whole"].append({"f": out.name, "d": acc,
                                               "n": len(bundle)})
                        state["consumed"].extend(p.name for p in bundle)
                    bundle, acc = [], 0.0
            if acc >= MIN_BUNDLE:
                out = episodes_dir / f"joined_{len(state['whole']):03d}.mp4"
                if concat(bundle, out, args.work):
                    state["whole"].append({"f": out.name, "d": acc,
                                           "n": len(bundle)})
                    state["consumed"].extend(p.name for p in bundle)
        state_path.write_text(json.dumps(state))

    # Number everything together so the two kinds are indistinguishable on air.
    args.dest.mkdir(parents=True, exist_ok=True)
    made = 0
    for i, ep in enumerate(state["whole"], 1):
        src = episodes_dir / ep["f"]
        if not src.is_file():
            continue
        dst = args.dest / f"{args.show} - S01E{i:02d}.mp4"
        src.replace(dst)
        made += 1
    whole = sum(1 for e in state["whole"] if not e["f"].startswith("joined_"))
    total = sum(e["d"] for e in state["whole"])
    print(f"\n{made} episodes written to {args.dest}")
    print(f"  {whole} with no internal cuts, {made - whole} stitched from fragments")
    print(f"  {total/3600:.1f} hours, mean {total/max(made,1)/60:.1f} min per episode")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
