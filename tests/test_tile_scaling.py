"""Tile pictures are placed in DISPLAY pixels, not canvas units.

Overlays are authored on a fixed 1280x720 virtual canvas which mpv scales up to
whatever the television is. Text and shapes ride that scaling for free, because
they are ASS and ASS is told its own resolution alongside the events. Pictures
do not: mpv positions image overlays in real display pixels.

Handing canvas coordinates straight to an image overlay therefore draws every
picture at canvas/display of its intended position AND size - on a 1080p screen
exactly two thirds, bunched toward the top-left, which is what a photograph of
the television showed on 2026-08-23.

No test on a laptop could have caught it: `scripts/render-overlay.py` uses
mpv's `--vo=image`, which renders AT canvas size, so the scale factor is 1 and
the bug cannot appear. Hence a pure function, tested at the sizes that matter.
"""

from nostalgiabox.guide import art_rect, page_tiles
from nostalgiabox.player import scale_to_display

CANVAS = (1280, 720)

# A tile picture on the canvas. Deliberately avoids coordinates that land on a
# half pixel when scaled, so the test asserts the mapping and not the rounding.
RECT = (76, 44, 264, 198)


def test_a_720p_display_needs_no_scaling_at_all():
    assert scale_to_display(*RECT, canvas=CANVAS, display=(1280, 720)) == RECT


def test_1080p_scales_by_one_and_a_half():
    assert scale_to_display(*RECT, canvas=CANVAS, display=(1920, 1080)) == (
        114,
        66,
        396,
        297,
    )


def test_4k_scales_by_three():
    assert scale_to_display(*RECT, canvas=CANVAS, display=(3840, 2160)) == (
        228,
        132,
        792,
        594,
    )


def test_an_unknown_display_leaves_the_rectangle_alone():
    """A picture in the wrong place beats no picture at all.

    mpv may not know its own output size yet - the guide can be opened before
    a frame has been rendered. Falling back to canvas units puts the artwork
    where it used to be rather than throwing it away.
    """
    assert scale_to_display(*RECT, canvas=CANVAS, display=None) == RECT


def test_a_nonsense_display_size_is_ignored_rather_than_dividing_by_zero():
    assert scale_to_display(*RECT, canvas=CANVAS, display=(0, 0)) == RECT


def test_the_real_four_channel_tile_lands_at_the_size_the_guide_intends():
    """End to end against the guide's own geometry, at Brian's resolution.

    Four channels give a 2x2 of 333x305 tiles - the tile hugs its picture - so
    the picture area is 333x250 on the canvas. The Pi is pinned to 1080p, so
    the television gets 500x375, which is what 1024x768 artwork is scaled down
    to and therefore the size worth judging legibility at.
    """
    x, y, w, h = art_rect(page_tiles(4, 0)[0])
    _, _, sw, sh = scale_to_display(x, y, w, h, canvas=CANVAS, display=(1920, 1080))
    assert (sw, sh) == (500, 375)
