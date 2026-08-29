"""Adult mode: browse channel -> show -> episode and pick one.

Pure state, like Guide - no player, no clock, no drawing - so every rule can be
tested with no television attached.

The guarantee Guide works hardest for does NOT apply here in the same way: this
is driven by an adult who can read, so a cursor may sit still at a list edge
rather than wrapping. What must hold instead is that you can always get BACK
out, from any depth, without the box ending up somewhere with nothing on it.
"""

from pathlib import Path

import pytest

from nostalgiabox.browser import Browser

# channel -> shows -> episodes
TREE = [
    ("Nick Jr", [
        ("Franklin", [Path(f"/m/NickJr/Franklin/S01E{n:02d}.mp4") for n in (1, 2, 3)]),
        ("Blue", [Path("/m/NickJr/Blue/S01E01.mp4")]),
    ]),
    ("Disney", [
        ("Kim Possible", [Path(f"/m/Disney/KP/S01E{n:02d}.mp4") for n in (1, 2)]),
    ]),
]


def b():
    return Browser(TREE)


# --- moving ----------------------------------------------------------------

def test_starts_on_the_first_channel():
    assert b().level == "channel"
    assert b().current_label == "Nick Jr"


def test_down_moves_to_the_next_channel():
    x = b(); x.down()
    assert x.current_label == "Disney"


def test_cursor_stops_at_the_end_rather_than_wrapping():
    """An adult reading a list expects it to stop, not loop silently."""
    x = b(); x.down(); x.down(); x.down()
    assert x.current_label == "Disney"


def test_up_stops_at_the_top():
    x = b(); x.up()
    assert x.current_label == "Nick Jr"


# --- descending and returning ----------------------------------------------

def test_enter_descends_to_shows():
    x = b(); x.enter()
    assert x.level == "show"
    assert x.current_label == "Franklin"


def test_enter_again_descends_to_episodes():
    x = b(); x.enter(); x.enter()
    assert x.level == "episode"


def test_choosing_an_episode_returns_its_path():
    x = b(); x.enter(); x.enter()
    assert x.enter() == Path("/m/NickJr/Franklin/S01E01.mp4")


def test_back_returns_to_the_level_above():
    x = b(); x.enter(); x.enter(); x.back()
    assert x.level == "show"


def test_back_from_the_top_signals_exit():
    x = b()
    assert x.back() is False          # nothing above the channel list


def test_descending_remembers_where_you_were():
    """Go into a show, come back, and the channel cursor has not moved."""
    x = b(); x.down(); x.enter(); x.back()
    assert x.current_label == "Disney"


# --- the episode that follows ----------------------------------------------

def test_knows_the_next_episode_in_the_show():
    """When one finishes the box plays the next in order, not a random one."""
    x = b(); x.enter(); x.enter(); x.enter()
    assert x.next_episode() == Path("/m/NickJr/Franklin/S01E02.mp4")


def test_the_last_episode_has_no_next():
    x = b(); x.enter(); x.enter()
    x.down(); x.down()                # to S01E03
    x.enter()
    assert x.next_episode() is None


# --- nothing to show -------------------------------------------------------

def test_a_channel_with_no_shows_cannot_be_entered():
    x = Browser([("Empty", [])])
    assert x.enter() is None
    assert x.level == "channel"
