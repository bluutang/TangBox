"""The episode timeline: a progress bar and time remaining, in the info banner.

Only the info button draws it. A channel change flashes the same banner without
it, so tuning looks exactly as it always has - which is what the kids see.
"""

from nostalgiabox.overlay import format_remaining


def test_remaining_reads_as_minutes_and_seconds():
    assert format_remaining(492) == "8:12"


def test_remaining_under_a_minute_keeps_the_zero():
    assert format_remaining(5) == "0:05"


def test_a_film_gets_an_hours_field():
    assert format_remaining(5380) == "1:29:40"


def test_the_very_end_is_not_negative():
    assert format_remaining(-3) == "0:00"


from nostalgiabox.overlay import bar_fill  # noqa: E402


def test_a_fresh_episode_has_an_empty_bar():
    assert bar_fill(0, 600, 400) == 0


def test_halfway_fills_half_the_bar():
    assert bar_fill(300, 600, 400) == 200


def test_the_end_fills_it_completely():
    assert bar_fill(600, 600, 400) == 400


def test_a_position_past_the_end_cannot_overflow():
    assert bar_fill(9999, 600, 400) == 400


def test_an_unknown_length_fills_nothing():
    assert bar_fill(120, 0, 400) == 0


# --- the banner ------------------------------------------------------------

from nostalgiabox.config import config_from_dict  # noqa: E402
from nostalgiabox.overlay import OverlayManager  # noqa: E402
from nostalgiabox.player import MockPlayer  # noqa: E402
from tests.helpers import FakeClock, make_show  # noqa: E402


def _overlay(tmp_path):
    make_show(tmp_path, "a", 1)
    config = config_from_dict(
        {
            "channel_bug_seconds": 4,
            "channels": [{"number": 3, "name": "Arthur", "path": str(tmp_path / "a")}],
        }
    )
    player = MockPlayer()
    return OverlayManager(player, config, clock=FakeClock()), player


def test_banner_without_progress_draws_no_bar(tmp_path):
    om, player = _overlay(tmp_path)
    om.show_channel_bug(3, "Arthur", show="Arthur")
    assert "\\p1" not in player.overlays[1], "a channel change must look as it always has"


def test_banner_with_progress_shows_the_time_left(tmp_path):
    om, player = _overlay(tmp_path)
    om.show_channel_bug(3, "Arthur", show="Arthur", position=108, runtime=600)
    assert "8:12" in player.overlays[1]


def test_banner_with_progress_draws_a_bar(tmp_path):
    om, player = _overlay(tmp_path)
    om.show_channel_bug(3, "Arthur", show="Arthur", position=108, runtime=600)
    assert "\\p1" in player.overlays[1], "the bar is an ASS drawing"


def test_an_unknown_length_falls_back_to_the_plain_banner(tmp_path):
    om, player = _overlay(tmp_path)
    om.show_channel_bug(3, "Arthur", show="Arthur", position=108, runtime=0)
    ass = player.overlays[1]
    assert "\\p1" not in ass and "0:00" not in ass


# --- end to end, through the app -------------------------------------------

from nostalgiabox.actions import Action  # noqa: E402
from tests.test_app import build_app, send  # noqa: E402


def test_player_reports_no_length_before_anything_plays():
    assert MockPlayer().get_duration() is None


def test_info_button_draws_the_timeline(tmp_path):
    app, player, _ = build_app(tmp_path)
    app.start()
    player.duration = 600.0
    player.time_pos = 108.0
    send(app, Action.INFO)
    assert "8:12" in player.overlays[1]


def test_changing_channel_leaves_the_banner_alone(tmp_path):
    app, player, _ = build_app(tmp_path)
    app.start()
    player.duration = 600.0
    player.time_pos = 108.0
    send(app, Action.CHANNEL_UP)
    assert "8:12" not in player.overlays[1]
    assert "\\p1" not in player.overlays[1]
