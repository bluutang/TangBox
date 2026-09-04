#!/usr/bin/env python3
r"""Join Daniel Tigre's 11-minute segments into full-length episodes.

The show aired as two ~11-minute stories per half hour, and 14 of the downloads
are single segments while the other 28 are already full episodes. Pairing them
gives a consistent ~23 minutes across the channel.

Pairs are THEMED where the titles show an obvious partner and by episode number
otherwise - Brian's call. Every file shares one encode profile (h264 1280x720
23.976fps, aac 44100 stereo), so this concatenates with -c copy: no re-encoding,
no quality loss, and it takes seconds rather than minutes.

Output goes to _joined/ and NOTHING is deleted. The originals stay until the
result has been looked at.

    python3 _tools/join-shorts.py            # dry run
    python3 _tools/join-shorts.py --apply
"""
from __future__ import annotations
import re, subprocess, sys, tempfile
from pathlib import Path

SHOW = Path("/Users/briantang/Downloads/Converted/Daniel Tigre")

# (first, second) by episode number. Themed pairs first, with the reason.
PAIRS = [
    (26, 25),   # "El viaje de la familia Tigre" Parte 1 then Parte 2 - a real
                # two-parter, and the episode NUMBERS are backwards: 25 is Part 2.
    (12, 14),   # "Alergias en la escuela" + "La alergia de Daniel"
    (6, 8),     # "juegan a la escuelita" + "Dia de campo en la escuela"
    (2, 4),     # the rest, in number order
    (11, 17),
    (18, 20),
    (22, 63),
]

def find(n: int) -> Path | None:
    hits = [p for p in SHOW.rglob("*.mp4")
            if not any(x.startswith("_") for x in p.relative_to(SHOW).parts)
            and re.search(rf"S01E{n:02d} - ", p.name)]
    return hits[0] if len(hits) == 1 else None

def title(p: Path) -> str:
    m = re.match(r".*S01E\d+ - (.+)\.mp4$", p.name)
    return m.group(1) if m else p.stem

def main() -> int:
    apply = "--apply" in sys.argv
    out = SHOW / "_joined"
    plan = []
    for a, b in PAIRS:
        pa, pb = find(a), find(b)
        if not pa or not pb:
            print(f"  !! could not resolve E{a:02d}+E{b:02d} - skipped"); continue
        name = f"Daniel Tigre - S01E{a:02d} - {title(pa)} + {title(pb)}.mp4"
        if len(name) > 150:
            name = f"Daniel Tigre - S01E{a:02d} - {title(pa)[:60]} + {title(pb)[:60]}.mp4"
        plan.append((pa, pb, out / name))

    print(f"  {len(plan)} pairs -> {len(plan)} episodes of ~23 min\n")
    for pa, pb, dst in plan:
        print(f"    E{re.search(r'S01E(\d+)', pa.name).group(1)} + "
              f"E{re.search(r'S01E(\d+)', pb.name).group(1)}  ->  {dst.name[:88]}")
    if not apply:
        print("\n  (dry run - pass --apply; originals are kept either way)")
        return 0

    out.mkdir(exist_ok=True)
    for pa, pb, dst in plan:
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            for p in (pa, pb):
                fh.write(f"file '{p.resolve()}'\n")
            lst = fh.name
        r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                            "-f", "concat", "-safe", "0", "-i", lst,
                            "-c", "copy", str(dst)])
        Path(lst).unlink(missing_ok=True)
        ok = r.returncode == 0 and dst.exists()
        print(f"    {'ok  ' if ok else 'FAIL'} {dst.name[:70]}")
    print(f"\n  wrote {len(plan)} joined episodes to _joined/ - originals untouched")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
