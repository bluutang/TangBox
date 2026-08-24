"""Waking from standby should feel like a television coming on.

Pressing POWER used to drop straight back into whatever was playing. On a box
pretending to be a television that is the wrong beat entirely - the station
opens with an ident every morning, and coming out of standby is the same event
as far as anyone in the room is concerned.

The sign-on at BOOT and the sign-on at WAKE are not the same length, though,
and the reason is the television:

* At boot the set is often asleep, so the pre-roll exists to cover the seconds
  it takes to wake and switch input over CEC. That is what the spinner is for.
* At wake the set may ALSO be asleep - TangBox cannot switch this television
  off (the Samsung ignores CEC standby), so it gets switched off by hand, and
  a wake has to bring it back and wait for it just like a cold boot.

So a wake replays the WHOLE sign-on, pre-roll included. Off by default,
because it changes what a button does; config.pi.yaml turns it on.
"""

from __future__ import annotations

from pathlib import Path

from nostalgiabox.actions import Action, InputEvent
from nostalgiabox.app import TVApp
from nostalgiabox.config import config_from_dict
from nostalgiabox.input.manager import InputManager
from nostalgiabox.player import MockPlayer
from tests.helpers import FakeClock, make_show


def build(tmp_path, *, assets=("logo.mp4", "colorbars.mp4"), **overrides):
    make_show(tmp_path, "dragon", 3)
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir(exist_ok=True)
    for name in assets:
        (assets_dir / name).write_bytes(b"\x00")

    data = {
        "shuffle_seed": 7,
        "start_channel": 2,
        "start_offset": 0,
        "initial_volume": 5,
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
        sleep=lambda _s: None,
    )
    return app, app.player


def played(player):
    """Everything the player was asked to show. play_loop sets `looping`."""
    names = [p.name for p, _ in player.played]
    if player.looping is not None:
        names.append(player.looping.name)
    return names


def sleep_and_wake(app):
    # ANY button skips the boot sign-on, so get it out of the way first or the
    # first POWER press is spent skipping rather than sleeping.
    if app.signing_on:
        app._finish_sign_on()
    app.handle_event(InputEvent(Action.POWER))   # into standby
    app.player.played.clear()
    app.player.looping = None
    app.handle_event(InputEvent(Action.POWER))   # back out


SIGN_ON = {"enabled": True, "bars_seconds": 10, "on_wake": True}


def run_out_the_pre_roll(app):
    """Let the timed pre-roll expire so the sign-on moves on to the ident."""
    app._clock.advance(app.config.sign_on.bars_seconds + 1)
    app.step()


# --- the new behaviour -----------------------------------------------------


def test_waking_plays_the_ident(tmp_path):
    app, player = build(tmp_path, sign_on=SIGN_ON)
    app.start()
    sleep_and_wake(app)
    run_out_the_pre_roll(app)
    assert "logo.mp4" in played(player)


def test_waking_plays_the_pre_roll_too(tmp_path):
    """The television may well be OFF on a wake, so it still needs covering.

    This asserted the opposite at first, on the reasoning that a wake finds the
    set already on. That is wrong for this box: TangBox cannot put the
    television into standby (the Samsung ignores CEC standby entirely), so
    Brian switches it off by hand - and then a wake has to bring it back and
    wait for it, exactly like a cold boot. Proven on the set 2026-08-24: the
    ident played to a television that was still waking.
    """
    app, player = build(tmp_path, sign_on=SIGN_ON)
    app.start()
    sleep_and_wake(app)
    assert "colorbars.mp4" in played(player)


def test_waking_is_still_signing_on(tmp_path):
    """So a button press skips it, exactly as at boot."""
    app, _player = build(tmp_path, sign_on=SIGN_ON)
    app.start()
    sleep_and_wake(app)
    assert app.signing_on is True


def test_the_ident_hands_over_to_the_channel(tmp_path):
    app, player = build(tmp_path, sign_on=SIGN_ON)
    app.start()
    sleep_and_wake(app)
    run_out_the_pre_roll(app)
    app._finish_sign_on()
    assert app.signing_on is False
    assert player.current is not None


def test_a_missing_ident_still_wakes_the_box(tmp_path):
    """Every stage is optional; a missing asset must never cost the cartoons.

    With no ident to play, the pre-roll expires and the box tunes straight in
    rather than sitting on a spinner for ever.
    """
    app, player = build(tmp_path, assets=("colorbars.mp4",), sign_on=SIGN_ON)
    app.start()
    sleep_and_wake(app)
    run_out_the_pre_roll(app)
    assert app.signing_on is False
    assert player.current is not None


# --- unchanged behaviour ---------------------------------------------------


def test_off_by_default_waking_tunes_straight_in(tmp_path):
    app, player = build(
        tmp_path, sign_on={"enabled": True, "bars_seconds": 10}
    )
    app.start()
    sleep_and_wake(app)
    assert "logo.mp4" not in played(player)
    assert app.signing_on is False
    assert player.current is not None


def test_boot_still_gets_the_full_sign_on(tmp_path):
    """Wake is the short version; boot keeps its pre-roll."""
    app, player = build(tmp_path, sign_on=SIGN_ON)
    app.start()
    assert "colorbars.mp4" in played(player)


def test_sign_on_disabled_means_nothing_on_wake_either(tmp_path):
    app, player = build(
        tmp_path, sign_on={"enabled": False, "on_wake": True}
    )
    app.start()
    sleep_and_wake(app)
    assert "logo.mp4" not in played(player)
    assert app.signing_on is False
