#!/usr/bin/env python3
r"""Fetch the approved 2000s/late-90s commercials into _commercials/.

Curated from two YouTube playlists (448 unique videos) down to 78: 15-45 s,
toys / snacks / food / kid brands, nothing dated before 1995, and no theme
songs, intros, network idents or brand logos - Brian's brief 2026-08-31.

They land at the TOP LEVEL of _commercials/, alongside the 61 vintage ads
already there. The Disney/ and Nickelodeon/ subfolders hold network bumpers and
are left alone.

H.264 ONLY. yt-dlp's default "best" serves AV1 and the Pi 5 has no AV1 hardware
decoder - AV1 plays as a slideshow or not at all.

Every file is checked after download: yt-dlp can exit 0 having written nothing
useful, so a missing or absurdly small file is caught here rather than showing
up as a dead commercial break months later.

    python3 _tools/get-commercials.py            # dry run
    python3 _tools/get-commercials.py --apply
"""
from __future__ import annotations
import subprocess, sys, time
from pathlib import Path

DEST = Path("/Users/briantang/Downloads/Converted/_commercials")
ARCHIVE = DEST / "_archive.txt"
FMT = ("bestvideo[vcodec^=avc1][height<=720]+bestaudio[ext=m4a]/"
       "best[vcodec^=avc1][height<=720]/best[height<=720]")

# (video id, expected seconds, title)
CLIPS = [
  ("3Boqg792QOk", 31, "Animorphs Transformers Action Figure Alien Invasion Hasbro Toy TV Comm"),
  ("E6VSQRlLEc0", 31, "Baby So Real Doll Commercial (1995)"),
  ("usNnvVeJgJc", 31, "Bananas in Pajamas  - Toys Dolls  - Tomy Commercial (1996)"),
  ("Ee08qLLuSkg", 37, "Bratz First Edition Commercial 2001"),
  ("GXTPxUl3qNY", 31, "Chia Pet (2005) feat. Garfield"),
  ("wNYXh-F3kgM", 33, "Dawson Dunbar - Hot Wheels Super Slammers Commercial (2008)"),
  ("EMvN9qKvsIg", 34, "First Wii commercial"),
  ("6xjqBei1Mj0", 33, "GameFly Commercial"),
  ("30DewN99MIQ", 33, "GUITAR HERO® WORLD TOUR ad featuring Kobe Bryant, Alex Rodriguez, Tony"),
  ("LZK6PUOgzIY", 37, "Hasbro Lost World Jurassic Park Commercial 1997"),
  ("9FTaGWqrYkw", 30, "Hulk Hands (2003) commercial"),
  ("xuK7xLJW--k", 16, "Kirby's Block Ball - Nintendo GameBoy - Game Boy Commercial (1996)"),
  ("O1g3UMjCA-A", 31, "Lego City 2008 Coast Guard Collection"),
  ("CVt1-FoWS2c", 31, "Lego City 2008 Fire Boat"),
  ("8uqh78cjnMs", 16, "Lego City 2008 Giant Crane"),
  ("T-HVmEQxhSY", 31, "Mario & Sonic at the Olympic Games (Wii) commercial"),
  ("JjV-8atcsns", 31, "Mighty Morphin Power Rangers - Talkin' Rangers & Lord Zedd Toy Commerc"),
  ("Q0d3Xq-yXn4", 32, "Nerf Longshot Commercial"),
  ("RgoukS3VyGU", 32, "Power Rangers Lost Galaxy - \"Magna Defender Collection\" Bandai Toy Com"),
  ("Dtl9ctxrfrs", 31, "RadioShack Toy Sale Commercial (2001)"),
  ("QFfP2tda8IU", 40, "Rock Band Wii TV Spot"),
  ("45Lt6NnRQdk", 31, "Super Mario Strikers Commercial"),
  ("1xYHyNq8_BI", 16, "Airheads Ice Age The Meltdown Commercial"),
  ("YKXNYMmclUE", 16, "Cheerios cereals (Nestle): Ice Age commercial"),
  ("xBGpRLjNnzM", 31, "Cocoa Puffs Commercial"),
  ("8vxyEM42kCM", 32, "Corn Pops \"Dragon Dreams\""),
  ("Vzxd_T0slzg", 31, "Danimals Crush Cup Commercial"),
  ("Ts7Pk_Svi8Y", 32, "Dexter's Lab Gogurt Commercial"),
  ("sEkEbKC8LZY", 31, "Eggo Waffle Commercial"),
  ("6FG2NNbYpCo", 37, "Fruit Gushers Commercial 1998"),
  ("82yZVB7IDlE", 32, "Got Milk? Commercial"),
  ("qHa03NoJoC8", 31, "Gripz Snacks (amazing trick) (2005) commercial"),
  ("SFKk7Wvv3LE", 31, "Honey Bunches of Oates Cereal Bars Television Commercial 2005"),
  ("RL9uFxfYOU0", 31, "Honey Nut Cheerios - Barber Commercial"),
  ("jpJPI_T2MIw", 31, "Honey Nut Cheerios Commercial"),
  ("Bpol6LDuJbU", 31, "Hostess Cupcakes - Shark Commercial  - Where's the Cream Filling (1997"),
  ("cFeBdbzXlCs", 16, "Jolly Rancher Gel Snacks Commercial 2001"),
  ("3JUA8VhfwrA", 32, "Kid Cuisine - Planet 51 commercial"),
  ("ofNVXMvSRPw", 32, "Lucky Charms commercial (2007)"),
  ("if4jDYOcOpM", 30, "Lunchables commercial (2005)"),
  ("11IG14Sy_7s", 31, "Nesquik Commercial (2003)"),
  ("vTOiFkxrVPI", 32, "Old Rice Krispies Commercial"),
  ("bLaWl6DZE24", 30, "Pop Tarts Commercial - Freedom"),
  ("caomY5CAjwI", 31, "Reese's Puffs Rap"),
  ("k0xfw7Tz1BU", 31, "Reeses Puffs Commercial"),
  ("UKfKK4ViozA", 16, "Ring Pops Candy Commercial 1998"),
  ("spFoAnAXusw", 33, "SpaghettiOs - SpaghettiO-O-Os (2004)"),
  ("wYX_zhlTDr8", 35, "Starburst Commercial"),
  ("VJwFUNHtCJQ", 41, "Super Mario Got Milk Commercial"),
  ("pBQnkehGlT8", 31, "Tang Commercial 2000"),
  ("qRaA3lhXb8Q", 31, "Yoplait Go-Gurt commercial (2000)"),
  ("-A0I557Nx3M", 31, "Yoplait Trix Yogurt Commerical  - General Mills (1996)"),
  ("PiqoSiEXTEw", 31, "2004 Muppets Pizza Hut Commercial"),
  ("kRB1aaOnZV8", 30, "BK Big Kids Meal 2000"),
  ("ejdE3n4dLLg", 31, "BK Shake 'em Up Fries (2002)"),
  ("xu_bE7g2wqM", 31, "BK's Tiny Hands Commercial"),
  ("LTzdy6Xa_WM", 31, "Burger King Shake em' Up Fries The Simpsons Talking Wrist Watches TV C"),
  ("CMGPj8szs_c", 31, "Commercial - McDonald's Summer Treats (2000)"),
  ("GEVMkdScUZc", 32, "Jack in the Box Jack at Burger King 2009 Commercial"),
  ("2iZh5WyHHxA", 33, "McDonald's Monsters vs. Aliens Commercial 2009"),
  ("7gMZ62PsvRM", 32, "SpongeBob Burger King"),
  ("6MZd4BJdiMg", 16, "Disney Channel | Express Yourself | 2004 | Lizzie McGuire"),
  ("4sTt0s_zrZI", 31, "Disney's Toontown Online Commercial (2005)"),
  ("_bIcH14ThH0", 31, "Looney Tunes CN Return 2009 Marathon Promo"),
  ("jgy6OuSviBI", 30, "old toontown commercial"),
  ("nOAg9QtgQkQ", 31, "That's Warner Bros - Cartoon Looney Tunes Toons Commercial (1996)"),
  ("YB94fbBWSV4", 33, "Toon Disney Light-Bulb change"),
  ("VuAwm_AoWZ0", 15, "Chuck E  Cheese commercial (2007)"),
  ("jb7gpHP8_vI", 16, "Chuck E Chees's | Television Commercial | 2003 | Who You Gonna Call"),
  ("vW_5gYN52g8", 16, "Chuck E Cheese: Raining Tokens (2007)"),
  ("OkgtHr0pWhU", 16, "Duracell bunny ad 2003"),
  ("OP6kKc-0FSY", 15, "Lindsay Lohan in a Jello Commercial from c.1996"),
  ("KXf6X_BEMiw", 31, "Luvs Diapers Balloon Commercial (2000)"),
  ("LeconSHgw2o", 16, "Skechers Twinkle Toes | Television Commercial | 2009"),
  ("psuaF5DMiH0", 30, "Smokey the Bear Commercial"),
  ("UNH3Xr4rF-o", 30, "Toy Story Disney on Ice 90s Commercial (1999)"),
  ("VjolNti1uyQ", 28, "Wendy's Kids Meal Snoopy 2000"),
  ("PnYadw5mXjM", 31, "Zoobooks | Television Commercial | 2009"),
]


def main() -> int:
    apply = "--apply" in sys.argv
    print(f"  {len(CLIPS)} commercials, {sum(c[1] for c in CLIPS)/60:.1f} min -> {DEST}")
    if not apply:
        print("  (dry run - pass --apply)")
        return 0
    DEST.mkdir(parents=True, exist_ok=True)
    before = {p.name for p in DEST.glob("*.mp4")}
    ok = fail = 0
    bad = []
    for i, (vid, want, title) in enumerate(CLIPS, 1):
        r = subprocess.run([
            "yt-dlp", "--no-warnings", "--ignore-errors", "--no-abort-on-error",
            "-f", FMT, "--merge-output-format", "mp4",
            "--download-archive", str(ARCHIVE), "--no-overwrites",
            "--retries", "5", "--fragment-retries", "5", "--socket-timeout", "30",
            "--sleep-requests", "1",
            "-o", str(DEST / "%(title)s.%(ext)s"),
            f"https://www.youtube.com/watch?v={vid}",
        ], capture_output=True, text=True)
        now = {p.name for p in DEST.glob("*.mp4")}
        new = now - before
        if new:
            f = DEST / new.pop()
            # a valid-looking but tiny file is the failure mode to catch here
            if f.stat().st_size < 200_000:
                fail += 1; bad.append((vid, title, f"only {f.stat().st_size} bytes"))
                f.unlink()
            else:
                ok += 1
                print(f"  [{i:02d}/{len(CLIPS)}] ok  {f.stat().st_size/1e6:5.1f} MB  {title[:52]}", flush=True)
        else:
            # already in the archive from an earlier run, or it failed
            err = (r.stderr or "").strip().splitlines()
            if r.returncode == 0:
                print(f"  [{i:02d}/{len(CLIPS)}] already had it  {title[:52]}", flush=True)
            else:
                fail += 1; bad.append((vid, title, err[-1][:90] if err else "unknown"))
                print(f"  [{i:02d}/{len(CLIPS)}] FAIL  {title[:52]}", flush=True)
        before = now
        time.sleep(1)
    print(f"\n  downloaded {ok}, failed {fail}")
    for vid, title, why in bad:
        print(f"    {vid}  {title[:46]}  {why}")
    print(f"  _commercials now holds {len(list(DEST.glob('*.mp4')))} clips at the top level")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
