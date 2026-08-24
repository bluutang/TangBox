"""Going quiet should be as much of an event as coming on.

Waking from standby replays the sign-on. Going INTO standby went straight to
the standby card with no ceremony at all, which left the box lopsided: it made
an occasion of switching on and none of switching off.

Two things here:

* `sign_off_on_standby` - whether POWER plays the collapse before going quiet.
  Off by default: it puts ~4 seconds in front of every POWER press, which is a
  real trade rather than an obvious improvement.
* `sign_off_seconds` - how long to let the clip run. It was a hard-coded 1.1,
  which silently truncated the longer mirrored sign-off to about a second.
  The bedtime button ALWAYS plays it - that ceremony is the whole point of ✱ -
  so only POWER is governed by the flag.
"""

from __future__ import annotations

from nostalgiabox.actions import Action, InputEvent
from nostalgiabox.app import TVApp
from nostalgiabox.config import config_from_dict
from nostalgiabox.input.manager import InputManager
from nostalgiabox.player import MockPlayer
from tests.helpers import FakeClock, make_show


def build(tmp_path, **overrides):
    make_show(tmp_path, "dragon", 3)
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir(exist_ok=True)
    for name in ("power_off.mp4", "logo.mp4", "colorbars.mp4"):
        (assets_dir / name).write_bytes(b"\x00")

    slept = []
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
        assets_dir=assets_dir,
        sleep=slept.append,
    )
    return app, app.player, slept


def sign_offs(player):
    return [p.name for p, _ in player.played].count("power_off.mp4")


def press_power(app):
    app.handle_event(InputEvent(Action.POWER))


# --- POWER --------------------------------------------------------------


def test_power_plays_the_sign_off_when_asked(tmp_path):
    app, player, _ = build(tmp_path, sign_off_on_standby=True)
    app.start()
    app._finish_sign_on()
    press_power(app)
    assert app.standby is True
    assert sign_offs(player) == 1


def test_power_is_silent_by_default(tmp_path):
    app, player, _ = build(tmp_path)
    app.start()
    app._finish_sign_on()
    press_power(app)
    assert app.standby is True
    assert sign_offs(player) == 0


def test_waking_never_plays_the_sign_off(tmp_path):
    app, player, _ = build(tmp_path, sign_off_on_standby=True)
    app.start()
    app._finish_sign_on()
    press_power(app)          # asleep
    player.played.clear()
    press_power(app)          # awake
    assert sign_offs(player) == 0


# --- the bedtime button -------------------------------------------------


def test_bedtime_always_plays_it_even_with_the_flag_off(tmp_path):
    """✱ is the ceremony. It does not depend on what POWER is set to."""
    app, player, _ = build(tmp_path, bedtime_ends_in="standby")
    app.start()
    app._finish_sign_on()
    app.handle_event(InputEvent(Action.BEDTIME))
    app._bedtime_finish()
    assert app.standby is True
    assert sign_offs(player) == 1


def test_bedtime_does_not_play_it_twice(tmp_path):
    """It is played in one place now, not by bedtime AND by standby."""
    app, player, _ = build(
        tmp_path, bedtime_ends_in="standby", sign_off_on_standby=True
    )
    app.start()
    app._finish_sign_on()
    app.handle_event(InputEvent(Action.BEDTIME))
    app._bedtime_finish()
    assert sign_offs(player) == 1


# --- how long it is allowed to run --------------------------------------


def test_the_clip_is_given_its_configured_time(tmp_path):
    """1.1s was hard-coded, which truncated the mirrored sign-off."""
    app, _player, slept = build(tmp_path, sign_off_seconds=4.0, sign_off_on_standby=True)
    app.start()
    app._finish_sign_on()
    press_power(app)
    assert 4.0 in slept


def test_the_old_default_is_unchanged(tmp_path):
    app, _player, slept = build(tmp_path, sign_off_on_standby=True)
    app.start()
    app._finish_sign_on()
    press_power(app)
    assert 1.1 in slept
