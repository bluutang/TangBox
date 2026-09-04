#!/usr/bin/env python3
r"""Sort show folders into the channel folders the box expects.

config.pi.yaml maps each channel to ONE folder, and the shows sit inside it:

    /media/tangbox/NickClasico/Rugrats/Season 01/Rugrats - S01E01.mp4
                   ^ path:     ^ one "show" to ShowOrder

That nesting is structural, not tidiness: `episode_order: sequential` bags the
folders directly under path:, so getting it wrong makes a channel either find no
episodes or treat every episode as its own show.

A show is only moved once it is READY - it has episodes outside _staging. Shows
still downloading are listed and left alone, so this is safe to run at any time.

    organize-channels.py             # plan only
    organize-channels.py --apply     # move them
"""
from __future__ import annotations
import shutil, sys, unicodedata
from pathlib import Path


def nfc(name: str) -> str:
    """Compare folder names in ONE normal form.

    macOS stores some of these decomposed ("u" plus a combining accent) and
    others composed, so plain string equality says "Pistas de Blue y tu" is not
    itself. Path.exists() hides this - the filesystem matches either form - so
    the mismatch only shows up in set arithmetic, which is exactly where it bit:
    an assigned show was reported as unassigned. Same family of bug the
    config.pi.yaml comment warns about for channel `path:` values.
    """
    return unicodedata.normalize("NFC", name)

ROOT = Path("/Users/briantang/Downloads/Converted")

# channel folder (must match `path:` in config.pi.yaml) -> show folders on disk
CHANNELS: dict[str, list[str]] = {
    "PBSPequenos":    ["Plaza Sésamo", "Barney el Dinosaurio", "Teletubbies"],
    "PBSKids":        ["Daniel Tigre", "Jorge el Curioso"],
    "PBSEscolar":     ["Arthur", "Clifford", "El Autobús Mágico"],
    "NickJr":         ["Franklin", "Pistas de Blue y tú", "Dora la Exploradora"],
    "NickClasico":    ["Rugrats Aventuras en Pañales", "¡Oye Arnold", "Doug",
                       "Rocket Power"],
    "NickModerno":    ["Bob Esponja", "Las Aventuras de Jimmy Neutron El Niño Genio"],
    "NickAccion":     ["Avatar La leyenda de Aang", "Avatar La Leyenda de Aang",
                       "La Leyenda de Korra"],
    "DisneyJr":       ["Bluey", "Spidey y sus Sorprendentes Amigos",
                       "Bear in the Big Blue House", "Rolie Polie Olie"],
    "Disney":         ["Kim Possible", "Recreo", "Pepper Ann"],
    "DisneyAventura": ["Patoaventuras", "Lilo y Stitch La Serie",
                       "La Leyenda de los Tres Caballeros"],
    # Street Sharks is 1994 DIC syndication, not Disney - filed here for tone
    # and age (7+) because the lineup has no home for syndicated action.
    "DisneyAccion":   ["Tu amigo y vecino Spider-Man", "Jake Long El Dragón occidental",
                       "Street Sharks",
                       # Both are Disney TV Animation and darker than the rest of
                       # the Disney block, which is what 7+ is for.
                       "Gargoyles", "Mighty Ducks"],
    "CartoonNetwork": ["El laboratorio de Dexter", "Ed Edd y Eddy", "Escandalosos",
                       "KND Los chicos del barrio"],
    "AppleSnoopy":    ["De campamento con Snoopy",
                       "Snoopy el astronauta Buscando vida en el espacio",
                       "El show de Snoopy"],
    "AppleCuentos":   ["Lago tranquilo", "Sapo y Sepo",
                       "El niño lobo y la fábrica del todo", "Pato y Ganso"],
    "NetflixKids":    ["Misterios Animales", "My Melody Kuromi", "Concierge Pokémon"],
    "NetflixCuentos": ["Los guardaespíritus del bosque", "Tibucán", "Maya y los tres",
                       "Dr Seuss Pez rojo pez azul"],
    "Anime":          ["Sailor Moon", "Dragon Ball Z", "Sailor Moon Películas"],
    # Not television - YouTube teaching material, no network, breaks: false.
    # "Ms. Nenna" is the creator of the Spanish Basics videos.
    "Aprende":        ["Ms. Nenna", "Aprende Peque con Isa"],
    "Ejercicio":      ["Cosmic Kids Yoga"],
    # The show is named for the channel's creator, Uncle Calvin. The CHANNEL
    # folder stays ASCII "Cantones" - macOS and Linux disagree on how accents
    # are encoded, and only the path has to survive both.
    "Cantones":       ["Uncle Calvin"],
    # Digimon and Pokemon are anime but skew far younger than Sailor Moon and
    # Dragon Ball Z, so they get their own block rather than sitting on a 10+
    # channel. One network per channel, age splitting each block.
    "AnimeKids":      ["Digimon Adventure", "Pokémon"],
    # Cantonese TVB live action - not animation, not a learning channel.
    "JourneyWest":    ["Journey to the West"],
}


def finished_episodes(show: Path) -> int:
    """Episodes in real season folders - NOT in any working directory.

    Counting everything outside _staging was wrong: it also counted _review
    (detect-breaks scratch cuts) and _untrimmed-source, so a show still being
    downloaded looked finished. Moving one of those would strand the queue,
    which writes to Converted/<Show>/ and would simply make a new empty folder
    and re-download the lot. Any underscore-prefixed directory is working
    space, never output.
    """
    return len([p for p in show.rglob("*.mp4")
                if not any(part.startswith("_") for part in p.relative_to(show).parts)])


def main() -> int:
    apply = "--apply" in sys.argv
    assigned = {nfc(s) for shows in CHANNELS.values() for s in shows}
    on_disk = {nfc(d.name) for d in ROOT.iterdir()
               if d.is_dir() and not d.name.startswith("_") and d.name not in CHANNELS}

    ready, waiting, missing = [], [], []
    for chan, shows in CHANNELS.items():
        for name in shows:
            src = ROOT / name
            if not src.exists():
                missing.append(name); continue
            # A show is ready only when it is FINISHED, not merely started.
            # Episodes left in _staging still need splitting or naming, and the
            # tools that do that look for ROOT/<show>/_staging - so filing the
            # show first puts them somewhere those tools cannot find, quietly.
            # Order is: download -> split/join -> name -> file.
            pending = len(list((src / "_staging").glob("*.mp4"))) \
                if (src / "_staging").exists() else 0
            (ready if finished_episodes(src) and not pending
             else waiting).append((chan, src))

    print(f"  ready to move : {len(ready)}")
    print(f"  still working : {len(waiting)}  (no episodes outside _staging yet)")
    print(f"  not on disk   : {len(missing)}")
    unassigned = on_disk - assigned
    if unassigned:
        print(f"\n  ⚠ ON DISK BUT NOT IN ANY CHANNEL ({len(unassigned)}) - these would be left behind:")
        for n in sorted(unassigned):
            print(f"      {n}")
    if missing:
        print(f"\n  in the map but not on disk yet:")
        for n in sorted(missing):
            print(f"      {n}")

    if ready:
        print(f"\n  would move:")
        for chan, src in sorted(ready, key=lambda r: (r[0], r[1].name)):
            print(f"      {src.name}  ->  {chan}/{src.name}   "
                  f"({finished_episodes(src)} episodes)")
    if waiting:
        print(f"\n  waiting on downloads or naming:")
        for chan, src in sorted(waiting, key=lambda r: (r[0], r[1].name))[:12]:
            print(f"      {src.name}  ({chan})")
        if len(waiting) > 12:
            print(f"      ... and {len(waiting) - 12} more")

    if not apply:
        print("\n  (plan only - pass --apply to move)")
        return 0

    for chan, src in ready:
        dst_dir = ROOT / chan
        dst_dir.mkdir(exist_ok=True)
        dst = dst_dir / src.name
        if dst.exists():
            print(f"  SKIP exists: {chan}/{src.name}"); continue
        shutil.move(str(src), str(dst))
        print(f"  moved {src.name} -> {chan}/")
    print(f"\n  moved {len(ready)} shows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
