#!/usr/bin/env python3
r"""File Digimon's staged episodes into Season NN, one archive.org item per season.

Brian's call: Adventure (1999) and Adventure 02 are ONE show, two seasons - not
two shows. get-archive.py stages both items flat into the same folder, so this
runs after each item and files whatever is loose into the season just fetched.

The archive.org filenames already carry a leading episode number and the
uploader's own Spanish title ("01.- La Isla de las Aventuras.mp4"). Those titles
ship WITH the files, so they are the safe kind to keep - unlike a database title
looked up and matched by episode number.

    python3 _tools/digimon-file.py 1     # file loose staged files as season 1
"""
from __future__ import annotations
import re, sys, unicodedata
from pathlib import Path

SHOW = Path("/Users/briantang/Downloads/Converted/Digimon Adventure")
BAD = {'"': "'", "*": "+", "/": "-", ":": " -", "<": "(", ">": ")",
       "?": "", "\\": "-", "|": "｜"}

def safe(t: str) -> str:
    t = unicodedata.normalize("NFC", t)
    for k, v in BAD.items():
        t = t.replace(k, v)
    return re.sub(r"\s+", " ", t).strip().strip("-").strip().rstrip(".")[:110]

def main() -> int:
    season = int(sys.argv[1])
    stage = SHOW / "_staging"
    dest = SHOW / f"Season {season:02d}"
    files = sorted(p for p in stage.glob("*.mp4")) if stage.is_dir() else []
    if not files:
        print(f"  digimon-file: nothing loose in _staging for season {season}")
        return 0
    dest.mkdir(parents=True, exist_ok=True)
    moved = 0
    for p in files:
        # Two naming shapes, one per archive.org item:
        #   season 1: "01.- La Isla de las Aventuras"
        #   season 2: "Digimon Adventure 02 [Episodio 01] Español Latino (ETC TV)"
        # The old parser only understood a LEADING number, so season 2's single
        # downloaded file was filed as E00.
        m = re.match(r"^(\d+)\s*[.\-]*\s*(.*)$", p.stem)
        if m:
            ep, title = int(m.group(1)), safe(m.group(2))
        else:
            b = re.search(r"\[\s*Episodio\s*(\d+)\s*\]", p.stem, re.I)
            if b:
                ep = int(b.group(1))
                title = safe(re.sub(r"\[\s*Episodio\s*\d+\s*\]", "", p.stem, flags=re.I))
            else:
                ep, title = 0, safe(p.stem)
        name = f"Digimon Adventure - S{season:02d}E{ep:02d}" + (f" - {title}" if title else "") + ".mp4"
        dst = dest / name
        if dst.exists():
            print(f"  digimon-file: {dst.name} already there, leaving {p.name} alone")
            continue
        p.rename(dst); moved += 1
    print(f"  digimon-file: filed {moved} episodes into Season {season:02d}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
