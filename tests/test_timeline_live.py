"""The timeline moves while you are looking at it.

Press ☰ and the banner carries a progress bar and the time left. Until now it
was drawn once and then sat there, so what you saw was a photograph of the
moment you pressed the button - noticed on a television 2026-08-23: "it is not
live, it is a snapshot of when i pressed the button".

A progress bar that does not progress is not a progress bar.

Only the INFO banner does this. A channel change draws the same banner WITHOUT
a timeline, and that one must stay exactly as it always has - it is what the
children see all evening, and redrawing it would be motion for nothing.
"""

from __future__ import annotations

from nostalgiabox.actions import Action, InputEvent
from nostalgiabox.app import TVApp
from nostalgiabox.config import config_from_dict
from nostalgiabox.input.manager import InputManager
from nostalgiabox.overlay import format_remaining
from nostalgiabox.player import MockPlayer
from tests.helpers import FakeClock, make_show

_ID_CHANNEL = 1


def build(tmp_path, **overrides):
    make_show(tmp_path, "dragon", 3)
    clock = FakeClock()
    data = {
        "shuffle_seed": 7,
        "start_channel": 2,
        "start_offset": 0,
        "initial_volume": 5,
        "channel_bug_seconds": 10,
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
        sleep=lambda _s: None,
    )
    return app, clock, app.player


def press_info(app):
    app.handle_event(InputEvent(Action.INFO))


def banner(player):
    return player.overlays.get(_ID_CHANNEL)


def playing(player, *, position, runtime=22 * 60):
    player.time_pos = position
    player.duration = runtime


# --- the new behaviour -----------------------------------------------------


def test_the_timeline_redraws_as_the_episode_plays(tmp_path):
    app, clock, player = build(tmp_path)
    app.start()
    playing(player, position=60)
    press_info(app)
    first = banner(player)

    playing(player, position=120)
    clock.advance(1.0)
    app.step()

    assert banner(player) != first


def test_the_redrawn_banner_shows_the_new_time_remaining(tmp_path):
    """Not just 'it changed' - it changed to the RIGHT thing."""
    app, clock, player = build(tmp_path)
    app.start()
    playing(player, position=60)
    press_info(app)
    assert format_remaining(22 * 60 - 60) in banner(player)

    playing(player, position=120)
    clock.advance(1.0)
    app.step()

    assert format_remaining(22 * 60 - 120) in banner(player)


def test_it_stops_once_the_banner_has_gone(tmp_path):
    """The redraw must not resurrect a banner that has timed out."""
    app, clock, player = build(tmp_path, channel_bug_seconds=4)
    app.start()
    playing(player, position=60)
    press_info(app)

    clock.advance(5.0)
    app.step()

    assert banner(player) is None


def test_redrawing_does_not_keep_the_banner_alive_forever(tmp_path):
    """Each redraw must inherit the original deadline, not restart it."""
    app, clock, player = build(tmp_path, channel_bug_seconds=4)
    app.start()
    playing(player, position=60)
    press_info(app)

    for _ in range(6):
        clock.advance(1.0)
        playing(player, position=player.time_pos + 1)
        app.step()

    assert banner(player) is None


def test_a_channel_change_banner_is_left_alone(tmp_path):
    """No timeline on it, so nothing to animate - and it must not flicker."""
    app, clock, player = build(tmp_path)
    app.start()
    playing(player, position=60)
    app.overlay.show_channel_bug(2, "Dragon Tales")
    first = banner(player)

    playing(player, position=120)
    clock.advance(1.0)
    app.step()

    assert banner(player) == first


def test_standby_stops_the_redraw(tmp_path):
    app, clock, player = build(tmp_path)
    app.start()
    playing(player, position=60)
    press_info(app)

    app.handle_event(InputEvent(Action.POWER))
    clock.advance(1.0)
    app.step()

    assert banner(player) is None


def test_a_programme_of_unknown_length_still_draws_no_timeline(tmp_path):
    """Unchanged behaviour: no runtime, no bar, and nothing to redraw."""
    app, clock, player = build(tmp_path)
    app.start()
    player.time_pos = 60
    player.duration = 0
    press_info(app)
    first = banner(player)

    clock.advance(1.0)
    app.step()

    assert banner(player) == first
