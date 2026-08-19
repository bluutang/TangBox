#!/usr/bin/env bash
#
# Watch a clip on the TV without disturbing anything permanently.
#
# Usage:
#   ./scripts/preview-clip.sh nostalgiabox/assets/power_off.mp4       # 3 plays
#   ./scripts/preview-clip.sh nostalgiabox/assets/power_on.mp4 5      # 5 plays
#
# WHY THIS EXISTS
# ---------------
# The sign-off animation only plays as part of an actual shutdown, so every look
# at it used to mean halting the Pi and walking to the room to press the power
# button. Tuning it took several rounds. This stops TangBox, plays the clip a
# few times, and hands the screen straight back - no halt, no button.
#
# It plays through the SAME CRT shader TangBox uses, so what you see is what the
# box will show: rounded corners, vignette and all. A clip previewed without the
# shader looks meaningfully different, which would defeat the point.
#
set -euo pipefail

CLIP="${1:-}"
REPEATS="${2:-3}"

if [[ -z "${CLIP}" ]]; then
  sed -n '3,9p' "$0"
  exit 2
fi
[[ -f "${CLIP}" ]] || { echo "error: no such clip: ${CLIP}" >&2; exit 1; }

CACHE_HOME="${XDG_CACHE_HOME:-${HOME}/.cache}"
SHADER="${CACHE_HOME}/nostalgiabox/crt.glsl"

was_running=0
if systemctl is-active --quiet tangbox 2>/dev/null; then
  was_running=1
  sudo systemctl stop tangbox
  sleep 1
fi

# Hand the screen back even if mpv fails or the user interrupts - leaving the TV
# on a dead console would be a worse outcome than not seeing the clip.
restore() {
  if [[ "${was_running}" -eq 1 ]]; then
    sudo systemctl start tangbox
  fi
}
trap restore EXIT

opts=(--really-quiet --fullscreen --no-osc --drm-mode=1920x1080@60)
if [[ -f "${SHADER}" ]]; then
  opts+=(--glsl-shaders="${SHADER}")
else
  echo "note: no CRT shader at ${SHADER}; previewing without it" >&2
fi

for _ in $(seq 1 "${REPEATS}"); do
  mpv "${opts[@]}" "${CLIP}" || true
  sleep 1.2
done
