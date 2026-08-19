"""HDMI-CEC input: use the TV's own remote to drive the box.

Many TVs can forward remote button presses to attached HDMI devices over CEC
(Samsung "Anynet+", LG "SimpLink", Sony "BRAVIA Sync", etc.). On a Raspberry Pi
the easiest way to receive those is libCEC's ``cec-client`` utility, which
prints a line like ``key pressed: up (1)`` for every button. This backend spawns
``cec-client`` and turns those lines into actions - so the kids can just use the
TV remote they already point at the screen, no separate remote required.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import time
from typing import Callable, List, Optional

from .base import InputBackend
from .keymap import cec_key_to_event

log = logging.getLogger(__name__)

_KEY_PRESSED_RE = re.compile(r"key pressed:\s*(.+?)\s*(?:\(|$)", re.IGNORECASE)

# libCEC prints TWO "key pressed" lines for a single press, in the same
# millisecond:
#     key pressed: up (1) current(ff) duration(0)
#     key pressed: up (1, 0)
# Both match the regex, so without this window one press moves two channels.
# A time window rather than a tighter regex, so it holds whichever of the two
# formats a future libCEC emits - and it tames a held-down button too.
_DUPLICATE_WINDOW = 0.25


class CecBackend(InputBackend):
    """Reads TV-remote button presses forwarded over HDMI-CEC."""

    name = "cec"

    def __init__(
        self,
        *,
        binary: str = "cec-client",
        osd_name: str = "TangBox",
        extra_args: Optional[List[str]] = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__()
        self._binary = binary
        self._osd_name = osd_name
        self._extra_args = list(extra_args) if extra_args else []
        self._proc: Optional[subprocess.Popen] = None
        self._clock = clock
        self._last_event = None
        self._last_time = 0.0

    @staticmethod
    def is_available(binary: str = "cec-client") -> bool:
        return shutil.which(binary) is not None

    def _run(self) -> None:
        if not self.is_available(self._binary):
            log.info("%s not found; HDMI-CEC input disabled", self._binary)
            return
        cmd = [
            self._binary,
            "-t", "p",            # register as a Playback device
            "-o", self._osd_name,  # the name the TV shows for this device
            # libCEC log level, a bitmask. It MUST include DEBUG (16): that is
            # where "key pressed:" is written. At the old value of 8 (TRAFFIC
            # only) the keys arrived and were never printed, so this backend
            # saw nothing and the remote looked dead. 31 = everything.
            "-d", "31",
            *self._extra_args,
        ]
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            log.warning("could not start %s: %s", self._binary, exc)
            return

        # A TV routes remote keys to whichever device claims to be the ACTIVE
        # SOURCE. Until we say so, the Samsung forwards nothing at all and just
        # tells the viewer the button "is not supported in the current mode" -
        # which reads as a dead remote rather than a missing handshake.
        # Side effect worth knowing: this also switches the TV to our input.
        self._announce_active_source()

        log.info("HDMI-CEC input active via %s", self._binary)
        assert self._proc.stdout is not None
        for line in self._proc.stdout:
            if self.stopping:
                break
            self._handle_line(line)

    def _announce_active_source(self) -> None:
        """Tell the TV to send us its remote keys (cec-client's ``as``)."""
        if self._proc is None or self._proc.stdin is None:
            return
        try:
            self._proc.stdin.write("as\n")
            self._proc.stdin.flush()
        except (OSError, ValueError):
            log.warning("could not claim active source", exc_info=True)

    def _handle_line(self, line: str) -> None:
        match = _KEY_PRESSED_RE.search(line)
        if not match:
            return
        event = cec_key_to_event(match.group(1))
        if event is None:
            return
        now = self._clock()
        if event == self._last_event and now - self._last_time < _DUPLICATE_WINDOW:
            return
        self._last_event = event
        self._last_time = now
        self.emit(event)

    def _close(self) -> None:
        if self._proc is None:
            return
        try:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        except OSError:
            pass
        self._proc = None


__all__ = ["CecBackend"]
