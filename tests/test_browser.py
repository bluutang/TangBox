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


# --- building the tree from the real config --------------------------------

from nostalgiabox.browser import tree_from_config          # noqa: E402
from nostalgiabox.config import config_from_dict           # noqa: E402
from tests.helpers import make_show                        # noqa: E402


def _cfg(tmp_path, **overrides):
    nick = tmp_path / "NickJr"
    make_show(nick, "Franklin", 3)
    make_show(nick, "Blue", 1)
    disney = tmp_path / "Disney"
    make_show(disney, "Kim Possible", 2)
    (tmp_path / "Empty").mkdir()
    data = {"channels": [
        {"number": 5, "name": "Nick Jr", "path": str(nick)},
        {"number": 10, "name": "Disney", "path": str(disney)},
        {"number": 99, "name": "Empty", "path": str(tmp_path / "Empty")},
    ]}
    data.update(overrides)
    return config_from_dict(data)


def test_tree_groups_episodes_under_their_show(tmp_path):
    tree = tree_from_config(_cfg(tmp_path))
    names = {chan: [s for s, _ in shows] for chan, shows in tree}
    assert names["Nick Jr"] == ["Blue", "Franklin"]      # alphabetical
    assert names["Disney"] == ["Kim Possible"]


def test_tree_keeps_every_episode_of_a_show(tmp_path):
    tree = tree_from_config(_cfg(tmp_path))
    shows = dict(dict(tree)["Nick Jr"])
    assert len(shows["Franklin"]) == 3


def test_a_channel_with_nothing_on_it_is_left_out(tmp_path):
    """An empty row is useless to someone browsing for something to watch."""
    tree = tree_from_config(_cfg(tmp_path))
    assert "Empty" not in dict(tree)


def test_loose_episodes_are_still_reachable(tmp_path):
    """Files sitting directly in a channel folder, with no show folder.

    They must not silently vanish from the browser, so they are grouped under
    the channel's own name rather than dropped.
    """
    loose = tmp_path / "Loose"
    loose.mkdir()
    (loose / "something.mp4").write_bytes(b"\x00")
    cfg = config_from_dict(
        {"channels": [{"number": 2, "name": "Loose", "path": str(loose)}]}
    )
    tree = tree_from_config(cfg)
    assert dict(dict(tree)["Loose"])["Loose"]


def test_the_tree_feeds_the_browser(tmp_path):
    """The two halves fit together without any adapting in between."""
    br = Browser(tree_from_config(_cfg(tmp_path)))
    assert br.current_label in ("Nick Jr", "Disney")
    br.enter()
    assert br.level == "show"


def test_working_folders_are_not_shows(tmp_path):
    """_staging, _split and friends hold work in progress, not programmes.

    They are real folders full of real video files, so nothing else filters
    them out - but an episode still being processed must not be offered as
    something to watch.
    """
    chan = tmp_path / "Chan"
    make_show(chan, "Franklin", 2)
    make_show(chan, "_staging", 5)
    make_show(chan, "_split", 3)
    cfg = config_from_dict(
        {"channels": [{"number": 2, "name": "Chan", "path": str(chan)}]}
    )
    shows = dict(dict(tree_from_config(cfg))["Chan"])
    assert list(shows) == ["Franklin"]


# --- drawing the list ------------------------------------------------------

from nostalgiabox.browser import ROWS_PER_PAGE, list_ass   # noqa: E402
from nostalgiabox.config import UiConfig                   # noqa: E402


def _ui():
    return UiConfig()


def test_the_heading_says_where_you_are():
    ass = list_ass("Nick Jr", ["Franklin", "Blue"], 0, _ui())
    assert "Nick Jr" in ass


def test_every_item_of_a_short_list_is_drawn():
    ass = list_ass("Nick Jr", ["Franklin", "Blue"], 0, _ui())
    assert "Franklin" in ass and "Blue" in ass


def test_the_picture_behind_is_dimmed():
    """A menu over full-brightness video is unreadable."""
    assert "\\p1" in list_ass("X", ["a"], 0, _ui())


def test_a_long_list_draws_only_one_page():
    items = [f"Episode {n:02d}" for n in range(1, 82)]      # Kim Possible has 81
    ass = list_ass("Kim Possible", items, 0, _ui())
    drawn = sum(1 for i in items if i in ass)
    assert drawn <= ROWS_PER_PAGE


def test_the_page_follows_the_cursor():
    """Selecting episode 70 must not draw episodes 1-12 and hide the cursor."""
    items = [f"Episode {n:02d}" for n in range(1, 82)]
    ass = list_ass("Kim Possible", items, 69, _ui())
    assert "Episode 70" in ass
    assert "Episode 01" not in ass


def test_position_is_shown_for_a_long_list():
    """Otherwise there is no way to tell 12 of 81 from 12 of 12."""
    items = [f"Episode {n:02d}" for n in range(1, 82)]
    ass = list_ass("Kim Possible", items, 69, _ui())
    assert "70" in ass and "81" in ass


def test_an_empty_list_says_so_rather_than_drawing_nothing():
    ass = list_ass("Empty", [], 0, _ui())
    assert "Empty" in ass
    assert len(ass) > 0
