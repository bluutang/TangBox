#!/usr/bin/env python3
r"""Which videos are geo-blocked, and which VPN country would unblock them all.

yt-dlp's geo-block error names every country the video IS available in. Collect
those lists across all blocked videos and INTERSECT them, and you get the set of
exits that would fetch the lot in one pass - rather than rerolling the VPN and
finding out a show at a time.

    python3 _tools/blocked.py            # report
    python3 _tools/blocked.py --retry    # re-fetch just the blocked ones

Only successful downloads are written to _archive.txt, so a retry never
re-downloads anything already held.
"""
from __future__ import annotations
import re, subprocess, sys
from pathlib import Path

ROOT = Path("/Users/briantang/Downloads/Converted")
BLOCK = re.compile(r'\[youtube\] ([A-Za-z0-9_-]{11}): The uploader has not made '
                   r'this video available in your country')
ALLOW = re.compile(r'This video is available in ([^\n]+)')

def main() -> int:
    retry = "--retry" in sys.argv
    per_show: dict[str, set[str]] = {}
    allowed: list[set[str]] = []

    for log in sorted(ROOT.glob("*/_download.log")):
        show = log.parent.name
        text = log.read_text(errors="replace").replace("\r", "\n")
        ids = set(BLOCK.findall(text))
        if not ids:
            continue
        # only count ones NOT since downloaded
        arch = log.parent / "_archive.txt"
        have = {l.split()[1] for l in arch.read_text().splitlines()
                if len(l.split()) > 1} if arch.exists() else set()
        ids -= have
        if ids:
            per_show[show] = ids
        for line in ALLOW.findall(text):
            allowed.append({c.strip().rstrip('.') for c in line.split(",") if c.strip()})

    if not per_show:
        print("  no geo-blocked videos outstanding")
        return 0

    total = sum(len(v) for v in per_show.values())
    print(f"  {total} geo-blocked videos still missing\n")
    for show, ids in per_show.items():
        print(f"  {show}: {len(ids)}")

    if allowed:
        common = set.intersection(*allowed)
        pick = [c for c in ("Mexico", "Spain", "Canada", "United Kingdom", "Argentina",
                            "Colombia", "Chile", "Peru", "Brazil", "Japan", "Netherlands",
                            "Sweden", "United States", "Germany", "France", "Poland")
                if c in common]
        print(f"\n  {len(common)} countries would unblock ALL of them.")
        print(f"  Common VPN choices that work: {', '.join(pick) if pick else '(none of the usual ones)'}")

    if retry:
        for show, ids in per_show.items():
            print(f"\n  retrying {len(ids)} in {show}...")
            for vid in sorted(ids):
                subprocess.run([
                    "yt-dlp", "--ignore-errors", "--no-abort-on-error",
                    "-f", "bestvideo[vcodec^=avc1][height<=720]+bestaudio[ext=m4a]/"
                          "best[vcodec^=avc1][height<=720]/best[height<=720]",
                    "--merge-output-format", "mp4",
                    "--download-archive", str(ROOT / show / "_archive.txt"),
                    "--no-overwrites", "--retries", "10",
                    "-o", str(ROOT / show / "_staging" / "%(playlist_index)03d-%(id)s.%(ext)s"),
                    f"https://www.youtube.com/watch?v={vid}",
                ], stdout=subprocess.DEVNULL)
    else:
        print("\n  (report only - pass --retry once you are on an allowed server)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
