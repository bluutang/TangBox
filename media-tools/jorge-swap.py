#!/usr/bin/env python3
r"""Put Jorge's finished episodes into Season 01 and free the show to be filed.

Three sources of truth, in priority order:
  _reenc/  the REPAIRED pieces - 19 old files whose cuts were wrong, plus 4 of
           the 5 late 66-minute arrivals that needed three-way splits
  _split/  the original stream-copied cuts, used ONLY for the 10 files that were
           always correct (001-005, 009, 015, 017, 019, 022)

A source with a _reenc version always wins: those were re-cut precisely because
the _split copy opened on the previous episode's credits, or on black.

The 34 source compilations move from _staging to _untrimmed-source. They are the
originals and must not be thrown away, but organize-channels.py refuses to file a
show while _staging holds anything - underscore folders are working space and it
ignores every other one. NA-XBSF8xSNt2g has no usable split yet, so its source is
the one still waiting for attention.

Numbering is sequential by source then part. These are compilations, so no
"real" episode number exists to honour - inventing a mapping to a database is
exactly what put wrong titles on 246 files.

    python3 _tools/jorge-swap.py            # dry run
    python3 _tools/jorge-swap.py --apply
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path

SHOW = Path("/Users/briantang/Downloads/Converted/Jorge el Curioso")
HEALTHY = {"001","002","003","004","005","009","015","017","019","022"}

def main() -> int:
    apply = "--apply" in sys.argv
    sources = sorted(p.stem for p in (SHOW / "_staging").glob("*.mp4"))
    plan, unsplit = [], []
    for stem in sources:
        key = stem.split("-")[0]
        reenc = sorted((SHOW / "_reenc").glob(f"{stem} - pt*.mp4"))
        split = sorted((SHOW / "_split").glob(f"{stem} - pt*.mp4"))
        pieces = split if (key in HEALTHY and split) else (reenc or split)
        if not pieces:
            unsplit.append(stem); continue
        src = "_split" if pieces is split else "_reenc"
        for p in pieces:
            plan.append((p, src, stem))

    print(f"  {len(sources)} sources -> {len(plan)} episodes")
    from collections import Counter
    print("  ", dict(Counter(s for _, s, _ in plan)))
    if unsplit:
        print(f"  NOT SPLIT (source kept, no episodes): {', '.join(unsplit)}")

    moves = []
    for i, (p, src, stem) in enumerate(plan, 1):
        dst = SHOW / "Season 01" / f"Jorge el Curioso - S01E{i:02d}.mp4"
        moves.append((p, dst, src, stem))
    dsts = [d for _, d, _, _ in moves]
    if len(set(dsts)) != len(dsts):
        print("  !! duplicate destinations - refusing"); return 1

    print("\n  sample:")
    for p, d, src, _ in moves[:3]:
        print(f"    {src}/{p.name[:44]:46s} -> {d.name}")
    print(f"    ... and {len(moves)-3} more")

    if not apply:
        print("\n  (dry run - pass --apply)")
        return 0

    (SHOW / "Season 01").mkdir(parents=True, exist_ok=True)
    (SHOW / "_untrimmed-source").mkdir(exist_ok=True)
    # record where every episode came from, so this is traceable and undoable
    ledger = [{"episode": d.name, "from": f"{src}/{p.name}", "source": stem}
              for p, d, src, stem in moves]
    (SHOW / "_untrimmed-source" / "_episode-origins.json").write_text(
        json.dumps(ledger, ensure_ascii=False, indent=1))
    for p, d, _, _ in moves:
        p.rename(d)
    for p in (SHOW / "_staging").glob("*.mp4"):
        p.rename(SHOW / "_untrimmed-source" / p.name)
    print(f"\n  filed {len(moves)} episodes; {len(sources)} sources kept in _untrimmed-source")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
