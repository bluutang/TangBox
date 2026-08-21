"""The channel guide: grid layout, cursor movement, and drawing."""

import re

from nostalgiabox.config import UiConfig
from nostalgiabox.overlay import CANVAS_H, CANVAS_W

from nostalgiabox.guide import (
    Guide,
    art_rect,
    grid_shape,
    guide_ass,
    page_count,
    page_shape,
    page_tiles,
)
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


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------
# A page holds 4 across and 2 down, so eight channels. Paging only switches on
# when the lineup outgrows one page; a short lineup keeps the square-ish layout
# it has always had, so the box on the television tonight is unaffected.
#
# Seventeen channels make three pages, indexed in reading order:
#     page 0:  0  1  2  3      page 1:  8  9 10 11      page 2: 16
#              4  5  6  7              12 13 14 15
#
# The last page is ragged on purpose - that is the case that breaks cursors.


def test_a_lineup_that_fits_on_one_page_keeps_the_layout_it_has_today():
    # The four-channel box on the television must not change under it.
    assert page_shape(4) == grid_shape(4) == (2, 2)


def test_a_lineup_that_fits_on_one_page_is_one_page():
    assert page_count(4) == 1


def test_a_lineup_too_big_for_one_page_uses_the_fixed_page_grid():
    assert page_shape(17) == (4, 2)


def test_seventeen_channels_make_three_pages():
    assert page_count(17) == 3


def test_a_part_full_last_page_still_gets_a_page():
    # Nine channels: eight on the first page, one left over. Rounding down
    # would lose that channel from the guide entirely.
    assert page_count(9) == 2


def test_exactly_one_full_page_does_not_spill_onto_a_second():
    assert page_count(8) == 1


def test_an_empty_lineup_has_no_pages():
    assert page_count(0) == 0
    assert page_shape(0) == (0, 0)


def test_the_page_size_is_a_dial_not_a_constant():
    # Judged from a sofa, so config.pi.yaml can retune it without new code.
    assert page_shape(17, page_cols=5, page_rows=3) == (5, 3)
    assert page_count(17, page_cols=5, page_rows=3) == 2


# -- what the guide knows about pages --------------------------------------


def test_the_guide_reports_which_page_the_cursor_is_on():
    assert Guide(count=17, cursor=9).page == 1


def test_the_guide_reports_how_many_pages_there_are():
    assert Guide(count=17).page_count == 3


def test_a_short_lineup_is_a_single_page():
    assert Guide(count=4).page_count == 1


# -- moving between pages ---------------------------------------------------


def test_down_within_a_page_moves_one_row():
    g = Guide(count=17, cursor=0)
    g.down()
    assert g.cursor == 4


def test_down_from_the_bottom_row_lands_on_the_next_page_in_the_same_column():
    # Column is kept, so the cursor does not jump sideways as the page turns.
    g = Guide(count=17, cursor=4)
    g.down()
    assert g.cursor == 8


def test_down_from_the_last_page_wraps_round_to_the_first():
    g = Guide(count=17, cursor=16)
    g.down()
    assert g.cursor == 0


def test_down_onto_a_ragged_last_page_still_lands_on_a_real_channel():
    # Page 2 holds channel 16 alone, so column 3 does not exist there.
    g = Guide(count=17, cursor=15)
    g.down()
    assert g.cursor == 16


def test_up_from_the_top_row_lands_on_the_previous_page_bottom_row():
    g = Guide(count=17, cursor=8)
    g.up()
    assert g.cursor == 4


def test_up_from_the_first_page_wraps_round_to_the_last():
    g = Guide(count=17, cursor=0)
    g.up()
    assert g.cursor == 16


def test_right_off_the_edge_of_a_page_carries_onto_the_next_page():
    # Reading order across the whole lineup, exactly as it always has been.
    g = Guide(count=17, cursor=7)
    g.right()
    assert g.cursor == 8


def test_left_off_the_start_of_a_page_carries_back_onto_the_previous_one():
    g = Guide(count=17, cursor=8)
    g.left()
    assert g.cursor == 7


def test_every_move_from_every_position_lands_on_a_real_channel():
    # The property that matters more than any individual rule. The users are 2
    # and 4: a cursor that parks on an empty cell in a ragged last page, or
    # stops dead at an edge, reads as a broken television to someone who cannot
    # read the screen to find out why.
    for count in range(1, 31):
        for start in range(count):
            for move in ("up", "down", "left", "right"):
                g = Guide(count=count, cursor=start)
                getattr(g, move)()
                assert 0 <= g.cursor < count, (count, start, move, g.cursor)


# -- drawing a page ---------------------------------------------------------
SEVENTEEN = [(n, f"Channel {n}") for n in range(11, 28)]


def _dots(ass):
    """Every part of the drawing that is a circle - the page dots."""
    return [part for part in ass.split("\n") if " b " in part]


def test_only_the_current_page_is_drawn():
    ass = guide_ass(SEVENTEEN, cursor=0, ui=_ui())
    assert "Channel 11" in ass       # first tile of page 0
    assert "Channel 18" in ass       # last tile of page 0
    assert "Channel 19" not in ass   # first tile of page 1


def test_moving_onto_the_next_page_draws_that_page_instead():
    ass = guide_ass(SEVENTEEN, cursor=8, ui=_ui())
    assert "Channel 19" in ass
    assert "Channel 11" not in ass


def test_one_page_dot_is_drawn_for_each_page():
    assert len(_dots(guide_ass(SEVENTEEN, cursor=0, ui=_ui()))) == 3


def test_exactly_one_page_dot_is_lit():
    # Neither child can read "page 2 of 3". One bright dot among dim ones is a
    # picture, and needs no explanation.
    dots = _dots(guide_ass(SEVENTEEN, cursor=8, ui=_ui()))
    lit = [d for d in dots if r"\1a&H00&" in d]
    assert len(lit) == 1


def test_the_lit_dot_is_the_page_the_cursor_is_on():
    dots = _dots(guide_ass(SEVENTEEN, cursor=8, ui=_ui()))
    assert r"\1a&H00&" in dots[1]


def test_a_single_page_lineup_draws_no_dots():
    # Nothing to page between, so the dots would be clutter.
    assert _dots(guide_ass(FOUR, cursor=0, ui=_ui())) == []


def test_the_page_dots_sit_inside_the_canvas():
    for x, y in _positions(guide_ass(SEVENTEEN, cursor=0, ui=_ui())):
        assert 0 <= x <= CANVAS_W
        assert 0 <= y <= CANVAS_H


def test_tiles_leave_room_for_the_dots_rather_than_drawing_over_them():
    # The dots live in a strip at the bottom that the tiles must not enter,
    # or a channel name and a dot would be drawn on top of each other.
    ass = guide_ass(SEVENTEEN, cursor=0, ui=_ui())
    dot_ys = [y for part in _dots(ass) for _, y in _positions(part)]
    tile_ys = [
        y
        for part in ass.split("\n")
        if " b " not in part
        for _, y in _positions(part)
    ]
    assert min(dot_ys) > max(tile_ys)


# --------------------------------------------------------------------------
# Tile geometry
# --------------------------------------------------------------------------
# The picture layer and the text layer both position themselves from this, so
# a picture cannot end up a few pixels away from the name underneath it.


def test_page_tiles_returns_one_rect_per_visible_tile():
    assert len(page_tiles(17, cursor=0)) == 8


def test_page_tiles_returns_only_the_ragged_last_pages_tiles():
    assert len(page_tiles(17, cursor=16)) == 1


def test_page_tiles_carries_the_lineup_index_not_the_position_on_the_page():
    # Page two's first tile is channel index 8, not 0. The caller uses this to
    # look up the right channel without repeating the paging arithmetic.
    assert page_tiles(17, cursor=8)[0].index == 8


def test_a_tile_is_264_by_288_on_a_four_by_two_page():
    tile = page_tiles(17, cursor=0)[0]
    assert (round(tile.w), round(tile.h)) == (264, 288)


def test_an_empty_lineup_has_no_tiles():
    assert page_tiles(0, cursor=0) == []


def test_tiles_do_not_overlap():
    rects = page_tiles(17, cursor=0)
    for a in rects:
        for b in rects:
            if a.index >= b.index:
                continue
            apart = (
                a.x + a.w <= b.x or b.x + b.w <= a.x
                or a.y + a.h <= b.y or b.y + b.h <= a.y
            )
            assert apart, (a, b)


def test_every_tile_is_inside_the_canvas():
    for count in (1, 4, 8, 9, 17, 30):
        for rect in page_tiles(count, cursor=0):
            assert rect.x >= 0 and rect.x + rect.w <= CANVAS_W, count
            assert rect.y >= 0 and rect.y + rect.h <= CANVAS_H, count


def test_the_picture_is_four_three_whatever_the_page_shape():
    for count, cols, rows in ((17, 4, 2), (17, 5, 3), (30, 3, 2), (4, 4, 2)):
        tile = page_tiles(count, cursor=0, page_cols=cols, page_rows=rows)[0]
        _, _, w, h = art_rect(tile)
        assert abs(w / h - 4 / 3) < 0.001, (count, cols, rows)


def test_the_picture_is_264_by_198_on_the_real_box():
    tile = page_tiles(17, cursor=0)[0]
    _, _, w, h = art_rect(tile)
    assert (round(w), round(h)) == (264, 198)


def test_the_picture_always_fits_inside_the_tile_that_holds_it():
    # A lineup small enough for one page gets very wide tiles - 552x305 for
    # four channels - and a 4:3 picture as wide as that would be 414 tall.
    for count, cols, rows in ((17, 4, 2), (17, 5, 3), (30, 3, 2), (4, 4, 2), (1, 4, 2)):
        tile = page_tiles(count, cursor=0, page_cols=cols, page_rows=rows)[0]
        x, y, w, h = art_rect(tile)
        assert x >= tile.x and x + w <= tile.x + tile.w + 0.001, (count, cols, rows)
        assert y >= tile.y and y + h <= tile.y + tile.h + 0.001, (count, cols, rows)


def test_the_picture_leaves_a_band_for_the_text_underneath():
    for count, cols, rows in ((17, 4, 2), (17, 5, 3), (4, 4, 2)):
        tile = page_tiles(count, cursor=0, page_cols=cols, page_rows=rows)[0]
        _, y, _, h = art_rect(tile)
        assert tile.y + tile.h - (y + h) > 20, (count, cols, rows)


def test_a_wide_tile_centres_its_picture_rather_than_stretching_it():
    tile = page_tiles(4, cursor=0)[0]          # 552 x 305, very wide
    x, _, w, _ = art_rect(tile)
    assert w < tile.w
    assert abs((x - tile.x) - (tile.x + tile.w - (x + w))) < 0.001
