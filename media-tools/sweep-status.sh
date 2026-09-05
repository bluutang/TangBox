#!/bin/sh
# Status of the full-library decode sweep. Safe to run any time.
LOG="/private/tmp/claude-501/-Users-briantang-BluuClaude-tang-box/e2615b8a-e85c-4ec5-854f-b03071863b40/scratchpad/decode_sweep.log"
[ -f "$LOG" ] || { echo "no sweep log found - it may have been cleaned up"; exit 1; }
if pgrep -f decode_sweep.py >/dev/null; then echo "STATUS: running"; else echo "STATUS: finished"; fi
echo
grep '\.\.\. ' "$LOG" | tail -1
grep -c '^  BAD' "$LOG" | sed 's/^/bad files so far: /'
grep '^  BAD' "$LOG"
grep 'DONE in' "$LOG" || true

exit 0
