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
from typing import Callable, Optional, Sequence, Tuple

# The guide reuses the overlay module's styling helpers rather than growing a
# second copy, so it comes out in the same phosphor green, the same VT323 and
# the same glow as the channel banner - and follows it automatically whenever
# those are retuned on the television. It should read as part of the
# television, not as an app that landed on one.
from .config import UiConfig
from .overlay import (
    CANVAS_H,
    CANVAS_W,
    _escape,
    _filled_rect,
    _hex_to_ass,
    _style,
)

# Text has to be readable from a sofa, not a desk, so the grid never grows
# wider than five columns however many channels there are - it grows down
# instead. Past about twenty channels a grid stops being readable at all and
# the answer is a scrolling list, which is a different design.
MAX_COLS = 5

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
    ) -> None:
        self._count = max(0, int(count))
        self._cols, self._rows = grid_shape(self._count)
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
        """(columns, rows) of the grid this guide draws."""
        return (self._cols, self._rows)

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
        """One row down, wrapping to the top of the same column.

        Wraps early when the row below is ragged and has no tile in this
        column, rather than selecting a cell that isn't there.
        """
        if not self._count:
            return
        below = self._cursor + self._cols
        self._cursor = below if below < self._count else self._cursor % self._cols
        self._touch()

    def up(self) -> None:
        """One row up, wrapping to the LOWEST real tile in the same column."""
        if not self._count:
            return
        above = self._cursor - self._cols
        if above >= 0:
            self._cursor = above
            self._touch()
            return
        # Walk up from the bottom of this column until we find a tile that
        # exists - the last row may stop short.
        column = self._cursor % self._cols
        lowest = column + self._cols * (self._rows - 1)
        while lowest >= self._count:
            lowest -= self._cols
        self._cursor = lowest
        self._touch()

    # -- internals ----------------------------------------------------------
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

_TRANSPARENT = "&HFF&"


def guide_ass(
    channels: Sequence[Tuple[int, str]],
    cursor: int,
    ui: UiConfig,
    *,
    on_now: Optional[int] = None,
    dim: float = DEFAULT_DIM,
) -> str:
    """Draw the whole guide - scrim, tiles, cursor and labels - as one string.

    A pure function of (channels, cursor, on_now), which is what lets all of
    this be tested with no player and no television.

    ``channels`` is a sequence of ``(number, name)`` pairs in lineup order.
    ``cursor`` and ``on_now`` are INDEXES into it: the cursor is where the
    d-pad has got to, ``on_now`` is what is actually playing. They start out
    the same and diverge as soon as anyone moves.

    The whole guide is one ASS string so it occupies a single overlay slot -
    one draw call, one clear.
    """
    count = len(channels)
    if count == 0:
        return ""

    cols, rows = grid_shape(count)
    tile_w = (CANVAS_W - 2 * _MARGIN_X - _GAP * (cols - 1)) / cols
    tile_h = (CANVAS_H - 2 * _MARGIN_Y - _GAP * (rows - 1)) / rows

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

    for index, (number, name) in enumerate(channels):
        col, row = index % cols, index // cols
        x = _MARGIN_X + col * (tile_w + _GAP)
        y = _MARGIN_Y + row * (tile_h + _GAP)
        cx = x + tile_w / 2
        focused = index == cursor
        alpha = 0 if focused else DIM_ALPHA

        parts.append(_tile_frame(x, y, tile_w, tile_h, green, ui, focused=focused))
        parts.append(
            rf"{{\an5\pos({round(cx)},{round(y + tile_h * 0.34)})"
            rf"{_style(ui, size=num_size, alpha=alpha)}}}{number:02d}"
        )
        parts.append(
            rf"{{\an5\pos({round(cx)},{round(y + tile_h * 0.66)})"
            rf"{_style(ui, size=name_size, alpha=alpha)}}}{_escape(name)}"
        )
        if on_now is not None and index == on_now:
            # Home then OK always means "never mind", so the guide has to say
            # which one you are already watching.
            parts.append(
                rf"{{\an5\pos({round(cx)},{round(y + tile_h * 0.90)})"
                rf"{_style(ui, size=tag_size, alpha=alpha)}}}ON NOW"
            )

    return "\n".join(parts)


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
    "guide_ass",
    "grid_shape",
    "MAX_COLS",
    "DEFAULT_TIMEOUT",
    "DEFAULT_DIM",
    "DIM_ALPHA",
]
