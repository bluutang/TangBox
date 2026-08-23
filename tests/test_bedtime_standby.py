"""What the ✱ button does when the evening is over: halt, or merely go quiet.

Halting is the honest end of the day, but it is a one-way door. A halted Pi
cuts power to its own USB ports, the infrared receiver stops listening, and
the remote cannot switch the box back on - only the button on the board can.

That is fine when a parent presses ✱ deliberately at bedtime. It is not fine
when a four-year-old presses it at four in the afternoon, because the
television is then gone until an adult walks over to the shelf.

So where the sign-off ENDS is a setting. `shutdown` is the old behaviour and
stays the default, so no existing box changes what its button does just by
taking an update. `standby` keeps the whole ritual - the countdown, the
collapse - and simply leaves the box quiet and wakeable instead of dead.
"""

from __future__ import annotations

from typing import List

import pytest

from nostalgiabox.actions import Action, InputEvent
from nostalgiabox.app import TVApp
from nostalgiabox.config import ConfigError, config_from_dict
from nostalgiabox.input.manager import InputManager
from nostalgiabox.player import END_EOF, MockPlayer
from tests.helpers import FakeClock, make_show


def build(tmp_path, **overrides):
    make_show(tmp_path, "dragon", 3)
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir(exist_ok=True)
    (assets_dir / "power_off.mp4").write_bytes(b"\x00")

    ran: List[bool] = []
    clock = FakeClock()
    data = {
        "shuffle_seed": 7,
        "start_channel": 2,
        "start_offset": 0,
        "initial_volume": 5,
        "power_off_command": ["/bin/true"],
        "channels": [
            {"number": 2, "name": "Dragon Tales", "path": str(tmp_path / "dragon")}
        ],
    }
    data.update(overrides)
    app = TVApp(
        config_from_dict(data),
        MockPlayer(),
        InputManager([]),
        clock=clock,
        assets_dir=assets_dir,
        sleep=lambda _s: None,
    )
    app._run_power_off_command = lambda: ran.append(True)
    return app, clock, ran


def arm_bedtime(app):
    app.handle_event(InputEvent(Action.BEDTIME))


def run_out_the_clock(app, clock):
    """Advance past whatever deadline bedtime set, then let the loop notice."""
    assert app.bedtime_deadline is not None
    clock.now = app.bedtime_deadline + 1
    app.step()


def played_names(player):
    return [p.name for p, _ in player.played]


# --- the new behaviour -----------------------------------------------------


def test_standby_bedtime_goes_quiet_instead_of_halting(tmp_path):
    app, clock, _ = build(tmp_path, bedtime_ends_in="standby")
    app.start()
    arm_bedtime(app)
    run_out_the_clock(app, clock)

    assert app.standby is True
    assert app.powered_off is False


def test_standby_bedtime_never_runs_the_power_off_command(tmp_path):
    app, clock, ran = build(tmp_path, bedtime_ends_in="standby")
    app.start()
    arm_bedtime(app)
    run_out_the_clock(app, clock)

    assert ran == []


def test_standby_bedtime_still_plays_the_sign_off_collapse(tmp_path):
    """The ritual is the point. Only its ending changes."""
    app, clock, _ = build(tmp_path, bedtime_ends_in="standby")
    app.start()
    arm_bedtime(app)
    run_out_the_clock(app, clock)

    assert "power_off.mp4" in played_names(app.player)


def test_power_brings_the_box_back_after_a_standby_bedtime(tmp_path):
    """The whole reason for the setting: one button undoes it."""
    app, clock, _ = build(tmp_path, bedtime_ends_in="standby")
    app.start()
    arm_bedtime(app)
    run_out_the_clock(app, clock)
    assert app.standby is True

    app.handle_event(InputEvent(Action.POWER))

    assert app.standby is False


def test_standby_bedtime_disarms_itself_so_it_does_not_fire_again(tmp_path):
    """Waking up must not drop straight back into a spent countdown."""
    app, clock, _ = build(tmp_path, bedtime_ends_in="standby")
    app.start()
    arm_bedtime(app)
    run_out_the_clock(app, clock)
    app.handle_event(InputEvent(Action.POWER))

    clock.advance(60)
    app.step()

    assert app.standby is False
    assert app.bedtime_deadline is None


def test_a_finished_programme_under_standby_bedtime_also_goes_quiet(tmp_path):
    """The other route to the end of the evening: the episode simply ends."""
    app, clock, ran = build(tmp_path, bedtime_ends_in="standby")
    app.start()
    arm_bedtime(app)
    app.player.finish_current(END_EOF)
    app.step()

    assert app.standby is True
    assert app.powered_off is False
    assert ran == []


# --- the old behaviour is untouched ----------------------------------------


def test_shutdown_is_still_the_default(tmp_path):
    app, _clock, _ran = build(tmp_path)
    assert app.config.bedtime_ends_in == "shutdown"


def test_shutdown_bedtime_still_halts(tmp_path):
    app, clock, ran = build(tmp_path, bedtime_ends_in="shutdown")
    app.start()
    arm_bedtime(app)
    run_out_the_clock(app, clock)

    assert app.powered_off is True
    assert app.standby is False
    assert ran == [True]


def test_a_nonsense_setting_is_refused(tmp_path):
    with pytest.raises(ConfigError):
        build(tmp_path, bedtime_ends_in="sleep")
