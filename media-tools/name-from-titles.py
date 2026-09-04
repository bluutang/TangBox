#!/usr/bin/env python3
"""Name staged downloads from their YouTube titles.

Safe because the title comes from the video itself: unlike a database lookup it
cannot land on the wrong episode, which is the failure that got titles banned
after Rugrats. Same reasoning as Plaza Sesamo.

Only valid where ONE video becomes ONE episode. Split compilations and joined
clips have no title of their own and must be numbered instead.

  dry run  : name-from-titles.py "Franklin" franklin.json
  apply    : name-from-titles.py "Franklin" franklin.json --apply
"""
from __future__ import annotations
import json, re, subprocess, sys, unicodedata
from pathlib import Path


def duration(path: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(path)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0

ROOT = Path("/Users/briantang/Downloads/Converted")
SCRATCH = Path("/private/tmp/claude-501/-Users-briantang-BluuClaude-tang-box"
               "/33ed14ed-6324-4ed1-91ae-25fb6b0a564d/scratchpad")

# Channel boilerplate that carries no information about the episode.
# "Temporada 3" is a season marker, not a story name - it was arriving as if it
# were the second title of a two-story episode. Stripped rather than used: the
# box sorts alphabetically and never parses a season, and Plaza Sesamo already
# files everything flat under Season 01.
SEASON = re.compile(r'^\s*temporada\s+\d+\s*$', re.I)

BOILER = re.compile(
    r'\s*\|\s*(episodios?\s+completos?|epis[oó]dio\s+completo|ep\s+completo|'
    r'cap[ií]tulo\s+entero|full\s+episodes?|clifford\s+en\s+espa[nñ]ol|'
    r'el\s+autob[uú]s\s+m[aá]gico[^|]*|jorge\s+el\s+curioso[^|]*|'
    r'daniel\s+tigre[^|]*|pistas\s+de\s+blue[^|]*|ciencia[^|]*|'
    r'scholastic|video\s+nuevo)\s*', re.I)
PARENS = re.compile(r'\s*\((episodios?\s+completos?[^)]*|hd[^)]*|'
                    r'episodio\s+completo[^)]*)\)\s*', re.I)

def strip_emoji(s: str) -> str:
    return ''.join(c for c in s if unicodedata.category(c) not in ('So', 'Cs', 'Co', 'Cn'))

def clean(title: str, show: str = "") -> str:
    t = strip_emoji(title)
    t = BOILER.sub(' | ', t)
    t = PARENS.sub(' ', t)
    parts = [p.strip() for p in t.split('|')]
    parts = [p for p in parts
             if p and not BOILER.match('| ' + p) and not SEASON.match(p)]
    # A segment can be "Temporada 3 Daniel Tigre en Español" - season marker and
    # channel name run together once the pipe between them has gone.
    parts = [re.sub(r'\s*temporada\s+\d+\s*', ' ', x, flags=re.I).strip() for x in parts]
    parts = [re.sub(r'\s*daniel tigre en espa[nñ]ol\s*', ' ', x, flags=re.I).strip() for x in parts]
    parts = [x for x in parts if x]
    # Drop a segment that is just the show's own name. Uploaders lead with it
    # ("Barney | Un Pequeño Gran Día"), and once the pipes are re-joined it
    # reads as if the show were the first of two stories.
    if show:
        low = show.lower()
        parts = [x for x in parts if x.lower() != low and not low.startswith(x.lower() + " ")]
    t = ' ｜ '.join(parts) if parts else t
    # Two stories in one episode are separated by a FULLWIDTH vertical line
    # (U+FF5C), not ASCII '|'. The USB drive is exFAT (README Part E), and exFAT
    # forbids " * / : < > ? \\ | outright - an ASCII pipe would make the file
    # impossible to copy to the drive. U+FF5C is outside that set and looks the
    # same. The box never displays filenames anyway (channel.py finds episodes by
    # extension and sorts alphabetically), so this is purely for browsing.
    t = t.replace('/', ' ｜ ').replace('\\', ' ｜ ').replace(':', ' -')
    t = re.sub(r'[*?"<>|]', '', t)
    return re.sub(r'\s{2,}', ' ', t).strip(' .-')

def main() -> int:
    show, meta = sys.argv[1], sys.argv[2]
    apply = '--apply' in sys.argv
    # A title only describes the whole file. A COMPILATION's title names just its
    # first episode, so naming one would put the wrong name on everything after
    # the first cut. Only files that are already one episode get named; the rest
    # wait until they have been split.
    cap = 1800.0
    for i, a in enumerate(sys.argv):
        if a == "--max-minutes":
            cap = float(sys.argv[i + 1]) * 60
    entries = json.load(open(SCRATCH / meta))["entries"]
    titles = {e["id"]: e["title"] for e in entries if e}

    stage = ROOT / show / "_staging"
    dest = ROOT / show / "Season 01"
    files = sorted(p for p in stage.glob("*.mp4") if not re.search(r'\.f\d+\.mp4$', p.name))

    plan, unmatched, too_long = [], [], []
    for p in files:
        if duration(p) > cap:
            too_long.append(p.name); continue
        m = re.match(r'^(\d+)-([A-Za-z0-9_-]{11})$', p.stem)
        if not m or m.group(2) not in titles:
            unmatched.append(p.name); continue
        idx, vid = int(m.group(1)), m.group(2)
        raw = titles[vid]
        # Some uploaders prefix their own episode number: "Franklin - 48 - Story".
        # That number is better than the playlist position (it is the uploader's
        # own ordering) and repeating the show name in the filename is noise.
        pre = re.match(rf'^\s*{re.escape(show)}\s*[-–]\s*(\d{{1,3}})\s*[-–]\s*(.+)$', raw, re.I)
        if pre:
            idx, raw = int(pre.group(1)), pre.group(2)
        name = clean(raw, show)
        plan.append((p, dest / f"{show} - S01E{idx:02d} - {name}.mp4"))

    # A show pulled from SEVERAL playlists into one folder gets a filename index
    # that restarts at 001 for each playlist, so two files can claim the same
    # episode number. Barney did exactly that from two playlists, and Sailor Moon
    # comes from five. If the numbers collide, throw them away and number the
    # whole set in order instead - the box never parses these anyway.
    nums = [int(re.search(r"S01E(\d+)", d.name).group(1)) for _, d in plan]
    if len(set(nums)) != len(nums):
        print(f"  ! episode numbers collided ({len(nums) - len(set(nums))} clashes)"
              f" - renumbering the whole set in order")
        plan.sort(key=lambda t: t[0].name)
        plan = [(src, dst.with_name(re.sub(r"S01E\d+", f"S01E{i:02d}", dst.name)))
                for i, (src, dst) in enumerate(plan, 1)]

    print(f"staged   : {len(files)}")
    print(f"to name  : {len(plan)}")
    print(f"unmatched: {len(unmatched)}")
    print(f"left as-is: {len(too_long)}  (over {cap/60:.0f} min - split these first)")
    for u in unmatched[:5]: print("   !", u)
    print()
    for src, dst in plan[:8]:
        print(f"  {src.name}\n    -> {dst.name}")
    if len(plan) > 8: print(f"  ... and {len(plan)-8} more")
    over = [d for _, d in plan if len(d.name) > 150]
    if over: print(f"\n  WARNING: {len(over)} names over 150 chars")

    if not apply:
        print("\n(dry run - pass --apply to move files)"); return 0
    dest.mkdir(parents=True, exist_ok=True)
    for src, dst in plan:
        if dst.exists(): print(f"SKIP exists: {dst.name}"); continue
        src.rename(dst)
    print(f"\nmoved {len(plan)} files into {dest}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
