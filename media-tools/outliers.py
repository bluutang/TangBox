#!/usr/bin/env python3
"""Find episodes that do not match their siblings.

Born from Dragon Ball Z S01E01: one 1080p file among 290 SD ones, four times
the decode cost of anything else on the channel, and - because that channel is
episode_order: sequential - the FIRST thing played every time anyone landed on
it. It made the remote lag and looked for all the world like a hardware fault.

A file is flagged when it differs from the rest of ITS OWN SHOW: a different
resolution from the show's usual, or a bitrate far above the show's median.
Comparing within a show rather than across the library is the point - PBS at
720p and Nick at 480p are both fine, a lone 1080p among 480p is not.
"""
import json, statistics, subprocess, sys
from collections import Counter
from pathlib import Path

ROOT = Path.home()/"Downloads"/"Converted"
BITRATE_FACTOR = 2.5

def probe(p):
    r = subprocess.run(
        ["ffprobe","-v","error","-select_streams","v:0",
         "-show_entries","stream=width,height:format=bit_rate",
         "-of","json",str(p)], capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
        s = d["streams"][0]
        return (s.get("width"), s.get("height"),
                int(d.get("format",{}).get("bit_rate") or 0))
    except Exception:
        return None

shows = {}
for ch in sorted(x for x in ROOT.iterdir() if x.is_dir() and not x.name.startswith("_")):
    for show in sorted(x for x in ch.iterdir() if x.is_dir() and not x.name.startswith("_")):
        eps = [p for p in show.rglob("*.mp4") if not p.name.startswith("._")]
        if len(eps) >= 3:
            shows[f"{ch.name}/{show.name}"] = eps

print(f"scanning {sum(len(v) for v in shows.values())} files across {len(shows)} shows", flush=True)
findings = []
for name, eps in shows.items():
    data = [(p, probe(p)) for p in eps]
    data = [(p, m) for p, m in data if m]
    if len(data) < 3:
        continue
    res_mode = Counter((m[0], m[1]) for _, m in data).most_common(1)[0][0]
    br_med = statistics.median(m[2] for _, m in data if m[2])
    for p, m in data:
        why = []
        if (m[0], m[1]) != res_mode:
            why.append(f"{m[0]}x{m[1]} vs {res_mode[0]}x{res_mode[1]}")
        if br_med and m[2] > br_med * BITRATE_FACTOR:
            why.append(f"{m[2]/1e6:.1f} Mbps vs {br_med/1e6:.1f} median")
        if why:
            findings.append((name, p.name, "; ".join(why)))
    print(f"  {name}: {len(data)} eps, mode {res_mode[0]}x{res_mode[1]}", flush=True)

print(f"\n=== {len(findings)} OUTLIERS ===", flush=True)
for show, fn, why in findings:
    print(f"  {show}\n    {fn[:60]}\n      {why}", flush=True)
