#!/usr/bin/env python3
"""Full-decode every playable episode and report anything that is not clean.

Each show was verified at filing time, but nothing has ever checked the whole
library in one pass - and 22 files were re-encoded on 2026-09-04. A file can
also rot on disk. This decodes every frame and reports any ffmpeg error.

Parallel because serial is ~3 hours: the Mac decodes at ~450x realtime, so the
job is CPU-bound and scales across cores. 8 of 10, leaving room to work.
"""
import subprocess, sys, time, json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path.home() / "Downloads" / "Converted"
OUT = Path(sys.argv[1])
WORKERS = 8

def playable(p: Path) -> bool:
    # Mirror the box's own exclude rules: anything under, or named, _*
    return not any(part.startswith(("_", ".")) for part in p.relative_to(ROOT).parts)

files = sorted(p for p in ROOT.rglob("*.mp4") if playable(p))
print(f"  {len(files)} playable episodes to decode", flush=True)

def check(p: Path):
    r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(p), "-f", "null", "-"],
                       capture_output=True, text=True)
    return p, r.stderr.strip()

start = time.time()
bad, done = [], 0
with ThreadPoolExecutor(max_workers=WORKERS) as pool:
    futures = {pool.submit(check, p): p for p in files}
    for fut in as_completed(futures):
        p, err = fut.result()
        done += 1
        if err:
            bad.append({"file": str(p.relative_to(ROOT)), "error": err[:300]})
            print(f"  BAD  {p.relative_to(ROOT)}\n       {err[:160]}", flush=True)
        if done % 250 == 0:
            el = time.time() - start
            rate = done / el
            print(f"  ... {done}/{len(files)}  {el/60:.1f} min elapsed, "
                  f"~{(len(files)-done)/rate/60:.1f} min left, {len(bad)} bad", flush=True)

el = time.time() - start
print(f"\n  DONE in {el/60:.1f} min - {done} decoded, {len(bad)} with errors", flush=True)
OUT.write_text(json.dumps(bad, indent=1))
