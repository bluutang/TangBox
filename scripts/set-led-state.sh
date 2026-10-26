#!/usr/bin/env bash
#
# Control the onboard Raspberry Pi 5 dual-color status LED to show TangBox's state.
#
# On Raspberry Pi 5:
#   brightness 0   -> Solid GREEN (On the air / Playing)
#   brightness 255 -> Solid RED   (Standby / Sleep)
#
set -euo pipefail

MODE="${1:-}"

case "$MODE" in
  on)
    rm -f /tmp/tangbox-standby
    echo none > /sys/class/leds/PWR/trigger 2>/dev/null || true
    echo 0 > /sys/class/leds/PWR/brightness 2>/dev/null || true
    ;;
  standby)
    touch /tmp/tangbox-standby
    echo none > /sys/class/leds/PWR/trigger 2>/dev/null || true
    echo 255 > /sys/class/leds/PWR/brightness 2>/dev/null || true
    ;;
  *)
    echo "Usage: $0 {on|standby}" >&2
    exit 1
    ;;
esac
