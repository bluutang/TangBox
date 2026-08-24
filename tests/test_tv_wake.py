"""Taking the television with us, in both directions.

The box already had `tv_standby_command`, which tells the TV to switch off just
before the Pi halts. There was no counterpart for coming back on - and until
POWER became standby there could not be one, because a halted Pi cuts power to
its own infrared receiver and there was no "on" press to hang anything from.

Now POWER goes to standby, the Pi stays alive, and waking is a real event. So:

* Waking  -> `tv_wake_command`     - HDMI-CEC "One Touch Play": the TV powers on
                                     AND switches to this input.
* Standby -> `tv_standby_command`  - the same one the halt has always used.

The pairing is what makes it safe to switch the television off on standby. On
its own that would leave POWER waking the box to a dark screen; with a wake
command the round trip closes.

Both default to empty, so a box that has never heard of CEC behaves exactly as
it always has. Everything is best-effort: a television that will not answer
must never stop the box working.
"""

from __future__ import annotations

from typing import List

import pytest

from nostalgiabox.actions import Action, InputEvent
from nostalgiabox.app import TVApp
from nostalgiabox.config import config_from_dict
from nostalgiabox.input.manager import InputManager
from nostalgiabox.player import MockPlayer
from tests.helpers import FakeClock, make_show

WAKE = ["sh", "-c", "echo on"]
OFF = ["sh", "-c", "echo standby"]


def build(tmp_path, monkeypatch, **overrides):
    make_show(tmp_path, "dragon", 3)
    launched: List[list] = []

    def fake_popen(command, *a, **kw):
        launched.append(list(command))
        return object()

    monkeypatch.setattr("nostalgiabox.app.subprocess.Popen", fake_popen)

    data = {
        "shuffle_seed": 7,
        "start_channel": 2,
        "start_offset": 0,
        "initial_volume": 5,
        "power_off_command": [],
        "channels": [
            {"number": 2, "name": "Dragon Tales", "path": str(tmp_path / "dragon")}
        ],
    }
    data.update(overrides)
    app = TVApp(
        config_from_dict(data),
        MockPlayer(),
        InputManager([]),
        clock=FakeClock(),
        sleep=lambda _s: None,
    )
    return app, launched


# --- waking ----------------------------------------------------------------


def test_waking_from_standby_tells_the_television_to_come_on(tmp_path, monkeypatch):
    app, launched = build(tmp_path, monkeypatch, tv_wake_command=WAKE)
    app.start()
    app.handle_event(InputEvent(Action.POWER))  # into standby
    launched.clear()

    app.handle_event(InputEvent(Action.POWER))  # back out

    assert WAKE in launched


def test_switching_on_tells_the_television_to_come_on(tmp_path, monkeypatch):
    """A cold boot too - which is what makes a smart plug useful."""
    app, launched = build(tmp_path, monkeypatch, tv_wake_command=WAKE)
    app.start()
    assert WAKE in launched


# --- going quiet -----------------------------------------------------------


def test_going_to_standby_switches_the_television_off(tmp_path, monkeypatch):
    app, launched = build(tmp_path, monkeypatch, tv_standby_command=OFF)
    app.start()
    launched.clear()

    app.handle_event(InputEvent(Action.POWER))

    assert OFF in launched


def test_bedtime_ending_in_standby_also_switches_the_television_off(
    tmp_path, monkeypatch
):
    """The sign-off should take the television with it, halt or not."""
    app, launched = build(
        tmp_path, monkeypatch, tv_standby_command=OFF, bedtime_ends_in="standby"
    )
    app.start()
    app.handle_event(InputEvent(Action.BEDTIME))
    launched.clear()

    app._bedtime_finish()

    assert app.standby is True
    assert OFF in launched


# --- unchanged behaviour ---------------------------------------------------


def test_a_halt_still_switches_the_television_off(tmp_path, monkeypatch):
    app, launched = build(
        tmp_path, monkeypatch, tv_standby_command=OFF, power_button="shutdown"
    )
    app.start()
    launched.clear()

    app.handle_event(InputEvent(Action.POWER))

    assert app.powered_off is True
    assert OFF in launched


def test_a_box_with_no_commands_configured_launches_nothing(tmp_path, monkeypatch):
    app, launched = build(tmp_path, monkeypatch)
    app.start()
    app.handle_event(InputEvent(Action.POWER))
    app.handle_event(InputEvent(Action.POWER))

    assert launched == []


def test_a_television_that_will_not_answer_never_stops_the_box(
    tmp_path, monkeypatch
):
    """Best-effort, like everything else on this path."""
    app, _ = build(tmp_path, monkeypatch, tv_wake_command=WAKE)

    def explode(*a, **kw):
        raise OSError("no cec-client here")

    monkeypatch.setattr("nostalgiabox.app.subprocess.Popen", explode)
    app.start()
    app.handle_event(InputEvent(Action.POWER))
    app.handle_event(InputEvent(Action.POWER))

    assert app.standby is False


# --- config ----------------------------------------------------------------


def test_the_wake_command_defaults_to_leaving_the_television_alone(
    tmp_path, monkeypatch
):
    app, _ = build(tmp_path, monkeypatch)
    assert app.config.tv_wake_command == ()


def test_the_wake_command_accepts_a_list_or_a_string(tmp_path, monkeypatch):
    app, _ = build(tmp_path, monkeypatch, tv_wake_command="cec-client -s")
    assert app.config.tv_wake_command == ("cec-client", "-s")
