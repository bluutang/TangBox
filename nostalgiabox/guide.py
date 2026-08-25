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


# How much of the picture's height the name bar covers, drawn ON the picture.
#
# There used to be a BAND below the picture instead - 0.3125 of the tile, then
# 0.18, then 0.15 - and every reduction was an attempt to stop the band
# stealing the tile from the artwork it was labelling. Photographed on the
# television 2026-08-25, the answer was that the band should not be there at
# all: neither child can read, so a strip of text permanently occupying a sixth
# of every tile buys nothing they can use, and the ON NOW tag had run out of
# room to sit under the name without colliding with it.
#
# The tile is now the picture, and the name rides on a shaded bar across the
# bottom of it, the way a printed guide captions a thumbnail. The picture gains
# 38% of its area (339x254 -> 399x299 on the canvas, 598x449 on a 1080p
# screen), and the bar can be as dark as it needs to be, because it no longer
# costs the picture anything to be there.
_LABEL_RATIO = 0.17

# How opaque the name bar is. ASS alpha is inverted, so this is how much of the
# picture still shows through underneath: dark enough that the name reads over
# a white cartoon frame, light enough that the bar is part of the picture
# rather than a lid on it.
_LABEL_ALPHA = 70

# The picture is 4:3, the shape the programmes themselves are.
_ART_RATIO = 4 / 3


def art_rect(tile: "TileRect") -> Tuple[float, float, float, float]:
    """``(x, y, w, h)`` of the picture area inside ``tile``.

    The largest 4:3 rectangle that fits the WHOLE tile, centred both ways. It
    used to stop short of a text band along the bottom; the name now sits on
    the picture instead, so nothing is reserved and the artwork gets the lot.

    It still has to be FITTED rather than simply derived from the tile's width:
    a lineup small enough for one page gets very wide tiles, and a 4:3 picture
    as wide as that would burst out of the bottom of the tile.
    """
    w, h = tile.w, tile.h
    if w / h > _ART_RATIO:
        w = h * _ART_RATIO
    else:
        h = w / _ART_RATIO
    return (tile.x + (tile.w - w) / 2, tile.y + (tile.h - h) / 2, w, h)


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
    tile_h = (CANVAS_H - 2 * _MARGIN_Y - strip - _GAP * (rows - 1)) / rows

    # A tile is only as wide as the picture it holds. Stretching it to fill the
    # canvas just puts dead space either side of the artwork - with four
    # channels that was a 552-wide tile around a 280-wide picture, which is what
    # a photograph of the television showed. The picture cannot grow to meet it:
    # it is 4:3 and limited by the tile's HEIGHT, because the name sits in a
    # band underneath.
    #
    # Whatever that frees up becomes margin, so more of the programme playing
    # behind the guide shows through.
    # A tile is exactly as wide as the 4:3 picture its HEIGHT allows, unless
    # there is not room for that many across, in which case width wins.
    widest = (CANVAS_W - 2 * _MARGIN_X - _GAP * (cols - 1)) / cols
    tile_w = min(tile_h * _ART_RATIO, widest)

    # Spread the leftover width EVENLY between the outer margins and the gaps,
    # rather than banking it all at the edges.
    #
    # Banking it at the edges was the previous fix, for the opposite problem:
    # centring each tile in its own slot had put 243 canvas pixels between the
    # two columns and only 185 at the screen edge. That overcorrected -
    # photographed on the television 2026-08-25, two columns sat huddled in the
    # middle of the screen inside wide black borders.
    #
    # Even shares put the same air between the tiles as around them. The outer
    # margin is never allowed below _MARGIN_X, because that one is not taste:
    # televisions overscan, and closer to the edge risks being cut off.
    gaps = cols - 1
    leftover = CANVAS_W - tile_w * cols
    share = leftover / (cols + 1)
    if share >= _MARGIN_X:
        margin = gap = share
    else:
        margin = float(_MARGIN_X)
        gap = max(0.0, (leftover - 2 * margin) / gaps) if gaps else 0.0

    return [
        TileRect(
            index=first + local,
            x=margin + (local % cols) * (tile_w + gap),
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
        """One column right, carrying onto the next PAGE from the last column.

        SPATIAL rather than reading order. Reading order meant right from the
        top-right corner dropped diagonally to the row below: Brian pressed
        right on the top-right tile expecting the next page and landed on the
        tile underneath, which is not what an arrow looks like it should do.

        The ROW is kept as the page turns, the mirror of what :meth:`down`
        already does with the column. On a single page there is nowhere to turn
        to, so the row wraps on itself.
        """
        if not self._count:
            return
        beside = self._cursor + 1
        if self._column < self._cols - 1 and beside < self._count:
            self._cursor = beside
        else:
            self._cursor = self._land_at(
                (self.page + 1) % self._pages, self._row, 0
            )
        self._touch()

    def left(self) -> None:
        """One column left, carrying back onto the previous PAGE.

        The mirror of :meth:`right`: the row is kept, and the cursor arrives in
        the LAST column of it.
        """
        if not self._count:
            return
        if self._column > 0:
            self._cursor -= 1
        else:
            self._cursor = self._land_at(
                (self.page - 1) % self._pages, self._row, self._cols - 1
            )
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

    def _land_at(self, page: int, row: int, column: int) -> int:
        """The tile to land on arriving at ``page`` at (``row``, ``column``).

        Only the LAST page can be part-full, so a page turn that keeps its row
        can aim at a cell that does not exist. Walk UP the column until a real
        tile appears, and settle for the last tile on the page if that column
        is empty from top to bottom - never park on an empty cell.
        """
        start = page * self._per_page
        last = min(start + self._per_page, self._count) - 1
        candidate = start + row * self._cols + column
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
_MARGIN_Y = int(CANVAS_H * 0.045)   # tighter than X: height is what limits the picture
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
_DOT_GROW = 3          # how much bigger the current page's dot is
_DOT_AWAY_ALPHA = 205  # dimmer than the tiles: the dots are small and glow
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
    # Only a tile with NO picture uses this. A tile with one sizes its label
    # off the bar the label sits in, which is what it has to fit inside.
    name_size = max(14, int(tile_h * 0.12))
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
            # The picture is the whole tile, so the label rides ON it: a shaded
            # bar across the bottom, the way a printed guide captions a
            # thumbnail. The number LEADS the name rather than sitting in its
            # own corner plate - one label reads as one thing, and it leaves
            # the top of the picture free for the ON NOW tag, which used to
            # collide with the name in the old band.
            art_x, art_y, art_w, art_h = art_rect(rect)
            label_h = art_h * _LABEL_RATIO
            label_y = art_y + art_h - label_h
            parts.append(
                _filled_rect(
                    x=art_x, y=label_y, w=art_w, h=label_h,
                    fill="&H00000000", alpha=min(255, alpha + _LABEL_ALPHA),
                )
            )
            parts.append(
                rf"{{\an5\pos({round(art_x + art_w / 2)},{round(label_y + label_h / 2)})"
                rf"{_style(ui, size=max(14, int(label_h * 0.60)), alpha=alpha)}}}"
                rf"{number:02d}  {_escape(name)}"
            )
            if on_now is not None and index == on_now:
                parts.append(
                    _on_now_tag(
                        art_x + art_w - _PLATE_INSET, art_y + _PLATE_INSET,
                        tag_size, ui, alpha=alpha,
                    )
                )
        else:
            parts.append(
                rf"{{\an5\pos({round(cx)},{round(y + tile_h * 0.34)})"
                rf"{_style(ui, size=num_size, alpha=alpha)}}}{number:02d}"
            )
            parts.append(
                rf"{{\an5\pos({round(cx)},{round(y + tile_h * 0.66)})"
                rf"{_style(ui, size=name_size, alpha=alpha)}}}{_escape(name)}"
            )
            if on_now is not None and index == on_now:
                # Home then OK always means "never mind", so the guide has to
                # say which one you are already watching.
                parts.append(
                    rf"{{\an5\pos({round(cx)},{round(y + tile_h * 0.90)})"
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
            r=dot_style(index, current)[0],
            fill=color,
            alpha=dot_style(index, current)[1],
        )
        for index in range(pages)
    ]


def dot_style(index: int, current: int) -> Tuple[int, int]:
    """Radius and alpha for one page dot.

    The current page's dot is BIGGER as well as brighter. Brightness alone did
    not read in a render: the glow fills the gap between alpha 0 and alpha 150,
    and the dots are only six pixels across to begin with. A size difference
    survives the glow, the television's 1.5x scaling, and the sofa.
    """
    if index == current:
        return _DOT_R + _DOT_GROW, 0
    return _DOT_R, _DOT_AWAY_ALPHA


def _on_now_tag(
    right: float, y: float, size: int, ui: UiConfig, *, alpha: int,
) -> str:
    """ON NOW on a solid dark block in the picture's top-right corner.

    ``right`` is the plate's RIGHT edge, so the tag hangs off the corner of the
    picture without the caller having to work out how wide it came out.

    It used to sit under the channel name in the text band, where the two
    collided once the band was narrowed to 0.15 - photographed on the
    television 2026-08-25. The name has since moved onto a bar across the
    bottom of the picture, which leaves this corner empty and makes the
    collision impossible rather than merely unlikely.

    The dark block is the trick the channel number used to need: green text on
    a bright cartoon frame is unreadable, and the phosphor glow alone does not
    save it. Printed television guides solve it the same way.
    """
    text = "ON NOW"
    plate_w = round(size * len(text) * 0.62)
    plate_h = round(size * 1.5)
    plate = _filled_rect(
        x=right - plate_w, y=y, w=plate_w, h=plate_h, fill="&H00000000",
        alpha=min(255, alpha + 30),
    )
    label = (
        rf"{{\an5\pos({round(right - plate_w / 2)},{round(y + plate_h / 2)})"
        rf"{_style(ui, size=size, alpha=alpha)}}}{text}"
    )
    return plate + "\n" + label


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
