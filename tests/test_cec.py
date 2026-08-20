"""Tests for the HDMI-CEC input backend.

Every line of libCEC output quoted here was captured from the real Samsung on
the Pi 5 on 2026-08-19, not invented. That matters: all three bugs these tests
cover were invisible until the box was on an actual television.
"""

from __future__ import annotations

from typing import List, Optional

from nostalgiabox.actions import Action
from nostalgiabox.input.cec import CecBackend

from .helpers import FakeClock

# One press of "up" as libCEC 7.0.0 actually reports it: TWO lines, same
# millisecond, followed by the release.
REAL_UP_PRESS = [
    "DEBUG:   [           27290]\tkey pressed: up (1) current(ff) duration(0)\n",
    "DEBUG:   [           27290]\tkey pressed: up (1, 0)\n",
    "DEBUG:   [           27540]\tkey released: up (1) D:250ms\n",
]

REAL_DOWN_PRESS = [
    "DEBUG:   [           27810]\tkey pressed: down (2) current(ff) duration(0)\n",
    "DEBUG:   [           27810]\tkey pressed: down (2, 0)\n",
]


def drain(backend: CecBackend) -> List[Action]:
    """Everything the backend has emitted so far, as a list of actions."""
    actions = []
    while not backend._queue.empty():
        actions.append(backend._queue.get_nowait().action)
    return actions


def feed(backend: CecBackend, lines) -> None:
    for line in lines:
        backend._handle_line(line)


# -- duplicate suppression --------------------------------------------------


def test_one_press_emits_one_event():
    """libCEC prints two 'key pressed' lines per press; that is still one press.

    Without suppression a single press of the d-pad's up button would move
    two channels at once.
    """
    backend = CecBackend(clock=FakeClock())
    feed(backend, REAL_UP_PRESS)
    assert drain(backend) == [Action.NAV_UP]


def test_different_keys_in_quick_succession_both_emit():
    """Suppression must key on the event, not just on time."""
    clock = FakeClock()
    backend = CecBackend(clock=clock)
    feed(backend, REAL_UP_PRESS)
    clock.advance(0.01)
    feed(backend, REAL_DOWN_PRESS)
    assert drain(backend) == [Action.NAV_UP, Action.NAV_DOWN]


def test_same_key_after_the_window_emits_again():
    """Pressing up twice, properly spaced, is two channel changes."""
    clock = FakeClock()
    backend = CecBackend(clock=clock)
    feed(backend, REAL_UP_PRESS)
    clock.advance(1.0)
    feed(backend, REAL_UP_PRESS)
    assert drain(backend) == [Action.NAV_UP, Action.NAV_UP]


def test_unmapped_keys_are_ignored():
    backend = CecBackend(clock=FakeClock())
    backend._handle_line("DEBUG: key pressed: teletext (91) current(ff)\n")
    backend._handle_line("TRAFFIC: [   9]\t<< f0\n")
    assert drain(backend) == []


# -- how cec-client is launched ---------------------------------------------


class FakeStdin:
    def __init__(self) -> None:
        self.written: List[str] = []
        self.flushed = False

    def write(self, text: str) -> None:
        self.written.append(text)

    def flush(self) -> None:
        self.flushed = True

    def close(self) -> None:
        pass


class FakeProc:
    """Just enough of Popen for _run() to start, read a little, and finish."""

    def __init__(self, lines) -> None:
        self.stdout = iter(lines)
        self.stdin = FakeStdin()

    def terminate(self) -> None:
        pass

    def wait(self, timeout: Optional[float] = None) -> int:
        return 0

    def kill(self) -> None:
        pass


def run_backend(monkeypatch, lines=()) -> tuple:
    """Run _run() against a fake cec-client. Returns (command, stdin)."""
    captured = {}

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        proc = FakeProc(lines)
        captured["proc"] = proc
        return proc

    monkeypatch.setattr("nostalgiabox.input.cec.shutil.which", lambda _: "/usr/bin/cec-client")
    monkeypatch.setattr("nostalgiabox.input.cec.subprocess.Popen", fake_popen)

    backend = CecBackend(clock=FakeClock())
    backend._run()
    return captured["cmd"], captured["proc"].stdin


def test_announces_itself_as_the_active_source(monkeypatch):
    """The TV routes remote keys to the ACTIVE SOURCE and nowhere else.

    Without this the Samsung forwards nothing at all and simply complains that
    the button "is not supported in the current mode" - which reads as a dead
    remote rather than a missing handshake.
    """
    _, stdin = run_backend(monkeypatch)
    assert "as\n" in stdin.written
    assert stdin.flushed


def test_debug_level_includes_key_press_lines(monkeypatch):
    """`key pressed:` is logged at libCEC's DEBUG level (16), not TRAFFIC (8).

    At -d 8 the keys arrive but are never printed, so the parser sees nothing.
    """
    cmd, _ = run_backend(monkeypatch)
    level = int(cmd[cmd.index("-d") + 1])
    assert level & 16, f"-d {level} does not include DEBUG (16)"


def test_keys_arriving_from_the_subprocess_are_emitted(monkeypatch):
    """End to end: real libCEC output in, one InputEvent out."""
    captured = {}

    def fake_popen(cmd, **kwargs):
        proc = FakeProc(REAL_UP_PRESS)
        captured["proc"] = proc
        return proc

    monkeypatch.setattr("nostalgiabox.input.cec.shutil.which", lambda _: "/usr/bin/cec-client")
    monkeypatch.setattr("nostalgiabox.input.cec.subprocess.Popen", fake_popen)

    backend = CecBackend(clock=FakeClock())
    backend._run()
    assert drain(backend) == [Action.NAV_UP]
