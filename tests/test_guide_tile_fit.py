"""A tile should be no wider than the picture it holds.

Tiles used to stretch to fill the canvas width. With four channels that made
each one 552 wide while the picture inside could only ever be 280 - the
picture is limited by the tile's HEIGHT, because a text band sits under it and
the artwork is 4:3. The result was a tile roughly half full, photographed on
the television 2026-08-24: 204 screen pixels of dead space either side of
every picture.

Widening the picture instead is not an option. It would have to be cropped to
the tile's 1.81:1, losing about 44% of its height - faces sliced off - and it
would invalidate the 1024x768 4:3 artwork spec and the tile cutter built
around it.

So the tile shrinks to its picture, and the space that frees up becomes gaps
and margins. The programme playing behind the guide shows through more, which
is what Brian asked for: "decrease the size of the tile canvas a bit so we can
see more of the background".
"""

from nostalgiabox.guide import art_rect, page_tiles
from nostalgiabox.overlay import CANVAS_H, CANVAS_W


def tiles(count, cursor=0):
    return page_tiles(count, cursor)


# --- the point of the change ----------------------------------------------


def test_a_tile_is_no_wider_than_its_picture(tmp_path=None):
    for count in (4, 5, 6, 8):
        t = tiles(count)[0]
        _x, _y, w, _h = art_rect(t)
        assert w == t.w, f"{count} channels: picture {w:.0f} in a {t.w:.0f} tile"


def test_the_picture_fills_the_tile_width():
    t = tiles(4)[0]
    _x, _y, w, _h = art_rect(t)
    assert w / t.w == 1.0


def test_more_of_the_programme_shows_through():
    """Measured by AREA covered, not by span.

    The tiles keep their positions across the canvas - moving them would cost
    a child the only cue they have - so the grid still reaches both edges. What
    changes is how much of the screen the tiles actually cover.
    """
    got = tiles(4)
    covered = sum(t.w * t.h for t in got) / (CANVAS_W * CANVAS_H)
    # 73% before the tiles were shrunk to their pictures, 37% after, 49% once
    # the pictures were made as large as the height allows, and 58% now the
    # text band is gone and the picture IS the tile. The point is that the
    # tiles no longer blanket the screen - not a race to the smallest, and the
    # band was never programme showing through anyway, it was a black strip.
    assert covered < 0.65


def test_the_row_is_centred():
    row = [t for t in tiles(4) if t.y == tiles(4)[0].y]
    left = min(t.x for t in row)
    right = CANVAS_W - max(t.x + t.w for t in row)
    assert abs(left - right) < 1.0


# --- what must NOT change --------------------------------------------------


def test_the_picture_is_the_size_the_artwork_spec_assumes():
    """421x316 on the canvas, so 632x474 on a 1080p screen.

    The history of this one number: 280x210, then 358x269 once the text band
    was narrowed from 0.3125 to 0.18, and now 421x316 with the band gone
    altogether and the name moved onto the picture.

    On the real box - ten channels at 2x2 paging - it is 399x299, or 598x449
    on a 1080p screen, because more channels mean a page turn rather than
    smaller tiles.

    1024x768 artwork still covers all of these (about 1.7x oversampled at the
    largest), so the RECOMMENDATION is unchanged. The number quoted as "actual
    size" is not, and both published artifacts still say 419x315.
    """
    _x, _y, w, h = art_rect(tiles(4)[0])
    assert (round(w), round(h)) == (421, 316)


def test_tiles_still_fit_when_there_are_many_columns():
    """A tile must never grow past the slot it has, however few channels."""
    for count in (2, 3, 4, 5, 8, 9, 17):
        for t in tiles(count):
            assert t.x >= 0
            assert t.x + t.w <= CANVAS_W + 0.5


def test_rows_do_not_overlap():
    got = tiles(8)
    rows = sorted({round(t.y) for t in got})
    for a, b in zip(rows, rows[1:]):
        height = next(t.h for t in got if round(t.y) == a)
        assert a + height <= b + 0.5


def test_every_channel_still_gets_a_tile():
    assert len(tiles(4)) == 4
    assert len(tiles(8)) == 8
