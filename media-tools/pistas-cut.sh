#!/bin/bash
# Cut the last 12 Pistas compilations at Brian's own timemarks (2026-08-31).
#
# cut-at.py always RE-ENCODES: `-c copy` can only start a piece on a keyframe
# and rounds backwards silently by up to ~5 s, which is what once made pieces
# open on the previous episode's credits. Re-encoding puts the cut exactly where
# asked. Source here is ~536 kbps, so the 800k default is a comfortable target.
#
# 024 and 030 are "don't split" - copied whole, not re-encoded, so they stay
# lossless. They keep the same "- pt01" naming so the filing step is uniform.
set -uo pipefail
cd "/Users/briantang/Downloads/Converted/Pistas de Blue y tú/_compilations"
OUT=../_reenc
mkdir -p "$OUT"
T=/Users/briantang/Downloads/Converted/_tools/cut-at.py

cut () {  # index, then cut points in seconds
  local idx="$1"; shift
  local f; f=$(ls "${idx}"-*.mp4 2>/dev/null | head -1)
  [ -z "$f" ] && { echo "!! no file for $idx"; return 1; }
  echo "### $idx  cuts: $*"
  python3 "$T" "$f" --at "$@" --outdir "$OUT" --name "$idx"
}
whole () {
  local idx="$1"
  local f; f=$(ls "${idx}"-*.mp4 2>/dev/null | head -1)
  [ -z "$f" ] && { echo "!! no file for $idx"; return 1; }
  echo "### $idx  no split - copying whole"
  cp "$f" "$OUT/${idx} - pt01.mp4"
}

cut   018 1251 2606      # 20:51, 43:26
cut   019 1181           # 19:41
cut   020 1417           # 23:37
whole 024                # don't split
cut   027 1214           # 20:14
whole 030                # don't split
cut   034 1113           # 18:33
cut   044 1159           # 19:19
cut   046 1142           # 19:02
cut   049 1695           # 28:15
cut   063 1862           # 31:02
cut   080 1786           # 29:46

echo
echo "### pieces written: $(ls -1 "$OUT"/*.mp4 2>/dev/null | wc -l | tr -d ' ') (expected 23)"
