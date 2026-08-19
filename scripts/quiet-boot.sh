#!/usr/bin/env bash
#
# Hide the Raspberry Pi's boot messages so the TV goes from black to TangBox
# instead of scrolling twenty seconds of kernel log.
#
# Usage:
#   sudo ./scripts/quiet-boot.sh            # apply
#   sudo ./scripts/quiet-boot.sh --undo     # restore the originals
#   ./scripts/quiet-boot.sh --status        # report, change nothing
#
# WHY THIS IS A SCRIPT AND NOT A NOTE SAYING "EDIT cmdline.txt"
# -------------------------------------------------------------
# cmdline.txt must be EXACTLY ONE LINE. A stray newline and the Pi will not
# boot at all - and recovery means shutting down, pulling the SD card out of
# the case, and editing it on another computer. That is a bad thing to risk on
# a tired hand-edit, so the rule is enforced in code and tested on a laptop
# (tests/test_quiet_boot.py) against a throwaway directory.
#
# Everything here is reversible: the originals are copied to
# *.tangbox-backup before anything is written, and --undo puts them back
# byte-for-byte.
#
set -euo pipefail

# Overridable so the tests can run against a temp dir instead of the real thing.
BOOT_DIR="${BOOT_DIR:-}"
if [[ -z "${BOOT_DIR}" ]]; then
  if [[ -d /boot/firmware ]]; then
    BOOT_DIR=/boot/firmware      # Bookworm and later
  else
    BOOT_DIR=/boot               # older Raspberry Pi OS
  fi
fi

CMDLINE="${BOOT_DIR}/cmdline.txt"
CONFIG="${BOOT_DIR}/config.txt"
CMDLINE_BAK="${CMDLINE}.tangbox-backup"
CONFIG_BAK="${CONFIG}.tangbox-backup"

# quiet                      - suppress most kernel chatter
# loglevel=0                 - and the rest of it
# logo.nologo                - no raspberry logos in the corner
# vt.global_cursor_default=0 - no blinking cursor left on screen
# systemd.show_status=false  - THE IMPORTANT ONE. `quiet` only silences the
#                              KERNEL; most of what scrolls past on a Linux boot
#                              is systemd announcing each service it starts
#                              ("[ OK ] Started ..."), written straight to the
#                              console. Both other flags sail right past it.
#                              Added 2026-08-19 after Brian watched the first
#                              quiet boot and still saw terminal lines.
QUIET_FLAGS=(
  quiet
  loglevel=0
  logo.nologo
  vt.global_cursor_default=0
  systemd.show_status=false
)

MODE=apply
for arg in "$@"; do
  case "$arg" in
    --undo)   MODE=undo ;;
    --status) MODE=status ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

# Use sudo only when the boot partition isn't already writable. Keeps the tests
# (which point at a temp dir they own) from needing a password.
SUDO=""
if [[ ! -w "${BOOT_DIR}" ]]; then
  SUDO="sudo"
fi

die() { echo "error: $*" >&2; exit 1; }

[[ -f "${CMDLINE}" ]] || die "${CMDLINE} not found. Is BOOT_DIR right? (BOOT_DIR=${BOOT_DIR})"

# --- status -----------------------------------------------------------------
if [[ "${MODE}" == "status" ]]; then
  echo "boot dir: ${BOOT_DIR}"
  missing=()
  for flag in "${QUIET_FLAGS[@]}"; do
    grep -qw -- "${flag}" "${CMDLINE}" || missing+=("${flag}")
  done
  if [[ ${#missing[@]} -eq 0 ]]; then
    echo "cmdline.txt: quiet boot IS applied"
  else
    echo "cmdline.txt: not applied (missing: ${missing[*]})"
  fi
  if [[ -f "${CONFIG}" ]] && grep -q "^disable_splash=1" "${CONFIG}"; then
    echo "config.txt:  rainbow splash disabled"
  else
    echo "config.txt:  rainbow splash still shown"
  fi
  [[ -f "${CMDLINE_BAK}" ]] && echo "backup:      ${CMDLINE_BAK}" || echo "backup:      none"
  exit 0
fi

# --- undo -------------------------------------------------------------------
if [[ "${MODE}" == "undo" ]]; then
  [[ -f "${CMDLINE_BAK}" ]] || die "no backup at ${CMDLINE_BAK}; nothing to undo"
  ${SUDO} cp "${CMDLINE_BAK}" "${CMDLINE}"
  [[ -f "${CONFIG_BAK}" ]] && ${SUDO} cp "${CONFIG_BAK}" "${CONFIG}"
  echo "==> Restored the original boot files. Reboot to see the messages again."
  exit 0
fi

# --- apply ------------------------------------------------------------------
# Back up ONCE. Running twice must not overwrite the pristine copy with an
# already-modified one, or --undo would restore the wrong thing.
[[ -f "${CMDLINE_BAK}" ]] || ${SUDO} cp "${CMDLINE}" "${CMDLINE_BAK}"
if [[ -f "${CONFIG}" && ! -f "${CONFIG_BAK}" ]]; then
  ${SUDO} cp "${CONFIG}" "${CONFIG_BAK}"
fi

# Collapse to a single line no matter what the file looked like, then append
# only the flags that aren't already there.
line="$(tr '\n' ' ' < "${CMDLINE}" | tr -s ' ')"
line="${line#"${line%%[![:space:]]*}"}"   # trim leading space
line="${line%"${line##*[![:space:]]}"}"   # trim trailing space

# Move the console OFF the visible screen. The flags above reduce how much gets
# written; this decides WHERE anything still written goes. tty3 is a virtual
# terminal nobody ever displays, so stray output (early kernel lines before
# loglevel bites, fsck, cloud-init) lands out of sight and TangBox owns tty1
# uncontested.
#
# Only ever rewrites an existing console=tty1 - never invents one, and never
# touches console=serial0, which is how you debug a Pi that will not boot.
console_moved=""
if [[ " ${line} " == *" console=tty1 "* ]]; then
  line="${line//console=tty1/console=tty3}"
  console_moved="yes"
fi

added=()
for flag in "${QUIET_FLAGS[@]}"; do
  if [[ " ${line} " != *" ${flag} "* ]]; then
    line="${line} ${flag}"
    added+=("${flag}")
  fi
done

# The guard this whole script exists for. Refuse to write anything but one line.
if [[ "$(printf '%s' "${line}" | grep -c '' || true)" -gt 1 ]]; then
  die "refusing to write: result is not a single line"
fi
case "${line}" in
  *$'\n'*) die "refusing to write: result contains a newline" ;;
esac
[[ -n "${line}" ]] || die "refusing to write an empty cmdline.txt"

if [[ ${#added[@]} -gt 0 || -n "${console_moved}" ]]; then
  printf '%s\n' "${line}" | ${SUDO} tee "${CMDLINE}" > /dev/null
  [[ ${#added[@]} -gt 0 ]] && echo "==> cmdline.txt: added ${added[*]}"
  [[ -n "${console_moved}" ]] && echo "==> cmdline.txt: console moved tty1 -> tty3"
else
  echo "==> cmdline.txt: already quiet, nothing to do"
fi

# The rainbow square at the very start of boot is firmware, not the kernel, so
# it needs config.txt rather than a kernel flag.
if [[ -f "${CONFIG}" ]]; then
  if grep -q "^disable_splash=1" "${CONFIG}"; then
    echo "==> config.txt:  rainbow splash already disabled"
  else
    printf '\n# TangBox: no rainbow square at power-on.\ndisable_splash=1\n' \
      | ${SUDO} tee -a "${CONFIG}" > /dev/null
    echo "==> config.txt:  disabled the rainbow splash"
  fi
fi

cat <<EOF

==> Done. Reboot to see it:  sudo systemctl reboot

You should get a black screen instead of scrolling text, then TangBox. The
screen stays black for roughly 20 seconds - that is the Pi booting, not a fault.

To put it all back:  ${SUDO:+sudo }$0 --undo
Backups:             ${CMDLINE_BAK}
EOF
