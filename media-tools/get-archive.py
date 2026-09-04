#!/usr/bin/env python3
"""Download video files from archive.org items into a show's staging folder.

archive.org is not YouTube: there is no geo-blocking, no format negotiation and
no playlist. Each item is a plain file listing, so this fetches the metadata,
picks the h.264 derivatives (already what the Pi wants) and pulls them over
plain HTTPS with resume support.

  get-archive.py "Arthur" arthurT01LatCast ArthurT02LatCast

Like get-playlist.sh it keeps an _archive.txt of finished files, so re-running
is cheap and skips whatever already landed.
"""
from __future__ import annotations
import json, subprocess, sys, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path("/Users/briantang/Downloads/Converted")

def meta(ident: str) -> dict:
    with urllib.request.urlopen(f"https://archive.org/metadata/{ident}", timeout=60) as r:
        return json.load(r)

EXFAT_BAD = {'"': "'", "*": "+", "/": "-", ":": " -", "<": "(", ">": ")",
             "?": "", "\\": "-", "|": "｜"}


def exfat_safe(name: str) -> str:
    for k, v in EXFAT_BAD.items():
        name = name.replace(k, v)
    return name


def main() -> int:
    args = sys.argv[1:]
    # $NAME_FILTER keeps only files whose name matches, for items that hold more
    # than one thing - Bear in the Big Blue House stores Latin Spanish, Mandarin
    # and Italian side by side, and taking the lot would give a channel that
    # changes language between episodes.
    import os, re as _re
    pat = os.environ.get("NAME_FILTER")
    show, idents = args[0], args[1:]
    stage = ROOT / show / "_staging"; stage.mkdir(parents=True, exist_ok=True)
    arch = ROOT / show / "_archive.txt"
    done = set(arch.read_text().split("\n")) if arch.exists() else set()

    for ident in idents:
        d = meta(ident)
        # Items label their video differently - Arthur offers "h.264", the DBZ
        # rip only "MPEG4". Take the best format the item actually has, and
        # only ONE per episode: many items store the same episode twice (an
        # original plus a derivative), which would otherwise double the download.
        # Dedupe by EPISODE, not by format label. Picking a single format label
        # for the whole item looked fine until Digimon Adventure 02, where 49
        # files are labelled "MPEG4", one "h.264" and one "Matroska" - the old
        # code preferred the h.264 label and downloaded exactly ONE episode of
        # fifty, reporting success. The label is unreliable anyway: files marked
        # "MPEG4" here are h264 inside, verified with ffprobe.
        #
        # So: group every video file by its name with the extension and
        # archive.org's ".ia" derivative marker stripped, then keep one file per
        # group, best format first. That still avoids fetching an episode twice
        # (the original reason for the filter) without dropping 49 of them.
        PREF = ("h.264", "MPEG4", "512Kb MPEG4", "Matroska", "Ogg Video")
        VIDEXT = (".mp4", ".mkv", ".avi", ".ogv", ".m4v")
        groups: dict[str, list] = {}
        for f in d.get("files", []):
            n = f.get("name", "")
            if not n.lower().endswith(VIDEXT):
                continue
            stem = n.rsplit(".", 1)[0]
            if stem.endswith(".ia"):
                stem = stem[:-3]
            groups.setdefault(stem, []).append(f)
        if not groups:
            print(f"[{ident}] no video files found")
            continue
        def rank(f):
            fm = f.get("format")
            return PREF.index(fm) if fm in PREF else len(PREF)
        vids = [sorted(g, key=rank)[0] for g in groups.values()]
        seen_fmt = sorted({v.get("format") for v in vids})
        print(f"[{ident}] {len(vids)} episodes (formats: {', '.join(str(x) for x in seen_fmt)})",
              flush=True)
        if pat:
            before = len(vids)
            vids = [f for f in vids if _re.search(pat, f["name"], _re.I)]
            print(f"[{ident}] name filter kept {len(vids)} of {before}", flush=True)
        vids.sort(key=lambda f: f["name"])
        # (the count is already reported above, with the formats actually chosen -
        # this line used to hardcode "h.264" no matter what was selected)
        for f in vids:
            key = f"archive {ident}/{f['name']}"
            # exFAT (the USB drive) forbids  " * / : < > ? \ |  and archive.org
            # names may contain them - two Bear episodes arrived with "?" in the
            # title and would have failed the copy to the drive. Sanitise the FILE
            # name only; the URL is still built from the real one.
            dst = stage / exfat_safe(f["name"])
            size = int(f.get("size") or 0)
            if key in done or (dst.exists() and dst.stat().st_size == size):
                continue
            # quote(), not a space substitution. Escaping only spaces leaves a
            # "?" in the filename intact, and the server then reads everything
            # after it as a query string - so "238. What's the Story? (Latin
            # Spanish).mp4" requested a path that stops at "Story" and 404s.
            # Measured: naive = HTTP 404, quote() = HTTP 206 on the same file.
            url = f"https://archive.org/download/{ident}/{urllib.parse.quote(f['name'])}"
            # -L is REQUIRED: archive.org always 302-redirects /download/ to a
            # specific node (dn######.xx.archive.org). Without it curl saves the
            # empty redirect body and exits 0 - --fail only trips on 4xx/5xx - so
            # every file lands at 0 bytes and reports "FAIL (rc=0)". That silently
            # cost Arthur, Dragon Ball Z and Bear every episode.
            # -C - resumes a partial file; --fail so an HTTP error is not saved as content
            r = subprocess.run(["curl", "-sS", "--fail", "-L", "--retry", "10", "--retry-delay", "5",
                                "-C", "-", "-o", str(dst), url])
            if r.returncode == 0 and dst.exists() and dst.stat().st_size == size:
                with arch.open("a") as fh: fh.write(key + "\n")
                print(f"  ok  {f['name']}  {size/1e6:.0f} MB", flush=True)
            else:
                print(f"  FAIL {f['name']} (rc={r.returncode})", flush=True)
    n = len([p for p in stage.glob('*.mp4')])
    print(f"=== {show} staged: {n} files")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
