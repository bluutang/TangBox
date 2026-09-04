#!/usr/bin/env python3
r"""Fetch the 52 Xiaolin Showdown files from Brian's shared Google Drive folder.

Files are pulled ONE BY ONE by id, not with `gdown --folder`: that path caps at
50 files and would silently leave two behind on a 52-episode series.

Every file's expected byte size is recorded here from the Drive listing and
checked after download. gdown exits 0 on a truncated transfer and on Google's
"quota exceeded" HTML page, both of which land as a small valid-looking file -
the same shape as the zero-byte curl failure and the 1-of-50 archive fetch.
Size is the only thing that catches it.

    python3 _tools/get-xiaolin.py            # what it would do
    python3 _tools/get-xiaolin.py --apply
"""
from __future__ import annotations
import subprocess, sys, time
from pathlib import Path

DEST = Path("/Users/briantang/Downloads/Converted/CartoonNetwork/Xiaolin Showdown/_staging")
GDOWN = Path("/Users/briantang/Downloads/Converted/_tools/.venv/bin/gdown")

# (episode number, drive id, expected bytes)
FILES = [
 (1,"1ihXKkm_LFioyxEcEJUuxYT2hSunC9u9i",314415458),(2,"11RUrWR3DZcEYinwDonCy1ERjAz1tGzgk",365507974),
 (3,"17-Pa4W7TTGIxegViUoblc5eraoMkIBFf",302304265),(4,"1UDALiDfwY-OV_bWU8URj4oxS4cg_UTX3",320639318),
 (5,"1eZS-nhI3L3-Saf5r4rl5kSuH_Nwk72Nv",299529860),(6,"1XFQqfwuGMFGyylYm-0BUah-f0Gr6WcJq",329493069),
 (7,"1LnAoA36eZZ3PgLIdunByK90bkhzAM1kV",287721473),(8,"11eaXwt2-OFKn9VVeLWkkF04RJ-exx45Q",329189855),
 (9,"1iaQ4jbJa_jEV7WZHimpqjaIi-hfFXWcy",324713077),(10,"18AIJqx1SF6JkOgw7hJ-z6VMyYp_cgGbr",339486286),
 (11,"1dSlPCF0mK8bDmocfbezUF2mx-N1HWMvr",335182885),(12,"1vav9DxvaMJ1jWIZFj4Zm6sFiDZ2cec84",362008811),
 (13,"1hLMDmRwcdPk1jdMauXh6JukJejvmGgLc",309472988),(14,"1EuU31dFpYKj8juYuh2xp_iLSnMqu58i8",466099474),
 (15,"150aE4Qs5fIq-67ou3t0knwFeYPx8udpJ",457553540),(16,"1IyGEydl62cgw4cdA-GdDFVlXIqkikUhK",527976555),
 (17,"1rHNXb1k8HMgXX35Ja-1h5BWHb5m_Ansq",319283171),(18,"1edRycnYg8wD88wN_ay-WCaTLA5Svbohh",431543941),
 (19,"1JMkx4iBd74RegUNcbn6P6yNkUZRJRJTL",454155702),(20,"10tRVSDxuUkzGfy3whUbv70L_3tIU4zww",443972224),
 (21,"1b9GTfzihFeqbMXSO8yRDwga2JsD-L36i",520692340),(22,"1pNbPsllM4mPzNS7dBdO1zHqid0bii84f",358382479),
 (23,"1EI4smeI98AvmwyPFCVaYblc5owVuyw4P",627983021),(24,"1gUAva0XldOJUiO6X-bD760XOJUWNbin-",463274375),
 (25,"1qcl_YQfxq0aQ2wkyl1pdFFkeqII_6jeV",423520510),(26,"1ensJUnK_7iN2fuceKS0FnIeS5ziGmWcj",422387431),
 (27,"1wIk_gBrFJLKn-3klKCYcl3K5UEChDgHm",464122496),(28,"11xACPAjE5byoEakiEO638nhyhnc_cdUl",474855630),
 (29,"1Z9Lb71uoLif3qIA9FSr-qMuVCffnFgid",485748512),(30,"1g9PuYgs-J7_7IF7KJbZt5qbYRBXUFOMo",494793271),
 (31,"1Gs_IpvjGbCW7OMx9p_Kz1Q2iDBE6QHis",442016435),(32,"17ejafNgei0GWaMf5C8P2e5uaaX3b_rJs",493511764),
 (33,"1wt3hGeBYyDVGgaAMO9W0EnW6f9DJZuwP",475739825),(34,"1aCyVxXR-8LxqXblgIC3saF_hrPH34eDR",433380869),
 (35,"1kxeCv5nReoDe61XmrZwQSM_9HhEnEuH6",538829213),(36,"169Ly9PGQ136D4QU8j8J-Cbe3EfUZuRlo",388670358),
 (37,"13G4-4MAY2Uc14eyyWsSIMX2ag48PeGaf",543067065),(38,"1mtikm2PIC33-8a-znUizbW9FTWzZ80La",414753302),
 (39,"1XzIdYpeoVKPmPr1twEIxJddHXStuhZHg",454393856),(40,"19yNwXzL42thApTZWqf4bUI2n1DF1dyLH",495913950),
 (41,"14EjCSa0mJ3hSEg8DG5c1F8jEKqF8dyai",525643681),(42,"15ILgRAYPgScwgMM7DxK-PpVkhYkgc4If",497160580),
 (43,"1YKVtBEjMFlfx_Lg-3l9QzKtXmE9j732c",377948439),(44,"1nDC-WFWIqlfDeqrGTi6cu95P8c3gHb42",552949629),
 (45,"1jh1pVbkP-Yi82gK2hTRdzFiIceNx9H_M",452726929),(46,"1lBQyt3dUXgior3YjpQ3n5FOPq0iqSNJx",423291022),
 (47,"1HIwgb-Ob1Wea25WorCqyAhVn8ZfZGTzU",406076511),(48,"1dzv4lGSdRN7sxXU-0wLA4JC4qIRttx4w",509795192),
 (49,"1YeWXAFZ0dG2NUs6KJ_E2FWrxNDBoXoym",446339670),(50,"1UttcgGQugNUM6Ocl5MISAtITt5WAFkid",531136149),
 (51,"1NH_y-k-fAgWHu9mn47Q9Sfvg9cHqupoH",413424218),(52,"1WQKFv2EwnrhUs-oh2TVV7WPV7vQ9qrtf",533120282),
]

def main() -> int:
    apply = "--apply" in sys.argv
    total = sum(f[2] for f in FILES)
    print(f"  {len(FILES)} files, {total/1e9:.1f} GB -> {DEST}")
    if not apply:
        print("  (dry run - pass --apply)"); return 0
    DEST.mkdir(parents=True, exist_ok=True)
    done = skipped = failed = 0
    bad = []
    for n, fid, want in FILES:
        dst = DEST / f"{n:02d}.mp4"
        if dst.exists() and dst.stat().st_size == want:
            skipped += 1; print(f"  [{n:02d}/52] already complete, skipping"); continue
        if dst.exists():
            print(f"  [{n:02d}/52] wrong size on disk, refetching"); dst.unlink()
        # gdown 6.x takes the id POSITIONALLY; the old --id flag was removed and
        # passing it makes every call exit on a usage error, writing nothing.
        r = subprocess.run([str(GDOWN), fid, "-O", str(dst), "--quiet", "--continue"],
                           capture_output=True, text=True)
        got = dst.stat().st_size if dst.exists() else 0
        # Drive throttles after a burst: files 1-32 came down fine, then 33-52
        # ALL failed at once with "or have had many accesses". Retry with backoff
        # and pace the whole run rather than treating a throttle as a dead file.
        tries = 1
        while got != want and tries <= 3:
            wait = 30 * tries
            print(f"  [{n:02d}/52] throttled, waiting {wait}s (try {tries}/3)", flush=True)
            time.sleep(wait)
            if dst.exists(): dst.unlink()
            r = subprocess.run([str(GDOWN), fid, "-O", str(dst), "--quiet", "--continue"],
                               capture_output=True, text=True)
            got = dst.stat().st_size if dst.exists() else 0
            tries += 1
        if got == want:
            done += 1
            print(f"  [{n:02d}/52] ok  {got/1e6:6.1f} MB", flush=True)
            time.sleep(4)                     # pace the run
        else:
            failed += 1
            bad.append((n, want, got, (r.stderr or "").strip()[:100]))
            print(f"  [{n:02d}/52] FAIL wanted {want} got {got}", flush=True)
            if dst.exists(): dst.unlink()      # never leave a partial behind
    print(f"\n  downloaded {done}, already had {skipped}, FAILED {failed}")
    for n, w, g, e in bad:
        print(f"    {n:02d}: wanted {w} got {g}  {e}")
    return 1 if failed else 0

if __name__ == "__main__":
    raise SystemExit(main())
