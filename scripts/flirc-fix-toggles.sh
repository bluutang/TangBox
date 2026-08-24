#!/usr/bin/env bash
#
# Teach the Flirc the SECOND infrared pattern for every button that only has one.
#
# Why this exists
# ---------------
# The GE Big Button remote is programmed to a cable/satellite code set, and that
# protocol carries a TOGGLE BIT: one bit of the infrared frame flips on every
# fresh press, so a receiver can tell "pressed twice" apart from "held down".
#
# The Flirc does not decode protocols. As docs/flirc-remote-mapping.md puts it,
# it "learns the shape of the infrared flash and staples a keystroke to it". A
# flipped toggle bit is a DIFFERENT shape. So a button recorded once is only
# recognised half the time - every other press is an unknown pattern and
# produces nothing at all.
#
# Measured 2026-08-24: pressing `5` ten times slowly typed exactly five
# characters. Ten times quickly typed all ten, because rapid presses send repeat
# frames that do NOT flip the toggle. Seventeen of the twenty-nine keys had only
# one pattern recorded; the nine with two were reliable.
#
# This is not a fault in the remote, the dongle, or the batteries. All three
# were replaced or cleared during diagnosis and none of them was the cause.
#
# What it does
# ------------
# Reads the Flirc's own key table, finds every key with fewer than two recorded
# patterns, and walks you through pressing each one so the other toggle state
# gets learned. Then re-reads the table and tells you whether it worked.
#
# Safe to re-run: it always asks the hardware what is missing rather than
# working from a list, so a half-finished session simply picks up where it
# stopped.
#
# Usage:  bash scripts/flirc-fix-toggles.sh
#
set -uo pipefail

FLIRC_UTIL="${FLIRC_UTIL:-/Applications/Flirc.app/Contents/Resources/flirc_util}"
DOCS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/docs"

if [[ ! -x "$FLIRC_UTIL" ]]; then
  echo "Cannot find flirc_util at: $FLIRC_UTIL" >&2
  echo "Install the Flirc app, or set FLIRC_UTIL=/path/to/flirc_util" >&2
  exit 1
fi

# Friendly names, so the prompt says which button to press rather than which
# keystroke it sends. Anything not listed falls back to the raw key name.
button_name() {
  case "$1" in
    h)        echo "🏠 HOUSE (guide)" ;;
    i)        echo "☰ HAMBURGER (banner)" ;;
    l)        echo "ch⤸ RETURN (last channel)" ;;
    m)        echo "🔇 MUTE" ;;
    c)        echo "INPUT (CRT cycle)" ;;
    b)        echo "✱ STAR (bedtime)" ;;
    p)        echo "⏻ POWER" ;;
    "=")      echo "VOL +" ;;
    "-")      echo "VOL −" ;;
    pageup)   echo "CH +" ;;
    pagedown) echo "CH −" ;;
    up)       echo "D-pad UP" ;;
    down)     echo "D-pad DOWN" ;;
    left)     echo "D-pad LEFT" ;;
    right)    echo "D-pad RIGHT" ;;
    return)   echo "OK / ENTER" ;;
    .)        echo "• DOT (random)" ;;
    [0-9])    echo "NUMBER $1" ;;
    *)        echo "$1" ;;
  esac
}

# Every key in the Flirc's table, one per line, with how many patterns it has.
pattern_counts() {
  "$FLIRC_UTIL" settings 2>/dev/null \
    | awk '/^-----/{go=1; next} go && NF>=5 {print $NF}' \
    | sort | uniq -c
}

under_recorded() {
  pattern_counts | awk '$1 < 2 {print $2}'
}

echo "=============================================================="
echo " Flirc toggle-bit repair"
echo "=============================================================="
"$FLIRC_UTIL" version 2>&1 | head -1

# The GUI app holds the dongle exclusively. flirc_util then sees nothing at all,
# which looks exactly like an unplugged dongle - documented in
# docs/flirc-remote-mapping.md and rediscovered the hard way at 3am.
if pgrep -qf "/Applications/Flirc.app/Contents/MacOS/Flirc"; then
  echo
  echo "Flirc.app is running, and it holds the dongle exclusively." >&2
  echo "Quit Flirc.app, then run this again." >&2
  exit 1
fi

# A reachable dongle reports its firmware. Only the tool's own version means
# nothing is listening.
if ! "$FLIRC_UTIL" version 2>&1 | grep -q "FW Version"; then
  echo
  echo "No Flirc detected. Plug the dongle into this Mac and try again." >&2
  echo "(If it IS plugged in, check that Flirc.app is not running.)" >&2
  exit 1
fi

missing=()
while IFS= read -r k; do [[ -n "$k" ]] && missing+=("$k"); done < <(under_recorded)

if [[ ${#missing[@]} -eq 0 ]]; then
  echo
  echo "Every key already has two or more patterns. Nothing to do."
  exit 0
fi

# Always back up before changing the dongle. Timestamped, so an existing
# backup is never overwritten.
backup="$DOCS_DIR/Tangbox-remote-$(date +%Y%m%d-%H%M%S).fcfg"
mkdir -p "$DOCS_DIR"
if "$FLIRC_UTIL" saveconfig "$backup" >/dev/null 2>&1; then
  # flirc_util appends its own .fcfg, so tidy the doubled extension.
  [[ -f "$backup.fcfg" ]] && mv "$backup.fcfg" "$backup"
  echo "Backed up to: ${backup/#$HOME/~}"
else
  echo "WARNING: could not save a backup. Continuing anyway." >&2
fi

cat <<EOF

${#missing[@]} key(s) have only ONE infrared pattern and will keep dropping
about half of all slow presses until they have two.

For each one: press the button ONCE, then WAIT for the prompt before the next.
Do not hold it and do not double-tap - a rapid second press repeats the same
toggle state and teaches the Flirc nothing new.

If it says the button is already recorded, that press happened to carry the
pattern it already knows. Just press again; the next one is the other state.

EOF
read -r -p "Ready? [Enter to start, Ctrl-C to quit] " _

done_keys=(); skipped=()
for key in "${missing[@]}"; do
  echo
  echo "--------------------------------------------------------------"
  printf ' Press:  %s\n' "$(button_name "$key")"
  echo "--------------------------------------------------------------"
  "$FLIRC_UTIL" record "$key"
  status=$?
  if [[ $status -eq 0 ]]; then
    done_keys+=("$key")
  else
    echo "  (that did not take - press it again on the next pass)"
    skipped+=("$key")
  fi
  read -r -p "  Enter for the next button, or 's' then Enter to skip ahead: " ans
  [[ "${ans:-}" == "s" ]] && { skipped+=("$key"); continue; }
done

echo
echo "=============================================================="
echo " Result"
echo "=============================================================="
still=()
while IFS= read -r k; do [[ -n "$k" ]] && still+=("$k"); done < <(under_recorded)

pattern_counts | awk '{printf "  %-10s %s pattern(s)%s\n", $2, $1, ($1<2 ? "   <-- STILL SHORT" : "")}'

echo
if [[ ${#still[@]} -eq 0 ]]; then
  echo "All keys now have two or more patterns."
  final="$DOCS_DIR/Tangbox-remote.fcfg"
  if "$FLIRC_UTIL" saveconfig "$final" >/dev/null 2>&1; then
    [[ -f "$final.fcfg" ]] && mv "$final.fcfg" "$final"
    echo "Saved the new configuration to: ${final/#$HOME/~}"
    echo "Commit it - that file is the only copy of 29 programmed buttons."
  fi
  echo
  echo "Test it: open a text editor and press one button ten times SLOWLY."
  echo "Ten characters means it is fixed. Five means that key needs another go."
else
  echo "${#still[@]} key(s) still have one pattern: ${still[*]}"
  echo "Re-run this script; it only asks for what is still missing."
fi
