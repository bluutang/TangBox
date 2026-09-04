#!/usr/bin/env python3
"""Resolve an ok.ru video id to its best direct rendition and download it.

Adapted from Codex's download_jackie_spanish.py, with one fix: that version's
regex required 'hlsManifestUrl' inside data-options. Older ok.ru uploads carry
no HLS manifest at all - only progressive MP4 renditions - so the match failed
and every Tom y Jerry video looked unresolvable. We match data-options
generally and confirm identity via movie.id instead.
"""
import html, json, re, subprocess, sys, urllib.request
from pathlib import Path

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
# ok.ru's own ladder. "full" is its name for 1080p and sits ABOVE "hd" - it was
# missing here until 2026-09-01, so any upload offering it silently fell back to
# hd (roughly half the bitrate).
RANK = {n: i for i, n in enumerate(
    ["mobile", "lowest", "low", "sd", "hd", "full", "full_hd", "quad_hd", "ultra_hd"])}

def player_data(video_id):
    canonical = f"https://ok.ru/video/{video_id}"
    for page in (f"https://ok.ru/videoembed/{video_id}", canonical):
        try:
            req = urllib.request.Request(page, headers={
                "User-Agent": UA, "Accept-Language": "es-419,es;q=0.9,en;q=0.5"})
            body = urllib.request.urlopen(req, timeout=45).read().decode("utf-8", "replace")
        except Exception:
            continue
        for m in re.finditer(r'data-options=(["\'])(.*?)\1', body, re.S):
            try:
                meta = json.loads(html.unescape(m.group(2)))["flashvars"]["metadata"]
                if isinstance(meta, str):
                    meta = json.loads(meta)
                if str(meta["movie"]["id"]) == str(video_id):
                    return canonical, meta
            except Exception:
                continue
    raise RuntimeError("player metadata not found")

def choose(meta, prefer=None):
    """Best available rendition, or the best that is no better than `prefer`.

    `prefer` caps quality (and therefore file size): prefer="low" takes low if
    present, else the closest rendition below it. Without it you get the best
    the upload offers, which for some shows is hd at ~15x the bytes of low.
    """
    vids = [v for v in meta.get("videos", []) if not v.get("disallowed") and v.get("url")]
    if not vids:
        raise RuntimeError("no direct rendition")
    if prefer is not None:
        cap = RANK.get(prefer, len(RANK))
        capped = [v for v in vids if RANK.get(v.get("name", ""), -1) <= cap]
        if capped:
            vids = capped
    return max(vids, key=lambda v: RANK.get(v.get("name", ""), -1))

def fetch(video_id, dest: Path, min_seconds=60, prefer=None):
    page, meta = player_data(video_id)
    r = choose(meta, prefer)
    tmp = dest.with_name("." + dest.stem + ".part.mp4")   # .mp4 LAST: ffmpeg infers the muxer from the extension
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-user_agent", UA, "-referer", page, "-i", r["url"],
                    "-c", "copy", "-movflags", "+faststart", str(tmp)],
                   check=True, timeout=1800)
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(tmp)], capture_output=True, text=True)
    dur = float(p.stdout.strip() or 0)
    if tmp.stat().st_size < 500_000 or dur < min_seconds:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"validation failed (size/duration {dur:.0f}s)")
    tmp.replace(dest)
    return r.get("name"), dur, dest.stat().st_size

if __name__ == "__main__":
    name, dur, size = fetch(sys.argv[1], Path(sys.argv[2]))
    print(json.dumps({"rendition": name, "duration_s": round(dur, 1),
                      "mb": round(size / 1048576, 1)}))
