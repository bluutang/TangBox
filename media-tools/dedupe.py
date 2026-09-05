#!/usr/bin/env python3
"""Find true duplicate episodes by audio content, not filename or duration.

Titles lie (the same episode is re-uploaded under several names) and duration
lies too (episodes cut to a fixed broadcast slot share lengths by chance). The
audio waveform does not: two files of the same episode have the same loudness
profile over time even across different encodes.

Each file is reduced to a short vector of mean audio energy per time slice,
normalised so encoding-level differences do not matter, then compared pairwise
by correlation.
"""
import subprocess, sys, math
from pathlib import Path

SRC = Path(sys.argv[1])
SLICES = 40

def envelope(p):
    """Mean absolute amplitude per slice, as a normalised vector."""
    r = subprocess.run(
        ["ffmpeg","-v","error","-i",str(p),"-ac","1","-ar","2000",
         "-f","s16le","-"], capture_output=True)
    raw = r.stdout
    if len(raw) < 4000: return None
    import array
    a = array.array("h"); a.frombytes(raw[:len(raw)//2*2])
    n = len(a) // SLICES
    if n == 0: return None
    vec=[]
    for i in range(SLICES):
        chunk = a[i*n:(i+1)*n]
        vec.append(sum(abs(x) for x in chunk)/len(chunk))
    m = sum(vec)/len(vec)
    if m == 0: return None
    return [v/m for v in vec]

def corr(a,b):
    ma, mb = sum(a)/len(a), sum(b)/len(b)
    va = sum((x-ma)**2 for x in a); vb = sum((x-mb)**2 for x in b)
    if va == 0 or vb == 0: return 0.0
    cov = sum((x-ma)*(y-mb) for x,y in zip(a,b))
    return cov/math.sqrt(va*vb)

files = sorted(SRC.glob("*.mp4"))
print(f"  fingerprinting {len(files)} files...")
fp={}
for f in files:
    e = envelope(f)
    if e: fp[f]=e
print(f"  fingerprinted {len(fp)}")

names=list(fp)
dupes=[]
for i in range(len(names)):
    for j in range(i+1,len(names)):
        c = corr(fp[names[i]], fp[names[j]])
        if c > 0.97:
            dupes.append((c, names[i], names[j]))
dupes.sort(reverse=True)
print(f"\n  {len(dupes)} pairs with audio correlation > 0.97:")
for c,a,b in dupes[:30]:
    print(f"    {c:.3f}  {a.name[:44]}")
    print(f"           {b.name[:44]}")

# --apply: quarantine one of each duplicate pair, keeping the larger file
# (same resolution, so larger means a higher bitrate).
if "--apply" in sys.argv:
    q = SRC/"_dupes"; q.mkdir(exist_ok=True)
    import shutil
    dropped=set()
    for c,a,b in dupes:
        if a in dropped or b in dropped: continue
        keep, drop = (a,b) if a.stat().st_size >= b.stat().st_size else (b,a)
        shutil.move(str(drop), str(q/drop.name))
        dropped.add(drop)
    print(f"\n  quarantined {len(dropped)} duplicates -> _dupes/")
    print(f"  unique episodes remaining: {len(list(SRC.glob('*.mp4')))}")
