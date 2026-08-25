"""Putting the box into standby without pressing the button.

The box reads input only from evdev devices it enumerated at STARTUP, so there
is no way in from a shell: a synthesised keypress needs a new virtual device,
which the keyboard backend would never bind, and creating one and restarting to
pick it up would kill the real remote when the virtual device went away (the
backend's select loop breaks on a disappearing fd).

So the box grows one deliberate door instead - a signal - and it opens onto the
SAME action the POWER button sends, rather than a second path into standby that
could drift away from the first.
"""

from nostalgiabox.actions import Action, InputEvent
from nostalgiabox.app import TVApp
from nostalgiabox.config import config_from_dict
from nostalgiabox.input.manager import InputManager
from nostalgiabox.player import MockPlayer
from tests.helpers import FakeClock, make_show


def build(tmp_path):
    make_show(tmp_path, "dragon", 3)
    return TVApp(
        config_from_dict({
            "shuffle_seed": 7,
            "start_channel": 2,
            "start_offset": 0,
            "power_off_command": [],
            "channels": [
                {"number": 2, "name": "Dragon Tales", "path": str(tmp_path / "dragon")}
            ],
        }),
        MockPlayer(),
        InputManager([]),
        clock=FakeClock(),
    )


def test_a_requested_power_press_puts_the_box_in_standby(tmp_path):
    app = build(tmp_path)
    app.start()
    assert not app.standby

    app.request_power()
    app.step()
    assert app.standby


def test_it_toggles_exactly_as_the_button_does(tmp_path):
    """One door, not two. Waking it again has to work the same way."""
    app = build(tmp_path)
    app.start()

    app.request_power()
    app.step()
    assert app.standby

    app.request_power()
    app.step()
    assert not app.standby


def test_the_request_does_nothing_until_the_loop_runs(tmp_path):
    """A signal handler must not touch the state machine mid-step.

    It sets a flag and returns; the loop does the work. Doing it in the handler
    would run player and overlay calls at an arbitrary bytecode boundary.
    """
    app = build(tmp_path)
    app.start()
    app.request_power()
    assert not app.standby, "the handler acted immediately"
    app.step()
    assert app.standby


def test_repeated_requests_before_a_step_only_count_once(tmp_path):
    app = build(tmp_path)
    app.start()
    for _ in range(5):
        app.request_power()
    app.step()
    assert app.standby, "five requests should not have toggled it back off"
