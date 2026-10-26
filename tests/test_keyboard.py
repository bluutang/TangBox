"""Tests for the keyboard/evdev input backend debouncing and repeat handling."""

from __future__ import annotations

from typing import List

from nostalgiabox.actions import Action
from nostalgiabox.input.keyboard import KeyboardBackend

from .helpers import FakeClock


def drain(backend: KeyboardBackend) -> List[Action]:
    """Drain all events emitted so far, returning their actions."""
    actions = []
    while not backend._queue.empty():
        actions.append(backend._queue.get_nowait().action)
    return actions


def test_one_press_emits_one_event():
    clock = FakeClock()
    backend = KeyboardBackend(clock=clock)
    backend._handle_key_press("KEY_PAGEUP", 1)  # down
    assert drain(backend) == [Action.CHANNEL_UP]


def test_key_release_ignored():
    clock = FakeClock()
    backend = KeyboardBackend(clock=clock)
    backend._handle_key_press("KEY_PAGEUP", 1)  # down
    backend._handle_key_press("KEY_PAGEUP", 0)  # up
    assert drain(backend) == [Action.CHANNEL_UP]


def test_rapid_duplicate_channel_press_suppressed():
    """Contact bounce or duplicate IR packets within 250ms are dropped."""
    clock = FakeClock()
    backend = KeyboardBackend(clock=clock)
    backend._handle_key_press("KEY_PAGEUP", 1)  # down
    clock.advance(0.10)
    backend._handle_key_press("KEY_PAGEUP", 1)  # duplicate down (e.g. bounce)
    assert drain(backend) == [Action.CHANNEL_UP]


def test_spaced_channel_presses_both_emit():
    """Legitimate separate clicks (>250ms apart) both register."""
    clock = FakeClock()
    backend = KeyboardBackend(clock=clock)
    backend._handle_key_press("KEY_PAGEUP", 1)
    clock.advance(0.30)
    backend._handle_key_press("KEY_PAGEUP", 1)
    assert drain(backend) == [Action.CHANNEL_UP, Action.CHANNEL_UP]


def test_different_keys_not_suppressed():
    """Alternating or different buttons in rapid succession are not debounced."""
    clock = FakeClock()
    backend = KeyboardBackend(clock=clock)
    backend._handle_key_press("KEY_PAGEUP", 1)
    clock.advance(0.05)
    backend._handle_key_press("KEY_PAGEDOWN", 1)
    assert drain(backend) == [Action.CHANNEL_UP, Action.CHANNEL_DOWN]


def test_channel_autorepeat_completely_suppressed():
    """Holding a channel button must NEVER autorepeat (no cascading channels)."""
    clock = FakeClock()
    backend = KeyboardBackend(clock=clock)
    backend._handle_key_press("KEY_PAGEUP", 1)  # initial press
    clock.advance(0.25)  # Linux evdev typematic delay (250ms)
    backend._handle_key_press("KEY_PAGEUP", 2)  # repeat 1
    clock.advance(0.033)
    backend._handle_key_press("KEY_PAGEUP", 2)  # repeat 2 (33ms later)
    clock.advance(0.033)
    backend._handle_key_press("KEY_PAGEUP", 2)  # repeat 3
    # All repeats ignored; only the initial down event was emitted.
    assert drain(backend) == [Action.CHANNEL_UP]


def test_volume_autorepeat_rate_limited():
    """Volume keys are allowed to repeat, but throttled to a sane cadence."""
    clock = FakeClock()
    backend = KeyboardBackend(clock=clock)
    backend._handle_key_press("KEY_VOLUMEUP", 1)  # initial press at t=1000.0
    assert drain(backend) == [Action.VOLUME_UP]

    # After 250ms hold, first repeat arrives at t=1000.25 (dt=0.25 >= 0.12s)
    clock.advance(0.25)
    backend._handle_key_press("KEY_VOLUMEUP", 2)
    assert drain(backend) == [Action.VOLUME_UP]

    # Repeats at 33ms interval arrive too quickly; should be throttled
    clock.advance(0.033)
    backend._handle_key_press("KEY_VOLUMEUP", 2)
    clock.advance(0.033)
    backend._handle_key_press("KEY_VOLUMEUP", 2)
    assert drain(backend) == []  # both throttled

    # Once 120ms total has elapsed since last repeat, next repeat fires
    clock.advance(0.06)  # total dt = 0.126s
    backend._handle_key_press("KEY_VOLUMEUP", 2)
    assert drain(backend) == [Action.VOLUME_UP]


def test_digit_entry_allows_fast_double_digits():
    """Dialing channel '11' with double-taps under 250ms (but >=150ms) is accepted."""
    clock = FakeClock()
    backend = KeyboardBackend(clock=clock)
    backend._handle_key_press("KEY_1", 1)
    clock.advance(0.18)  # 180ms double-tap
    backend._handle_key_press("KEY_1", 1)
    events = []
    while not backend._queue.empty():
        events.append(backend._queue.get_nowait())
    assert [e.action for e in events] == [Action.DIGIT, Action.DIGIT]
    assert [e.value for e in events] == [1, 1]


def test_digit_bounce_under_150ms_is_dropped():
    clock = FakeClock()
    backend = KeyboardBackend(clock=clock)
    backend._handle_key_press("KEY_1", 1)
    clock.advance(0.05)  # 50ms contact bounce
    backend._handle_key_press("KEY_1", 1)
    assert drain(backend) == [Action.DIGIT]
