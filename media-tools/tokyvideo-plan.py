#!/usr/bin/env python3
r"""Turn the video-source-links.csv into a download plan.

Column A (page_url) carries the show, season, episode and often the episode
title in its slug. Column B (source_url) is a direct CDN mp4 that plain curl can
fetch and resume.

These titles come FROM THE PAGE THE VIDEO LIVES ON, not from a database looked up
and matched by episode number - so they are the safe kind, like a YouTube title.
The rule that banned titles exists because looked-up ones were matched to the
wrong episodes; a title carried in the source's own URL cannot be.

    python3 _tools/tokyvideo-plan.py           # print the plan
    python3 _tools/tokyvideo-plan.py --json    # write it for the downloader
"""
from __future__ import annotations
import csv, json, re, sys, unicodedata
from pathlib import Path
from collections import defaultdict

CSV = Path("/Users/briantang/Library/CloudStorage/GoogleDrive-brianluutang@gmail.com"
           "/My Drive/TΛNG Downloads/video-source-links.csv")
OUT = Path("/Users/briantang/Downloads/Converted/_tools/tokyvideo-plan.json")

# Brian's skip list: Nintendo promotional clips and the bare "capitulo-N-hd"
# rows, which carry no show name at all and cannot be identified.
SKIP = re.compile(r"^(capitulo-\d+\s*-?\s*hd?$|nintendo-|conwiiupuedo|como-se-hizo|"
                  r"art-academy|30-aniversario|eiji-aonuma|adivina-el|super-smash|"
                  r"the-last-story|presentacion-de)", re.I)

BAD = {'"': "'", "*": "+", "/": "-", ":": " -", "<": "(", ">": ")",
       "?": "", "\\": "-", "|": "｜"}

def safe(t: str) -> str:
    t = unicodedata.normalize("NFC", t)
    for k, v in BAD.items():
        t = t.replace(k, v)
    return re.sub(r"\s+", " ", t).strip().rstrip(".")[:110]

def titlecase(sl: str) -> str:
    return safe(sl.replace("-", " ").strip().capitalize())

# Avatar's "books" are its seasons
BOOK = {"agua": 1, "tierra": 2, "fuego": 3}

def classify(slug: str):
    """-> (show, season, episode, title) or None to skip."""
    if SKIP.match(slug):
        return None

    # Spidey / Bob Esponja:  <show>-t01-e01-<title>
    m = re.match(r"^(spidey-y-sus-sorprendentes-amigos|bob-esponja)-t(\d+)-e(\d+)-?(.*)$", slug)
    if m:
        show = {"spidey-y-sus-sorprendentes-amigos": "Spidey y sus Sorprendentes Amigos",
                "bob-esponja": "Bob Esponja"}[m.group(1)]
        return show, int(m.group(2)), int(m.group(3)), titlecase(m.group(4))

    # One row lost its show prefix entirely: "t03-e13-quietos-es-doc-ock-ve-rapido-jeff".
    # It is Spidey on two independent grounds - Doc Ock and Jeff are Spidey
    # characters, not Bob Esponja ones, and S03E13 is the ONLY gap in Spidey's
    # otherwise unbroken S03 run of 1-30.
    m = re.match(r"^t(\d+)-e(\d+)-(.*)$", slug)
    if m:
        return ("Spidey y sus Sorprendentes Amigos", int(m.group(1)),
                int(m.group(2)), titlecase(m.group(3)))

    # Korra:  the-legend-of-korra-s2e7-espanol-latino
    m = re.match(r"^the-legend-of-korra-s(\d+)e(\d+)", slug)
    if m:
        return "La Leyenda de Korra", int(m.group(1)), int(m.group(2)), ""

    # Pokemon: the ABSOLUTE capitulo number is the only reliable key. The slug's
    # own "temporada" is wrong on two rows (capitulo 92 claims temporada 11,
    # capitulo 101 claims temporada 20) while sitting squarely inside season 2's
    # range. There are no duplicate capitulo numbers anywhere in the 115 rows, so
    # those two are single copies with a bad label, not alternate versions.
    # Season boundaries are taken from the DATA - the rows that do declare a
    # season - not from what a database says Pokemon's seasons are.
    m = re.match(r"^pokemon-capitulo-(\d+)", slug)
    if m:
        cap = int(m.group(1))
        if cap <= 81:    s, e = 1, cap
        elif cap <= 116: s, e = 2, cap - 81
        else:            s, e = 3, cap - 116
        return "Pokémon", s, e, ""

    # Avatar: book and absolute number agree perfectly across all 61 rows
    # (agua 1-20, tierra 21-40, fuego 41-61), so the number alone fixes the book
    # and the one row with no book name is placed with certainty.
    m = re.match(r"^avatar(?:-libro-(agua|tierra|fuego))?-capitulo-(\d+)-?(.*)$", slug)
    if m:
        cap = int(m.group(2))
        book = BOOK[m.group(1)] if m.group(1) else (1 if cap <= 20 else 2 if cap <= 40 else 3)
        rest = m.group(3)
        rest = re.sub(r"^libro-(agua|tierra|fuego)-?", "", rest)   # title after the book
        rest = re.sub(r"^libro-", "", rest)                        # stray "libro-" artefact
        off = {1: 0, 2: 20, 3: 40}[book]
        return ("Avatar La Leyenda de Aang", book, cap - off, titlecase(rest))

    return ("UNCLASSIFIED", 0, 0, slug)

def main() -> int:
    rows = list(csv.DictReader(CSV.open(encoding="utf-8")))
    plan, skipped, unknown = [], [], []
    for r in rows:
        slug = r["page_url"].rstrip("/").rsplit("/", 1)[-1]
        c = classify(slug)
        if c is None:
            skipped.append(slug); continue
        show, s, e, title = c
        if show == "UNCLASSIFIED":
            unknown.append(slug); continue
        name = f"{show} - S{s:02d}E{e:02d}" + (f" - {title}" if title else "") + ".mp4"
        plan.append({"show": show, "season": s, "episode": e,
                     "file": name, "url": r["source_url"], "slug": slug})

    per = defaultdict(list)
    for p in plan: per[p["show"]].append(p)
    print(f"{len(rows)} rows -> {len(plan)} to download, {len(skipped)} skipped, "
          f"{len(unknown)} unclassified\n")
    for show in sorted(per):
        eps = per[show]
        seasons = defaultdict(int)
        for p in eps: seasons[p["season"]] += 1
        ss = " ".join(f"S{k:02d}:{v}" for k, v in sorted(seasons.items()))
        print(f"  {show}  ({len(eps)})")
        print(f"    {ss}")
        print(f"    e.g. {eps[0]['file']}")
        # a duplicate destination would silently lose an episode
        names = [p["file"] for p in eps]
        dup = {n for n in names if names.count(n) > 1}
        if dup:
            print(f"    !! {len(dup)} DUPLICATE NAMES e.g. {list(dup)[:2]}")
        print()
    if unknown:
        print(f"  UNCLASSIFIED ({len(unknown)}) - not downloaded:")
        for u in unknown[:8]: print("   ", u[:88])
    if "--json" in sys.argv:
        OUT.write_text(json.dumps(plan, ensure_ascii=False, indent=1))
        print(f"\n  wrote {OUT}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
