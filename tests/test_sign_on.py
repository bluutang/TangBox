"""The sign-on sequence: colour bars, then a station logo, then the first channel.

How a television station used to start the broadcast day, and the reason the box
feels like a telly rather than a computer playing video files.

Two things drive the design and are worth stating, because they are easy to
forget once the artwork looks nice:

* This plays EVERY time the box is switched on, in front of a 2- and a
  4-year-old who want cartoons. It has to be short, and it has to be skippable.
* It runs before anything else, so a failure here means no television at all.
  A missing or broken logo must degrade to "just tune in", never to a black
  screen.
"""

from __future__ import annotations

import pytest

from nostalgiabox.actions import Action, InputEvent
from nostalgiabox.app import TVApp
from nostalgiabox.config import config_from_dict
from nostalgiabox.input.manager import InputManager
from nostalgiabox.player import END_EOF, MockPlayer
from tests.helpers import FakeClock, make_show


def build(tmp_path, *, assets=("colorbars.mp4", "logo.mp4"), **overrides):
    make_show(tmp_path, "dragon", 4)
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir(exist_ok=True)
    for name in assets:
        (assets_dir / name).write_bytes(b"\x00")

    data = {
        "shuffle_seed": 7,
        "start_channel": 2,
        "start_offset": 0,
        "power_off_command": [],
        "channels": [
            {"number": 2, "name": "Dragon Tales", "path": str(tmp_path / "dragon")},
        ],
        "sign_on": {"enabled": True, "bars_seconds": 2.0},
    }
    data.update(overrides)
    clock = FakeClock()
    player = MockPlayer()
    app = TVApp(
        config_from_dict(data),
        player,
        InputManager([]),
        clock=clock,
        assets_dir=assets_dir,
    )
    return app, player, clock, assets_dir


def played_names(player):
    return [p.name for p, _ in player.played]


# -- the happy path ---------------------------------------------------------


def test_starts_on_colour_bars_not_on_a_channel(tmp_path):
    app, player, _, assets = build(tmp_path)
    app.start()
    assert player.looping == assets / "colorbars.mp4"
    assert played_names(player) == [], "an episode started before the sign-on finished"


def test_bars_give_way_to_the_logo(tmp_path):
    app, player, clock, assets = build(tmp_path)
    app.start()
    clock.advance(2.0)
    app.step()
    assert played_names(player) == ["logo.mp4"]


def test_bars_hold_until_their_time_is_up(tmp_path):
    app, player, clock, _ = build(tmp_path)
    app.start()
    clock.advance(1.0)
    app.step()
    assert played_names(player) == [], "logo appeared early"


def test_when_the_logo_ends_the_first_channel_tunes_in(tmp_path):
    app, player, clock, _ = build(tmp_path)
    app.start()
    clock.advance(2.0)
    app.step()
    player.finish_current(END_EOF)
    app.step()
    assert app.lineup.current.number == 2
    assert played_names(player)[-1].startswith("dragon")


def test_the_logo_ending_does_not_skip_an_episode(tmp_path):
    """The logo finishing means 'sign-on over', not 'that episode ended'."""
    app, player, clock, _ = build(tmp_path)
    app.start()
    clock.advance(2.0)
    app.step()
    player.finish_current(END_EOF)
    app.step()
    episodes = [n for n in played_names(player) if n.startswith("dragon")]
    assert len(episodes) == 1, f"expected one episode, got {episodes}"


# -- it must be skippable ---------------------------------------------------


def test_any_button_skips_the_sign_on(tmp_path):
    """Charming on Tuesday, unbearable by Friday. Let people out of it."""
    app, player, _, _ = build(tmp_path)
    app.start()
    app.handle_event(InputEvent(Action.CHANNEL_UP))
    assert played_names(player)[-1].startswith("dragon")


def test_quit_during_the_sign_on_still_quits(tmp_path):
    app, player, _, _ = build(tmp_path)
    app.start()
    app._running = True
    app.handle_event(InputEvent(Action.QUIT))
    assert app._running is False


def test_a_skip_does_not_also_change_channel(tmp_path):
    """The press that escapes the sign-on is consumed by it."""
    app, player, _, _ = build(tmp_path)
    app.start()
    app.handle_event(InputEvent(Action.CHANNEL_UP))
    assert app.lineup.current.number == 2


# -- degrading gracefully ---------------------------------------------------


def test_disabled_tunes_straight_in(tmp_path):
    """The behaviour every existing install had before this feature."""
    app, player, _, _ = build(tmp_path, sign_on={"enabled": False})
    app.start()
    assert played_names(player)[-1].startswith("dragon")


def test_a_missing_logo_falls_back_to_bars_then_tunes(tmp_path):
    app, player, clock, _ = build(tmp_path, assets=("colorbars.mp4",))
    app.start()
    clock.advance(2.0)
    app.step()
    assert played_names(player)[-1].startswith("dragon")


def test_no_assets_at_all_still_gives_television(tmp_path):
    """A broken sign-on must never mean a black screen."""
    app, player, _, _ = build(tmp_path, assets=())
    app.start()
    assert played_names(player)[-1].startswith("dragon")


def test_zero_bars_seconds_goes_straight_to_the_logo(tmp_path):
    app, player, _, _ = build(tmp_path, sign_on={"enabled": True, "bars_seconds": 0})
    app.start()
    assert played_names(player) == ["logo.mp4"]


# -- config -----------------------------------------------------------------


def test_config_defaults(tmp_path):
    make_show(tmp_path, "dragon", 1)
    cfg = config_from_dict(
        {"channels": [{"number": 2, "name": "D", "path": str(tmp_path / "dragon")}]}
    )
    # Off unless asked for: this runs before any television happens.
    assert cfg.sign_on.enabled is False
    assert cfg.sign_on.bars_seconds == 2.0
    assert cfg.sign_on.logo == "logo.mp4"


def test_config_reads_the_block(tmp_path):
    make_show(tmp_path, "dragon", 1)
    cfg = config_from_dict(
        {
            "channels": [{"number": 2, "name": "D", "path": str(tmp_path / "dragon")}],
            "sign_on": {"enabled": False, "bars_seconds": 5, "logo": "ident.mp4"},
        }
    )
    assert cfg.sign_on.enabled is False
    assert cfg.sign_on.bars_seconds == 5.0
    assert cfg.sign_on.logo == "ident.mp4"


def test_absurd_bars_seconds_is_clamped(tmp_path):
    """Nobody wants a five-minute ident before the cartoons."""
    make_show(tmp_path, "dragon", 1)
    cfg = config_from_dict(
        {
            "channels": [{"number": 2, "name": "D", "path": str(tmp_path / "dragon")}],
            "sign_on": {"enabled": True, "bars_seconds": 999},
        }
    )
    assert cfg.sign_on.bars_seconds <= 30


def test_a_bad_sign_on_block_is_rejected(tmp_path):
    from nostalgiabox.config import ConfigError

    make_show(tmp_path, "dragon", 1)
    with pytest.raises(ConfigError):
        config_from_dict(
            {
                "channels": [{"number": 2, "name": "D", "path": str(tmp_path / "dragon")}],
                "sign_on": "yes please",
            }
        )


# -- the CRT power-on zap ----------------------------------------------------
#
# A telly doesn't cut to a picture, it blooms into one: a dot opens to a line,
# the line opens to the frame. The zap runs BEFORE everything else, so it is
# the very first thing the screen does.


def build_zap(tmp_path, *, assets=("power_on.mp4", "colorbars.mp4", "logo.mp4"), **over):
    return build(tmp_path, assets=assets, **over)


def test_the_zap_plays_first(tmp_path):
    app, player, _, assets = build_zap(tmp_path)
    app.start()
    assert played_names(player) == ["power_on.mp4"]


def test_the_zap_hands_over_to_the_bars(tmp_path):
    app, player, _, _ = build_zap(tmp_path)
    app.start()
    player.finish_current(END_EOF)
    app.step()
    assert player.looping is not None and player.looping.name == "colorbars.mp4"


def test_zap_then_logo_when_bars_are_off(tmp_path):
    """bars_seconds: 0 is the real Pi config - straight to the ident."""
    app, player, _, _ = build_zap(
        tmp_path, sign_on={"enabled": True, "bars_seconds": 0}
    )
    app.start()
    player.finish_current(END_EOF)
    app.step()
    assert played_names(player) == ["power_on.mp4", "logo.mp4"]


def test_the_whole_sequence_ends_on_a_channel(tmp_path):
    app, player, _, _ = build_zap(
        tmp_path, sign_on={"enabled": True, "bars_seconds": 0}
    )
    app.start()
    player.finish_current(END_EOF)   # zap done
    app.step()
    player.finish_current(END_EOF)   # ident done
    app.step()
    assert played_names(player)[-1].startswith("dragon")


def test_a_missing_zap_asset_just_skips_it(tmp_path):
    """Every stage is optional. A missing file must never cost the cartoons."""
    app, player, _, _ = build_zap(
        tmp_path,
        assets=("logo.mp4",),
        sign_on={"enabled": True, "bars_seconds": 0},
    )
    app.start()
    assert played_names(player) == ["logo.mp4"]


def test_a_button_skips_the_zap_too(tmp_path):
    app, player, _, _ = build_zap(tmp_path)
    app.start()
    app.handle_event(InputEvent(Action.CHANNEL_UP))
    assert played_names(player)[-1].startswith("dragon")


def test_the_zap_ending_does_not_burn_an_episode(tmp_path):
    """Same trap as the ident: an end-of-clip here is a cue, not a finished show."""
    app, player, _, _ = build_zap(
        tmp_path, sign_on={"enabled": True, "bars_seconds": 0}
    )
    app.start()
    player.finish_current(END_EOF)
    app.step()
    player.finish_current(END_EOF)
    app.step()
    episodes = [n for n in played_names(player) if n.startswith("dragon")]
    assert len(episodes) == 1, f"expected one episode, got {episodes}"


def test_config_default_zap_filename(tmp_path):
    make_show(tmp_path, "dragon", 1)
    cfg = config_from_dict(
        {"channels": [{"number": 2, "name": "D", "path": str(tmp_path / "dragon")}]}
    )
    assert cfg.sign_on.power_on == "power_on.mp4"
