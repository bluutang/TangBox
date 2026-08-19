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


# -- season and episode ------------------------------------------------------
#
# Reuses the same three forms detect_season() already understands, so a file the
# exclude_seasons filter can see is a file the banner can label.


def test_sxxexx():
    from nostalgiabox.channel import episode_label_for

    assert episode_label_for(Path("/m/Pocoyo/S01E04.mp4")) == "S01 E04"


def test_lowercase_and_separators():
    from nostalgiabox.channel import episode_label_for

    assert episode_label_for(Path("/m/Pocoyo/s6.e12 - title.mp4")) == "S06 E12"


def test_the_x_form():
    from nostalgiabox.channel import episode_label_for

    assert episode_label_for(Path("/m/Picapiedra/3x07 Rock Day.mp4")) == "S03 E07"


def test_season_from_the_folder_episode_from_the_file():
    """`Season 2/Episode 5` - the two halves live in different path components."""
    from nostalgiabox.channel import episode_label_for

    got = episode_label_for(Path("/m/Arthur/Season 2/Episode 5.mp4"))
    assert got == "S02 E05"


def test_episode_alone_when_there_is_no_season():
    """Plenty of rips are just 'Episode 12' in a flat folder."""
    from nostalgiabox.channel import episode_label_for

    assert episode_label_for(Path("/m/Pocoyo/Episode 12.mp4")) == "E12"


def test_a_film_has_no_label():
    from nostalgiabox.channel import episode_label_for

    assert episode_label_for(Path("/m/Cine/Mi Vecino Totoro.mp4")) is None


def test_a_year_in_the_title_is_not_an_episode():
    """'Toy Story 2 (1999)' must not become S19 E99 or E02."""
    from nostalgiabox.channel import episode_label_for

    assert episode_label_for(Path("/m/Cine/Toy Story 2 (1999).mp4")) is None


def test_the_banner_shows_the_episode_label():
    ass = _channel_bug_ass(
        2, "Los Pequeños", UiConfig(), show="Pocoyo", episode="S01 E04"
    )
    for expected in ("CH 02", "Los Pequeños", "Pocoyo", "S01 E04"):
        assert expected in ass


def test_the_banner_omits_the_episode_line_when_absent():
    ass = _channel_bug_ass(2, "Cine", UiConfig(), show="Totoro", episode=None)
    assert len(ass.strip().splitlines()) == 3


# -- during a commercial break -----------------------------------------------


def _app_with_ads(tmp_path):
    from nostalgiabox.app import TVApp
    from nostalgiabox.config import config_from_dict
    from nostalgiabox.input.manager import InputManager
    from nostalgiabox.player import MockPlayer
    from tests.helpers import FakeClock, make_show

    channel_dir = tmp_path / "Pequenos"
    make_show(channel_dir, "Pocoyo", 4)
    ads = tmp_path / "_ads"
    make_show(ads, "spots", 3)

    return TVApp(
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
                "commercials": {
                    "path": str(ads / "spots"),
                    "enabled": True,
                    "break_seconds": 60,
                },
            }
        ),
        MockPlayer(),
        InputManager([]),
        clock=FakeClock(),
    )


def test_the_banner_still_names_the_show_during_a_break(tmp_path):
    """Real broadcasters keep the channel bug up through the ads.

    Going quiet mid-break means a bare channel number for a minute at a time,
    and no way to tell what is coming back.
    """
    from nostalgiabox.actions import Action, InputEvent
    from nostalgiabox.overlay import _ID_CHANNEL
    from nostalgiabox.player import END_EOF

    app = _app_with_ads(tmp_path)
    app.start()
    app.player.finish_current(END_EOF)
    app.step()
    assert app.in_break, "expected a commercial break"

    app.handle_event(InputEvent(Action.INFO))
    banner = app.player.overlays[_ID_CHANNEL]
    assert "Los Pequeños" in banner
    assert "Pocoyo" in banner, f"break banner lost the show: {banner!r}"
