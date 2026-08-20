"""The channel guide: grid layout, cursor movement, and drawing."""

import re

from nostalgiabox.config import UiConfig
from nostalgiabox.overlay import CANVAS_H, CANVAS_W

from nostalgiabox.guide import Guide, grid_shape, guide_ass
from tests.helpers import FakeClock


def test_four_channels_make_a_two_by_two_grid():
    assert grid_shape(4) == (2, 2)


def test_nine_channels_make_a_three_by_three_grid():
    assert grid_shape(9) == (3, 3)


def test_twelve_channels_make_four_columns_and_three_rows():
    # Proves the return order is (cols, rows) and not the other way round.
    assert grid_shape(12) == (4, 3)


def test_a_single_channel_is_one_tile():
    assert grid_shape(1) == (1, 1)


def test_columns_are_capped_at_five_so_text_stays_readable_from_a_sofa():
    # sqrt(30) rounds up to 6, but the cap holds it at 5 and grows rows instead.
    assert grid_shape(30) == (5, 6)


def test_an_empty_lineup_has_no_grid():
    assert grid_shape(0) == (0, 0)


def test_a_part_full_last_row_still_gets_a_row():
    # 7 channels: 3 columns, so rows must round UP to 3 or a channel vanishes.
    assert grid_shape(7) == (3, 3)


# --------------------------------------------------------------------------
# Cursor movement
# --------------------------------------------------------------------------
# A 4-channel guide is a 2x2 grid indexed in reading order:
#     0 1
#     2 3
# A 7-channel guide is 3 columns with a ragged last row:
#     0 1 2
#     3 4 5
#     6


def test_right_moves_to_the_next_channel():
    g = Guide(count=4, cursor=0)
    g.right()
    assert g.cursor == 1


def test_right_at_the_end_of_a_row_continues_onto_the_next_row():
    # Reading order, so you can never land between two rows and stall.
    g = Guide(count=4, cursor=1)
    g.right()
    assert g.cursor == 2


def test_right_off_the_last_channel_wraps_to_the_first():
    g = Guide(count=4, cursor=3)
    g.right()
    assert g.cursor == 0


def test_left_off_the_first_channel_wraps_to_the_last():
    g = Guide(count=4, cursor=0)
    g.left()
    assert g.cursor == 3


def test_down_moves_a_whole_row():
    g = Guide(count=4, cursor=0)
    g.down()
    assert g.cursor == 2


def test_down_from_the_bottom_row_wraps_to_the_top_of_the_same_column():
    g = Guide(count=4, cursor=2)
    g.down()
    assert g.cursor == 0


def test_up_from_the_top_row_wraps_to_the_bottom_of_the_same_column():
    g = Guide(count=4, cursor=1)
    g.up()
    assert g.cursor == 3


def test_down_past_a_ragged_last_row_lands_on_a_real_channel():
    # 7 channels: below index 4 there is nothing, so it wraps to the column top
    # rather than selecting an empty cell.
    g = Guide(count=7, cursor=4)
    g.down()
    assert g.cursor == 1


def test_up_into_a_ragged_last_row_lands_on_the_lowest_real_channel():
    # Column 2 of a 7-channel grid ends at index 5; index 8 does not exist.
    g = Guide(count=7, cursor=2)
    g.up()
    assert g.cursor == 5


def test_every_move_from_every_position_lands_on_a_real_channel():
    # The property that actually matters: a small child holding the d-pad down
    # must never park the cursor on an empty cell or outside the lineup.
    for count in range(1, 24):
        for start in range(count):
            for move in ("left", "right", "up", "down"):
                g = Guide(count=count, cursor=start)
                getattr(g, move)()
                assert 0 <= g.cursor < count, (count, start, move, g.cursor)


def test_a_single_channel_guide_never_moves_anywhere():
    g = Guide(count=1, cursor=0)
    for move in ("left", "right", "up", "down"):
        getattr(g, move)()
        assert g.cursor == 0


# --------------------------------------------------------------------------
# Opening, closing, and the auto-close timeout
# --------------------------------------------------------------------------
def test_a_guide_starts_closed():
    assert not Guide(count=4).is_open


def test_opening_puts_the_cursor_on_the_channel_being_watched():
    # Home then OK must always mean "never mind".
    g = Guide(count=4)
    g.open(cursor=2)
    assert g.is_open and g.cursor == 2


def test_closing_it_leaves_it_closed():
    g = Guide(count=4)
    g.open(cursor=1)
    g.close()
    assert not g.is_open


def test_it_closes_itself_after_the_timeout_with_no_input():
    # A child who wanders off should not leave the television dimmed under a
    # menu all evening.
    clock = FakeClock()
    g = Guide(count=4, timeout=20.0, clock=clock)
    g.open(cursor=0)

    clock.advance(19.9)
    g.tick()
    assert g.is_open

    clock.advance(0.2)
    g.tick()
    assert not g.is_open


def test_moving_the_cursor_restarts_the_timeout():
    # Someone is clearly still there, so the clock starts again.
    clock = FakeClock()
    g = Guide(count=4, timeout=20.0, clock=clock)
    g.open(cursor=0)

    clock.advance(19.0)
    g.right()
    clock.advance(19.0)
    g.tick()
    assert g.is_open


def test_a_timeout_of_zero_means_it_never_closes_itself():
    # Same convention the overlays already use for "leave until cleared".
    clock = FakeClock()
    g = Guide(count=4, timeout=0, clock=clock)
    g.open(cursor=0)

    clock.advance(10_000)
    g.tick()
    assert g.is_open


def test_ticking_a_closed_guide_does_nothing():
    clock = FakeClock()
    g = Guide(count=4, timeout=20.0, clock=clock)
    clock.advance(10_000)
    g.tick()
    assert not g.is_open


# --------------------------------------------------------------------------
# Drawing
# --------------------------------------------------------------------------
FOUR = [(2, "Los Pequenos"), (4, "Caricaturas"), (6, "Cine"), (8, "Ingles")]


def _ui():
    return UiConfig()


def _positions(ass):
    return [(int(x), int(y)) for x, y in re.findall(r"\\pos\((-?\d+),(-?\d+)\)", ass)]


def test_every_channel_appears_in_the_guide():
    ass = guide_ass(FOUR, cursor=0, ui=_ui())
    for number, name in FOUR:
        assert f"{number:02d}" in ass
        assert name in ass


def test_the_guide_dims_the_picture_rather_than_covering_it():
    # The programme keeps playing underneath. A part-transparent scrim, not an
    # opaque one - alpha 00 would black the picture out entirely.
    ass = guide_ass(FOUR, cursor=0, ui=_ui())
    scrims = re.findall(r"\\1a&H([0-9A-F]{2})&", ass)
    assert any(a not in ("00",) for a in scrims), "nothing is transparent"


def test_the_channel_on_air_is_marked_on_now():
    ass = guide_ass(FOUR, cursor=3, ui=_ui(), on_now=1)
    assert ass.count("ON NOW") == 1


def test_nothing_is_marked_on_now_when_no_channel_is_playing():
    ass = guide_ass(FOUR, cursor=0, ui=_ui(), on_now=None)
    assert "ON NOW" not in ass


def test_moving_the_cursor_changes_what_is_drawn():
    # If focus were not drawn at all these two would be identical.
    a = guide_ass(FOUR, cursor=0, ui=_ui())
    b = guide_ass(FOUR, cursor=1, ui=_ui())
    assert a != b


def test_unfocused_tiles_are_dimmed_so_the_focused_one_stands_out():
    # Three things mark focus, but THIS is the one that works for a 2-year-old:
    # a single bright thing among dim ones needs no explanation.
    ass = guide_ass(FOUR, cursor=0, ui=_ui())
    fully_bright = len(re.findall(r"\\1a&H00&", ass))
    dimmed = len(re.findall(r"\\1a&H(?!00)[0-9A-F]{2}&", ass))
    assert dimmed > fully_bright


def test_everything_is_drawn_inside_the_canvas():
    # Anything outside is simply invisible on the television, and a tile that
    # silently vanishes is the worst kind of bug to spot from a sofa.
    for count in range(1, 24):
        channels = [(n * 2, f"Channel {n}") for n in range(1, count + 1)]
        ass = guide_ass(channels, cursor=0, ui=_ui())
        for x, y in _positions(ass):
            assert 0 <= x <= CANVAS_W, (count, x)
            assert 0 <= y <= CANVAS_H, (count, y)


def test_the_guide_spans_the_full_width_not_just_the_four_three_picture():
    # Unlike the channel banner, which is laid out inside the 4:3 picture area.
    # The banner sits over the picture; the guide replaces it.
    ass = guide_ass(FOUR, cursor=0, ui=_ui())
    assert any(x < 160 for x, _ in _positions(ass))


def test_a_channel_name_containing_braces_cannot_break_the_drawing():
    # Braces delimit ASS override blocks. An unescaped one would corrupt every
    # tag after it.
    ass = guide_ass([(2, "Odd {name}")], cursor=0, ui=_ui())
    assert "{name}" not in ass


def test_accented_channel_names_are_drawn_as_written():
    ass = guide_ass([(2, "Los Pequeños")], cursor=0, ui=_ui())
    assert "Los Pequeños" in ass


def test_an_empty_lineup_draws_nothing_rather_than_crashing():
    assert guide_ass([], cursor=0, ui=_ui()) == ""
