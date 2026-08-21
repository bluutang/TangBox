"""The channel guide - a grid of channels drawn over the dimmed picture.

Press Home and every channel appears as a tile. Move with the d-pad, press OK
to tune, press Back to leave without changing anything. It exists because the
box has no other way to answer "what is on channel 6?" - and once movie
channels are split by franchise the lineup grows past the point where anyone
remembers the numbers.

The guide is a LAYER, not a mode: it intercepts input while open and is
completely inert while closed. Nothing else in the application changes
behaviour because of it.

Drawing is a pure function of (channels, cursor), which is what lets the whole
of this be tested on a computer with no television attached.
"""

from __future__ import annotations

import math
import time
from typing import Callable, List, NamedTuple, Optional, Sequence, Tuple

# The guide reuses the overlay module's styling helpers rather than growing a
# second copy, so it comes out in the same phosphor green, the same VT323 and
# the same glow as the channel banner - and follows it automatically whenever
# those are retuned on the television. It should read as part of the
# television, not as an app that landed on one.
from .config import UiConfig
from .overlay import (
    CANVAS_H,
    CANVAS_W,
    _dot,
    _escape,
    _filled_rect,
    _hex_to_ass,
    _style,
)

# Text has to be readable from a sofa, not a desk, so the grid never grows
# wider than five columns however many channels there are - it grows down
# instead. Past about twenty channels a grid stops being readable at all,
# which is what pages are for.
MAX_COLS = 5

# A page holds four channels across and two down. Both are dials rather than
# constants because the only place the answer is visible is a television across
# a room: on the 1280x720 canvas this makes each tile 264x288, with the show
# name at 43px - 396x432 as it lands on a 1080p television. Five across and
# three down fits half as much again on a page at 206x184; four by two was
# chosen because neither child can read yet, so the tile is doing the work a
# label cannot.
#
# The tile is 17px shorter than the margins alone would suggest, because the
# page dots take a strip out of the bottom of the tile area.
DEFAULT_PAGE_COLS = 4
DEFAULT_PAGE_ROWS = 2

# Seconds of no input before the guide closes itself. A child who wanders off
# should not leave the television dimmed under a menu all evening. This number
# was chosen on paper and has never been watched, so it is a config value.
DEFAULT_TIMEOUT = 20.0


def grid_shape(count: int) -> Tuple[int, int]:
    """How many (columns, rows) for ``count`` channels.

    Roughly square, so four channels give 2x2 and nine give 3x3, capped at
    :data:`MAX_COLS` columns. Rows always round UP, or the last part-full row
    would be dropped and a channel would vanish from the guide.
    """
    if count <= 0:
        return (0, 0)
    cols = min(MAX_COLS, math.ceil(math.sqrt(count)))
    rows = math.ceil(count / cols)
    return (cols, rows)


def page_shape(
    count: int,
    page_cols: int = DEFAULT_PAGE_COLS,
    page_rows: int = DEFAULT_PAGE_ROWS,
) -> Tuple[int, int]:
    """How many (columns, rows) one page of ``count`` channels is laid out in.

    A lineup that fits on a single page keeps the roughly-square layout of
    :func:`grid_shape` - four channels stay a 2x2 of large tiles rather than
    being squeezed into the corner of a fixed grid. Paging, and the fixed page
    grid that comes with it, only switches on once the lineup outgrows a page.
    """
    if count <= 0:
        return (0, 0)
    if count <= page_cols * page_rows:
        return grid_shape(count)
    return (page_cols, page_rows)


def page_count(
    count: int,
    page_cols: int = DEFAULT_PAGE_COLS,
    page_rows: int = DEFAULT_PAGE_ROWS,
) -> int:
    """How many pages ``count`` channels need.

    Rounds UP, for the same reason :func:`grid_shape` rounds its rows up: a
    part-full last page still has to be reachable or its channels vanish from
    the guide.
    """
    if count <= 0:
        return 0
    cols, rows = page_shape(count, page_cols, page_rows)
    return math.ceil(count / (cols * rows))


class TileRect(NamedTuple):
    """Where one tile sits on the canvas, and which channel it is.

    ``index`` is into the WHOLE lineup, not into the page, so a caller can look
    up the channel without repeating the paging arithmetic.
    """

    index: int
    x: float
    y: float
    w: float
    h: float


# How much of a tile's height is the band under the picture. 0.3125 of a 288px
# tile is 90px, which holds the show name at 43px and ON NOW at 31px with a
# little air. Proportional rather than fixed so it survives a change of page
# size - the text scales with the tile too.
_BAND_RATIO = 0.3125

# The picture is 4:3, the shape the programmes themselves are.
_ART_RATIO = 4 / 3


def art_rect(tile: "TileRect") -> Tuple[float, float, float, float]:
    """``(x, y, w, h)`` of the picture area inside ``tile``.

    The largest 4:3 rectangle that fits above the text band, centred across the
    tile. On the real box - a 264x288 tile - that is exactly 264x198 with a
    90px band, which is what the artwork is cut to.

    It has to be fitted rather than simply derived from the tile's width: a
    lineup small enough for one page gets very wide tiles (552x305 for four
    channels), and a 4:3 picture as wide as that would be 414 tall and burst
    out of the bottom of the tile.
    """
    h = tile.h * (1 - _BAND_RATIO)
    w = h * _ART_RATIO
    if w > tile.w:
        w = tile.w
        h = w / _ART_RATIO
    return (tile.x + (tile.w - w) / 2, tile.y, w, h)


def page_tiles(
    count: int,
    cursor: int,
    page_cols: int = DEFAULT_PAGE_COLS,
    page_rows: int = DEFAULT_PAGE_ROWS,
) -> List[TileRect]:
    """Where every tile on the cursor's page sits.

    The single source of truth for tile geometry. The text layer draws from
    this and the picture layer is positioned from it, so a picture cannot end
    up a few pixels away from the name that belongs to it - and a change to a
    margin moves both together or neither.
    """
    if count <= 0:
        return []
    cols, rows = page_shape(count, page_cols, page_rows)
    pages = page_count(count, page_cols, page_rows)
    per_page = cols * rows
    page = max(0, min(pages - 1, cursor // per_page))
    first = page * per_page
    strip = _DOT_STRIP if pages > 1 else 0
    tile_w = (CANVAS_W - 2 * _MARGIN_X - _GAP * (cols - 1)) / cols
    tile_h = (CANVAS_H - 2 * _MARGIN_Y - strip - _GAP * (rows - 1)) / rows
    return [
        TileRect(
            index=first + local,
            x=_MARGIN_X + (local % cols) * (tile_w + _GAP),
            y=_MARGIN_Y + (local // cols) * (tile_h + _GAP),
            w=tile_w,
            h=tile_h,
        )
        for local in range(min(per_page, count - first))
    ]


class Guide:
    """Which tile the cursor is on, and how the d-pad moves it.

    Pure state - no player, no clock, no drawing - so every movement rule can
    be tested on a computer with no television attached.

    The one property that matters more than any individual rule: **every move
    from every position lands on a real channel.** The users are 2 and 4. A
    cursor that parks on an empty cell in a ragged last row, or stops dead at
    an edge, reads as a broken television to someone who cannot read the screen
    to work out why.
    """

    def __init__(
        self,
        *,
        count: int,
        cursor: int = 0,
        timeout: float = DEFAULT_TIMEOUT,
        clock: Callable[[], float] = time.monotonic,
        page_cols: int = DEFAULT_PAGE_COLS,
        page_rows: int = DEFAULT_PAGE_ROWS,
    ) -> None:
        self._count = max(0, int(count))
        self._cols, self._rows = page_shape(self._count, page_cols, page_rows)
        self._per_page = self._cols * self._rows
        self._pages = page_count(self._count, page_cols, page_rows)
        self._cursor = self._clamp(cursor)
        self._timeout = float(timeout)
        self._clock = clock
        self._open = False
        self._deadline: Optional[float] = None

    @property
    def cursor(self) -> int:
        return self._cursor

    @property
    def is_open(self) -> bool:
        return self._open

    # -- opening and closing ------------------------------------------------
    def open(self, *, cursor: int = 0) -> None:
        """Show the guide with the cursor on ``cursor`` (the channel playing)."""
        self._open = True
        self._cursor = self._clamp(cursor)
        self._touch()

    def close(self) -> None:
        self._open = False
        self._deadline = None

    def tick(self) -> None:
        """Close the guide if it has been sitting untouched. Call every loop."""
        if not self._open or self._deadline is None:
            return
        if self._clock() >= self._deadline:
            self.close()

    @property
    def count(self) -> int:
        return self._count

    @property
    def shape(self) -> Tuple[int, int]:
        """(columns, rows) of the grid ONE PAGE of this guide draws."""
        return (self._cols, self._rows)

    @property
    def page(self) -> int:
        """Which page the cursor is on, counting from zero."""
        if self._per_page <= 0:
            return 0
        return self._cursor // self._per_page

    @property
    def page_count(self) -> int:
        """How many pages the lineup fills. One means no paging at all."""
        return self._pages

    # -- movement -----------------------------------------------------------
    def right(self) -> None:
        """Next channel in reading order, wrapping past the last to the first."""
        if self._count:
            self._cursor = (self._cursor + 1) % self._count
            self._touch()

    def left(self) -> None:
        """Previous channel in reading order, wrapping past the first."""
        if self._count:
            self._cursor = (self._cursor - 1) % self._count
            self._touch()

    def down(self) -> None:
        """One row down, carrying onto the next PAGE from the bottom row.

        The column is kept as the page turns, so the cursor does not appear to
        jump sideways. Past the last page it wraps round to the first.
        """
        if not self._count:
            return
        below = self._cursor + self._cols
        if below < self._count and below // self._per_page == self.page:
            self._cursor = below
        else:
            self._cursor = self._land(
                (self.page + 1) % self._pages, self._column, from_bottom=False
            )
        self._touch()

    def up(self) -> None:
        """One row up, carrying onto the previous PAGE from the top row.

        Lands on the LOWEST real tile in the same column, because the last
        page is usually part-full and the cell directly above may not exist.
        """
        if not self._count:
            return
        if self._row > 0:
            self._cursor -= self._cols
        else:
            self._cursor = self._land(
                (self.page - 1) % self._pages, self._column, from_bottom=True
            )
        self._touch()

    # -- internals ----------------------------------------------------------
    @property
    def _column(self) -> int:
        """Which column of its page the cursor is in."""
        return (self._cursor % self._per_page) % self._cols

    @property
    def _row(self) -> int:
        """Which row of its page the cursor is in."""
        return (self._cursor % self._per_page) // self._cols

    def _land(self, page: int, column: int, *, from_bottom: bool) -> int:
        """The tile to land on arriving at ``page`` in ``column``.

        Only the LAST page can be part-full, and arriving on it in a column
        that has no tile is the case that would otherwise park the cursor on
        an empty cell. Coming from above, take the first tile at or before the
        one asked for; coming from below, walk up the column until a tile
        exists, and settle for the last tile on the page if the column is
        empty from top to bottom.
        """
        start = page * self._per_page
        last = min(start + self._per_page, self._count) - 1
        if not from_bottom:
            return min(start + column, last)
        candidate = start + (self._rows - 1) * self._cols + column
        while candidate > last:
            candidate -= self._cols
        return candidate if candidate >= start else last

    def _touch(self) -> None:
        """Restart the auto-close countdown. Any input means someone is there."""
        # A timeout of zero means "leave it until it is closed deliberately",
        # the same convention the overlays use for their durations.
        self._deadline = self._clock() + self._timeout if self._timeout > 0 else None

    def _clamp(self, index: int) -> int:
        if self._count <= 0:
            return 0
        return max(0, min(self._count - 1, int(index)))


# --------------------------------------------------------------------------
# Drawing
# --------------------------------------------------------------------------
# The guide spans the WHOLE 16:9 canvas, unlike the channel banner and volume
# bar which are laid out inside the 4:3 picture area. That is deliberate: the
# banner sits over the picture, the guide replaces it.
_MARGIN_X = int(CANVAS_W * 0.06)      # televisions overscan; keep clear of the edge
_MARGIN_Y = int(CANVAS_H * 0.06)
_GAP = 24                              # space between tiles, in canvas pixels

# How much the picture behind the guide is dimmed, 0 (not at all) to 1 (black).
# Whether 66% is right can only be judged on a television, so config.guide.dim
# overrides it.
DEFAULT_DIM = 0.66

# Unfocused tiles fade back so the focused one is the only bright thing on
# screen. This is the part that does the work for a child who cannot read.
DIM_ALPHA = 150

# The page dots: one per page along the bottom, the current one bright. Neither
# child can read "page 2 of 3", but one lit dot among dim ones is a picture.
# The strip is reserved out of the tile area, so a name and a dot can never be
# drawn on top of each other. Nothing is reserved on a single-page lineup.
_DOT_R = 6
_DOT_SPACING = 26
_DOT_STRIP = 34

# How far the number's plate sits in from the corner of the picture.
_PLATE_INSET = 8

_TRANSPARENT = "&HFF&"


def guide_ass(
    channels: Sequence[Tuple[int, str]],
    cursor: int,
    ui: UiConfig,
    *,
    on_now: Optional[int] = None,
    dim: float = DEFAULT_DIM,
    page_cols: int = DEFAULT_PAGE_COLS,
    page_rows: int = DEFAULT_PAGE_ROWS,
    artwork: Optional[Sequence[bool]] = None,
) -> str:
    """Draw ONE PAGE of the guide - scrim, tiles, cursor, labels and dots.

    A pure function of (channels, cursor, on_now), which is what lets all of
    this be tested with no player and no television.

    ``channels`` is a sequence of ``(number, name)`` pairs in lineup order.
    ``cursor`` and ``on_now`` are INDEXES into it: the cursor is where the
    d-pad has got to, ``on_now`` is what is actually playing. They start out
    the same and diverge as soon as anyone moves.

    Which page is drawn follows from the cursor, so the cursor is never off the
    page being looked at. A lineup that fits on one page draws exactly as it
    always has, with no dots and no reserved strip.

    ``artwork`` is one flag per channel, True where a picture will be drawn
    behind that tile. This function draws NO pictures - it is told where one
    will be and moves the text out of its way: the name drops into the band
    under the picture, and the channel number shrinks onto a dark plate in the
    corner so it stays readable over whatever the artwork contains. A tile
    whose flag is False draws exactly as it always has, which is what lets
    pictures be added one show at a time.

    The whole page is one ASS string so it occupies a single overlay slot -
    one draw call, one clear.
    """
    count = len(channels)
    if count == 0:
        return ""

    cols, rows = page_shape(count, page_cols, page_rows)
    pages = page_count(count, page_cols, page_rows)
    per_page = cols * rows
    page = max(0, min(pages - 1, cursor // per_page))

    # Tile positions come from page_tiles, which the PICTURE layer also uses -
    # so a picture cannot end up a few pixels away from the name below it.
    rects = page_tiles(count, cursor, page_cols, page_rows)
    tile_w, tile_h = rects[0].w, rects[0].h

    # Text scales with the tile, so four big tiles and twenty small ones both
    # fill their space. The floors stop a crowded lineup shrinking to nothing.
    num_size = max(24, int(tile_h * 0.30))
    name_size = max(14, int(tile_h * 0.15))
    tag_size = max(12, int(tile_h * 0.11))

    green = _hex_to_ass(ui.color)
    parts = [
        # The scrim: dim the picture rather than hide it. The programme keeps
        # playing underneath, which is what makes the guide feel like part of
        # the television.
        # ASS alpha is inverted, so it is "how much of the picture still
        # shows through": dim 0.66 becomes alpha 87.
        _filled_rect(x=0, y=0, w=CANVAS_W, h=CANVAS_H, fill="&H00000000",
                     alpha=round(255 * (1.0 - max(0.0, min(1.0, dim)))))
    ]

    for rect in rects:
        number, name = channels[rect.index]
        index = rect.index
        x, y = rect.x, rect.y
        cx = x + tile_w / 2
        focused = index == cursor
        alpha = 0 if focused else DIM_ALPHA

        parts.append(_tile_frame(x, y, tile_w, tile_h, green, ui, focused=focused))

        has_art = bool(artwork) and index < len(artwork) and artwork[index]
        if has_art:
            # The picture takes the middle of the tile, so the number moves to
            # a plate in its corner and everything else drops below it.
            art_x, art_y, art_w, art_h = art_rect(rect)
            band_y, band_h = art_y + art_h, tile_h - art_h
            parts.append(
                _number_plate(
                    art_x + _PLATE_INSET, art_y + _PLATE_INSET,
                    max(18, int(art_h * 0.16)), number, green, ui, alpha=alpha,
                )
            )
            name_y = band_y + band_h * 0.40
            on_now_y = band_y + band_h * 0.80
        else:
            parts.append(
                rf"{{\an5\pos({round(cx)},{round(y + tile_h * 0.34)})"
                rf"{_style(ui, size=num_size, alpha=alpha)}}}{number:02d}"
            )
            name_y = y + tile_h * 0.66
            on_now_y = y + tile_h * 0.90

        parts.append(
            rf"{{\an5\pos({round(cx)},{round(name_y)})"
            rf"{_style(ui, size=name_size, alpha=alpha)}}}{_escape(name)}"
        )
        if on_now is not None and index == on_now:
            # Home then OK always means "never mind", so the guide has to say
            # which one you are already watching.
            parts.append(
                rf"{{\an5\pos({round(cx)},{round(on_now_y)})"
                rf"{_style(ui, size=tag_size, alpha=alpha)}}}ON NOW"
            )

    parts.extend(_page_dots(pages, page, green))
    return "\n".join(parts)


def _page_dots(pages: int, current: int, color: str) -> List[str]:
    """One dot per page along the bottom, the current page's dot bright.

    Nothing at all on a single-page lineup: there is nowhere else to go, so a
    lone dot would be clutter that says nothing.
    """
    if pages <= 1:
        return []
    cy = CANVAS_H - _MARGIN_Y - _DOT_STRIP / 2
    span = _DOT_SPACING * (pages - 1)
    x0 = CANVAS_W / 2 - span / 2
    return [
        _dot(
            cx=x0 + index * _DOT_SPACING,
            cy=cy,
            r=_DOT_R,
            fill=color,
            alpha=0 if index == current else DIM_ALPHA,
        )
        for index in range(pages)
    ]


def _number_plate(
    x: float, y: float, size: int, number: int, color: str, ui: UiConfig,
    *, alpha: int,
) -> str:
    """The channel number on a solid dark block, over the picture.

    A green numeral on a bright cartoon frame is unreadable, and the OSD's
    usual defence - a dark outline and a phosphor glow - only ever helps. The
    plate guarantees it: whatever the artwork contains, the number is on black.

    Printed television guides solve it the same way, which is a reasonable
    thing for a box pretending to be a television to copy.
    """
    plate_w = round(size * 2.1)
    plate_h = round(size * 1.35)
    plate = _filled_rect(
        x=x, y=y, w=plate_w, h=plate_h, fill="&H00000000",
        alpha=min(255, alpha + 30),
    )
    numeral = (
        rf"{{\an5\pos({round(x + plate_w / 2)},{round(y + plate_h / 2)})"
        rf"{_style(ui, size=size, alpha=alpha)}}}{number:02d}"
    )
    return plate + "\n" + numeral


def _tile_frame(
    x: float, y: float, w: float, h: float, color: str, ui: UiConfig,
    *, focused: bool,
) -> str:
    """A rectangular outline - thick and glowing when focused, thin when not.

    Drawn as an ASS shape with a transparent FILL and a visible border, so one
    drawing command gives a frame rather than a filled block.
    """
    x, y = round(x), round(y)
    w, h = round(w), round(h)
    border = 5 if focused else 2
    alpha = 0 if focused else DIM_ALPHA
    tags = (
        rf"\an7\pos({x},{y})\p1\1a{_TRANSPARENT}"
        rf"\bord{border}\3c{color}\3a&H{alpha:02X}&\shad0"
    )
    # The focused tile also glows, matching the OSD's phosphor bloom.
    if focused and ui.glow and ui.glow_blur > 0:
        tags += rf"\blur{ui.glow_blur:g}"
    path = f"m 0 0 l {w} 0 l {w} {h} l 0 {h}"
    return rf"{{{tags}}}{path}{{\p0}}"


__all__ = [
    "Guide",
    "TileRect",
    "guide_ass",
    "grid_shape",
    "page_tiles",
    "art_rect",
    "page_shape",
    "page_count",
    "DEFAULT_PAGE_COLS",
    "DEFAULT_PAGE_ROWS",
    "MAX_COLS",
    "DEFAULT_TIMEOUT",
    "DEFAULT_DIM",
    "DIM_ALPHA",
]
