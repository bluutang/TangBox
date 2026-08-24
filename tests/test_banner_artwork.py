"""The info banner carries the show's picture, not just its name.

Press ☰ and the banner tells you the channel, the programme, the episode and
how long is left - all of it words. Neither child in this house can read any of
it, which makes the one overlay they might most want to check the one that
helps them least.

The guide already solved this: a picture per show, found at
`<channel>/<show>/tile.jpg`. The banner uses the same picture at the same size
a guide tile draws it (280x210 on the canvas), so a show looks the same in both
places and one `tile.jpg` serves both.

It sits to the LEFT of the text, in the space the progress bar does not reach.
"""

from __future__ import annotations

from nostalgiabox.actions import Action, InputEvent
from nostalgiabox.app import BANNER_ART_SLOT, TVApp
from nostalgiabox.config import config_from_dict
from nostalgiabox.input.manager import InputManager
from nostalgiabox.overlay import CANVAS_W, banner_art_rect
from nostalgiabox.player import MockPlayer
from tests.helpers import FakeClock, make_show


def build(tmp_path, *, tile=True, **overrides):
    show = make_show(tmp_path / "chan", "Pocoyo", 3)
    if tile:
        (show / "tile.jpg").write_bytes(b"\x00")
    data = {
        "shuffle_seed": 7,
        "start_channel": 2,
        "start_offset": 0,
        "initial_volume": 5,
        "channel_bug_seconds": 8,
        "channels": [
            {"number": 2, "name": "Los Pequeños", "path": str(tmp_path / "chan")}
        ],
    }
    data.update(overrides)
    app = TVApp(
        config_from_dict(data),
        MockPlayer(),
        InputManager([]),
        clock=FakeClock(),
        sleep=lambda _s: None,
    )
    return app, app.player


def press_info(app):
    app.handle_event(InputEvent(Action.INFO))


def banner_art(player):
    return player.images.get(BANNER_ART_SLOT)


# --- where it goes ---------------------------------------------------------


def test_the_picture_is_a_guide_tile_size():
    _x, _y, w, h = banner_art_rect()
    assert (round(w), round(h)) == (280, 210)


def test_it_sits_left_of_the_progress_bar():
    x, _y, w, _h = banner_art_rect()
    assert x > 0
    assert x + w < CANVAS_W * 0.56, "must not run into the bar or the text"


# --- the new behaviour -----------------------------------------------------


def test_pressing_info_shows_the_shows_picture(tmp_path):
    app, player = build(tmp_path)
    app.start()
    press_info(app)
    art = banner_art(player)
    assert art is not None
    assert art[0].name == "tile.jpg"


def test_the_picture_lands_where_the_rect_says(tmp_path):
    app, player = build(tmp_path)
    app.start()
    press_info(app)
    _path, x, y, w, h = banner_art(player)
    rx, ry, rw, rh = banner_art_rect()
    assert (x, y, w, h) == (round(rx), round(ry), round(rw), round(rh))


def test_a_show_with_no_picture_draws_none(tmp_path):
    app, player = build(tmp_path, tile=False)
    app.start()
    press_info(app)
    assert banner_art(player) is None


def test_the_picture_goes_when_the_banner_does(tmp_path):
    app, player = build(tmp_path, channel_bug_seconds=4)
    app.start()
    press_info(app)
    assert banner_art(player) is not None

    app._clock.advance(5)
    app.step()

    assert banner_art(player) is None


# --- what must not change --------------------------------------------------


def test_a_channel_change_banner_carries_no_picture(tmp_path):
    """Tuning looks exactly as it always has - that is what the kids see."""
    app, player = build(tmp_path)
    app.start()
    app.overlay.show_channel_bug(2, "Los Pequeños")
    assert banner_art(player) is None


def test_the_banner_does_not_disturb_guide_pictures(tmp_path):
    """They use different slots, so one cannot wipe the other."""
    app, player = build(tmp_path)
    app.start()
    player.images[0] = ("guide-tile", 0, 0, 10, 10)
    press_info(app)
    assert player.images.get(0) == ("guide-tile", 0, 0, 10, 10)
