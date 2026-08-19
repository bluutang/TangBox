"""Showing WHICH programme is on, not just which channel.

This became necessary the moment a channel stopped being a single show. Until
2026-08-19 channel 2 *was* Dragon Tales, so "Los Pequeños" told you everything.
Now channel 2 holds eight different programmes and the channel name alone
doesn't tell a parent whether Pocoyó or Plaza Sésamo is playing.
"""

from __future__ import annotations

from pathlib import Path

from nostalgiabox.channel import show_name_for
from nostalgiabox.config import UiConfig
from nostalgiabox.overlay import _channel_bug_ass


# -- deriving the show from where the file lives -----------------------------


def test_the_show_is_the_folder_under_the_channel():
    assert (
        show_name_for(
            Path("/media/tangbox/Pequenos/Pocoyo/S01E04.mp4"),
            Path("/media/tangbox/Pequenos"),
        )
        == "Pocoyo"
    )


def test_season_subfolders_do_not_become_the_show_name():
    """`scan_recursive` means episodes are often two levels down."""
    assert (
        show_name_for(
            Path("/media/tangbox/Caricaturas/Los Picapiedra/Season 3/6x01.mp4"),
            Path("/media/tangbox/Caricaturas"),
        )
        == "Los Picapiedra"
    )


def test_an_episode_loose_in_the_channel_folder_has_no_show():
    """Nothing to name, so the banner should just omit the line."""
    assert (
        show_name_for(
            Path("/media/tangbox/Cine/Totoro.mp4"), Path("/media/tangbox/Cine")
        )
        is None
    )


def test_a_path_outside_the_channel_has_no_show():
    """Adverts live in _commercials, not under any channel."""
    assert (
        show_name_for(
            Path("/media/tangbox/_commercials/gansito.mp4"),
            Path("/media/tangbox/Pequenos"),
        )
        is None
    )


def test_accents_survive():
    """Folder names are the one place accents are allowed - see config.pi.yaml."""
    assert (
        show_name_for(
            Path("/media/tangbox/Pequenos/Plaza Sésamo/ep1.mp4"),
            Path("/media/tangbox/Pequenos"),
        )
        == "Plaza Sésamo"
    )


# -- what the banner draws ---------------------------------------------------


def test_the_banner_shows_the_programme(tmp_path):
    ass = _channel_bug_ass(2, "Los Pequeños", UiConfig(), show="Pocoyo")
    assert "CH 02" in ass
    assert "Los Pequeños" in ass
    assert "Pocoyo" in ass


def test_the_banner_omits_the_line_when_there_is_no_show():
    """Two lines, not three with a blank - no floating gap on screen."""
    ass = _channel_bug_ass(2, "Los Pequeños", UiConfig(), show=None)
    assert len(ass.strip().splitlines()) == 2


def test_the_show_line_is_smaller_than_the_channel_name():
    """Hierarchy: number biggest, channel next, programme smallest."""
    import re

    ass = _channel_bug_ass(2, "Los Pequeños", UiConfig(), show="Pocoyo")
    sizes = [int(m) for m in re.findall(r"\\fs(\d+)", ass)]
    assert sizes == sorted(sizes, reverse=True), f"sizes not descending: {sizes}"


def test_show_names_are_escaped_like_everything_else():
    """A brace in a folder name must not be read as an ASS override tag."""
    ass = _channel_bug_ass(2, "Chan", UiConfig(), show="Odd{Name}")
    assert r"\{" in ass or "Odd{Name}" not in ass


# -- the INFO button ---------------------------------------------------------


def test_pressing_info_names_the_programme_that_is_on(tmp_path):
    """INFO re-shows the banner, so it must name the show like tuning in does.

    This is the path a parent actually uses: the box has been on for an hour,
    something is playing, and you want to know what it is.
    """
    from nostalgiabox.actions import Action, InputEvent
    from nostalgiabox.app import TVApp
    from nostalgiabox.config import config_from_dict
    from nostalgiabox.input.manager import InputManager
    from nostalgiabox.player import MockPlayer
    from tests.helpers import FakeClock, make_show

    channel_dir = tmp_path / "Pequenos"
    make_show(channel_dir, "Pocoyo", 3)

    app = TVApp(
        config_from_dict(
            {
                "shuffle_seed": 7,
                "start_channel": 2,
                "start_offset": 0,
                "power_off_command": [],
                "scan_recursive": True,
                "channels": [
                    {"number": 2, "name": "Los Pequeños", "path": str(channel_dir)}
                ],
            }
        ),
        MockPlayer(),
        InputManager([]),
        clock=FakeClock(),
    )
    app.start()
    app.handle_event(InputEvent(Action.INFO))

    from nostalgiabox.overlay import _ID_CHANNEL

    banner = app.player.overlays[_ID_CHANNEL]
    assert "Los Pequeños" in banner
    assert "Pocoyo" in banner, f"INFO banner did not name the show: {banner!r}"
