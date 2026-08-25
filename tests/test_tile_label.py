"""The caption burned into a guide tile's picture.

It has to be burned in rather than drawn over: mpv composites bitmap overlays
above ASS ones and the order cannot be changed, so text drawn over a tile's
artwork is invisible. The sizing arithmetic lives apart from Pillow so it can
be tested on a machine with no fonts installed.
"""

from nostalgiabox.player import (
    TileLabel,
    fit_label_size,
    _LABEL_MIN_SIZE,
    _LABEL_TEXT_RATIO,
)

# A monospace-ish stand-in: every glyph half an em wide, like VT323.
def measure(text, size):
    return len(text) * size * 0.5


def test_a_short_name_gets_the_full_size():
    size = fit_label_size(
        measure, bar_h=76, width=598, text="02  Cine", tag=None, pad=11
    )
    assert size == int(76 * _LABEL_TEXT_RATIO)


def test_a_long_name_shrinks_rather_than_overflowing():
    # The longest name in the real lineup, which does not fit at full size.
    long_name = "09  Disney Aventuras"
    size = fit_label_size(
        measure, bar_h=76, width=598, text=long_name, tag="ON NOW", pad=11
    )
    assert size < int(76 * _LABEL_TEXT_RATIO), "it should have shrunk"
    assert 22 + measure(long_name, size) + 20 + measure("ON NOW", size) <= 598


def test_the_on_now_tag_is_counted_in_the_fit():
    """The tag shares the bar, so it has to be part of the sum.

    Measured at a fixed 0.70 of the bar, "Disney Aventuras" came within five
    pixels of the tag - the reason this is fitted rather than fixed.
    """
    text = "10  Cartoon Network"
    without = fit_label_size(measure, bar_h=76, width=598, text=text, tag=None, pad=11)
    with_tag = fit_label_size(
        measure, bar_h=76, width=598, text=text, tag="ON NOW", pad=11
    )
    assert with_tag <= without


def test_it_never_shrinks_past_readable():
    """A name long enough to be silly still has to be read from a sofa."""
    size = fit_label_size(
        measure, bar_h=76, width=598, text="x" * 400, tag="ON NOW", pad=11
    )
    assert size == _LABEL_MIN_SIZE


def test_a_label_defaults_to_focused_and_untagged():
    label = TileLabel(text="02  Cine")
    assert label.tag is None
    assert label.dim is False
