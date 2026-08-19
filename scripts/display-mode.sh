#!/usr/bin/env bash
#
# Pin the HDMI output mode. Defaults to 1920x1080@60.
#
# Usage:
#   sudo ./scripts/display-mode.sh                 # force 1080p60
#   sudo ./scripts/display-mode.sh 1280x720@60     # something else
#   ./scripts/display-mode.sh --status             # report, change nothing
#   sudo ./scripts/display-mode.sh --undo          # let the TV decide again
#
# WHY YOU WOULD WANT LESS THAN 4K
# --------------------------------
# The Pi came up driving this TV at 3840x2160@30 - 4K, thirty hertz - because
# that is what the telly advertised and the kernel took it. For a box showing
# 480-line cartoons that is the worst of both worlds:
#
#   * No detail to gain. You cannot upscale your way to information that was
#     never in a 480-line source; it just scales the same pixels further.
#   * Half the refresh rate. 1080p60 is twice as smooth as 4Kp30, and motion is
#     the thing you actually notice on a TV.
#   * The 1280x720 overlay canvas gets stretched 3x instead of 1.5x, which is
#     why the HUD text stayed soft no matter what was done to its weight, its
#     letter spacing or its glow.
#   * The GPU scales every frame and runs the CRT shader over four times the
#     pixels, for nothing.
#
# Same file as quiet-boot.sh edits, so the same brutal rule: cmdline.txt must be
# EXACTLY ONE LINE or the Pi will not boot, and recovery means pulling the SD
# card. Enforced in code, tested in tests/test_display_mode.py.
#
set -euo pipefail

BOOT_DIR="${BOOT_DIR:-}"
if [[ -z "${BOOT_DIR}" ]]; then
  if [[ -d /boot/firmware ]]; then BOOT_DIR=/boot/firmware; else BOOT_DIR=/boot; fi
fi

CMDLINE="${BOOT_DIR}/cmdline.txt"
BACKUP="${CMDLINE}.tangbox-display-backup"

# HDMI0 on a Pi 5 - the port nearest the power connector, which is the one this
# project uses. HDMI-A-2 would be the second port.
CONNECTOR="HDMI-A-1"
MODE="1920x1080@60"

ACTION=apply
for arg in "$@"; do
  case "$arg" in
    --undo)   ACTION=undo ;;
    --status) ACTION=status ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    --*) echo "unknown option: $arg" >&2; exit 2 ;;
    *)   MODE="$arg" ;;
  esac
done

die() { echo "error: $*" >&2; exit 1; }

[[ -f "${CMDLINE}" ]] || die "${CMDLINE} not found (BOOT_DIR=${BOOT_DIR})"

# Reject anything that isn't WIDTHxHEIGHT@RATE. A mode the kernel cannot parse
# is silently ignored, which would look exactly like the script not working.
if [[ "${ACTION}" == "apply" ]]; then
  [[ "${MODE}" =~ ^[0-9]{3,5}x[0-9]{3,5}@[0-9]{2,3}$ ]] \
    || die "'${MODE}' is not a mode. Expected something like 1920x1080@60"
fi

SUDO=""
[[ -w "${BOOT_DIR}" ]] || SUDO="sudo"

if [[ "${ACTION}" == "status" ]]; then
  echo "boot dir: ${BOOT_DIR}"
  current="$(grep -o "video=${CONNECTOR}:[^ ]*" "${CMDLINE}" || true)"
  if [[ -n "${current}" ]]; then
    echo "pinned:   ${current}"
  else
    echo "pinned:   no (the TV's preferred mode is used, whatever that is)"
  fi
  [[ -f "${BACKUP}" ]] && echo "backup:   ${BACKUP}" || echo "backup:   none"
  exit 0
fi

if [[ "${ACTION}" == "undo" ]]; then
  [[ -f "${BACKUP}" ]] || die "no backup at ${BACKUP}; nothing to undo"
  ${SUDO} cp "${BACKUP}" "${CMDLINE}"
  echo "==> Restored. The TV picks the mode again after a reboot."
  exit 0
fi

# Back up ONCE, so --undo always reaches the pristine original rather than a
# previous run's output.
[[ -f "${BACKUP}" ]] || ${SUDO} cp "${CMDLINE}" "${BACKUP}"

line="$(tr '\n' ' ' < "${CMDLINE}" | tr -s ' ')"
line="${line#"${line%%[![:space:]]*}"}"
line="${line%"${line##*[![:space:]]}"}"

# Drop any existing pin first, so changing your mind doesn't leave two video=
# parameters fighting over the same connector.
cleaned=""
for word in ${line}; do
  case "${word}" in
    video=${CONNECTOR}:*) ;;
    *) cleaned="${cleaned:+${cleaned} }${word}" ;;
  esac
done
line="${cleaned} video=${CONNECTOR}:${MODE}"

# The guard this script exists for.
case "${line}" in
  *$'\n'*) die "refusing to write: result contains a newline" ;;
esac
[[ -n "${line}" ]] || die "refusing to write an empty cmdline.txt"

printf '%s\n' "${line}" | ${SUDO} tee "${CMDLINE}" > /dev/null
echo "==> cmdline.txt: display pinned to ${CONNECTOR} ${MODE}"

cat <<EOF

==> Reboot to apply:  sudo systemctl reboot

To let the TV choose again:  ${SUDO:+sudo }$0 --undo
Backup:                      ${BACKUP}
EOF
