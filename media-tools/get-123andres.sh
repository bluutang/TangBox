#!/bin/bash
# Fetch the four 123 Andrés playlists into TWO shows under Aprende.
#
# The four playlists share 12 videos: 9 among the three song lists, and 3 more
# between the alphabet list and the song lists (Abecedario, Ge/Gi, Baile de las
# Vocales). Rather than write a dedupe pass, this leans on get-playlist.sh's
# --download-archive: LETRAS is fetched first, then its archive is COPIED to
# CANCIONES as a starting point, so every id already taken by Letras is skipped.
# The three shared videos are alphabet content, so Letras is the right home.
#
# One entry in the PreKinder list is dead (no title, no duration - deleted or
# private). --ignore-errors lets the run continue past it.
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
LETRAS="Aprende/123 Andrés - Letras"
CANCIONES="Aprende/123 Andrés - Canciones"

A=PLk8FdP6psfMqPrFj2ivjxhlpwYHx6DKBL          # Canta las Letras          41
B=PLk8FdP6psfMoQQa7bdmug81AEXX92RmuY          # Canciones divertidas      23
C=PLk8FdP6psfMqwGue3DqL8DnIj_sWsldEg          # Conocimiento PreKinder    14
D=PLk8FdP6psfMpjrLcxjUynTy1QRCRXM21O          # Back to School            12

echo "### 1/4  LETRAS  (alphabet, 41 videos)"
bash _tools/get-playlist.sh "$LETRAS" "https://www.youtube.com/playlist?list=$A"

# Seed the Canciones archive so the 3 alphabet overlaps are never fetched twice.
mkdir -p "$ROOT/$CANCIONES"
cp "$ROOT/$LETRAS/_archive.txt" "$ROOT/$CANCIONES/_archive.txt"

# Brian's exclusions, 2026-08-31. Pre-seeding the archive is how yt-dlp is told
# to skip a video: it never fetches an id the archive already names.
#   L7Hmo3zi9Uw  "Salta, salta! en vivo LIVE especial para Wiggle Out Loud 2020"
#                A 5:30 live concert recording. The STUDIO version of the same
#                song (oBiFqDyAZGA, 3:00, the Latin Grammy winner) is a separate
#                video and is still fetched, so the song itself is not lost.
#   z6-YcvY9JQE  "El Motor - LIVE version - kids music virtual concert"
#                2:49 live concert recording. Same reasoning.
for SKIP in L7Hmo3zi9Uw z6-YcvY9JQE; do
  echo "youtube $SKIP" >> "$ROOT/$CANCIONES/_archive.txt"
  echo "### skipping $SKIP by Brian's request"
done
echo "### seeded Canciones archive with $(wc -l < "$ROOT/$CANCIONES/_archive.txt" | tr -d ' ') ids (Letras + skips)"

i=2
for PL in "$B" "$C" "$D"; do
  echo "### $i/4  CANCIONES  playlist $PL"
  bash _tools/get-playlist.sh "$CANCIONES" "https://www.youtube.com/playlist?list=$PL"
  i=$((i+1))
done

echo
echo "### DONE"
echo "  Letras   : $(find "$ROOT/$LETRAS/_staging"    -name '*.mp4' ! -name '*.f[0-9]*.mp4' 2>/dev/null | wc -l | tr -d ' ') files"
echo "  Canciones: $(find "$ROOT/$CANCIONES/_staging" -name '*.mp4' ! -name '*.f[0-9]*.mp4' 2>/dev/null | wc -l | tr -d ' ') files"
