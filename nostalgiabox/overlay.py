"""On-screen display: the green digital channel banner, volume bar, and messages.

These are drawn to look like a late-90s/early-2000s TV's on-screen display: a
chunky phosphor-green readout in a retro terminal font, with a soft CRT glow.
Two signature elements:

* the **channel banner** ("CH 03" + the show name) that flashes top-right when
  you change channels, and
* the **volume bar** - a row of solid green bars for the current level followed
  by green dots for the rest, with a "Volume" label - matching a classic TV OSD.

Everything is rendered as ASS overlays on a fixed 1280x720 virtual canvas (mpv
scales it to the TV) and cleared automatically after a few seconds by
:meth:`OverlayManager.tick`, which the main loop calls every iteration.
"""

from __future__ import annotations

import time
from typing import Callable, Dict, Optional

from .config import Config, UiConfig
from .player import Player

# Virtual canvas the overlays are laid out on. This maps to the WHOLE display
# (a 16:9 TV), so mpv scales it to whatever the screen is.
CANVAS_W = 1280
CANVAS_H = 720

# The video is forced into a 4:3 frame centred on the 16:9 canvas (see
# MpvPlayer.force_4_3). We lay the OSD out *inside* that 4:3 frame - with a small
# safe-area inset so nothing sits under the CRT's rounded corners - so the green
# readouts always sit over the picture, never out in the black pillarbox bars.
_FRAME_W = int(round(CANVAS_H * 4 / 3))        # 960
_FRAME_X0 = (CANVAS_W - _FRAME_W) // 2          # 160
_FRAME_X1 = _FRAME_X0 + _FRAME_W                # 1120
_FRAME_CX = (_FRAME_X0 + _FRAME_X1) // 2        # 640
_SAFE = 0.06
_IX0 = _FRAME_X0 + int(_FRAME_W * _SAFE)        # ~217  (left safe edge)
_IX1 = _FRAME_X1 - int(_FRAME_W * _SAFE)        # ~1062 (right safe edge)
_IY0 = int(CANVAS_H * _SAFE)                     # ~43   (top safe edge)
_IY1 = CANVAS_H - int(CANVAS_H * _SAFE)          # ~677  (bottom safe edge)

# Overlay slots (ids). Each kind of overlay owns one id so it can be replaced
# or cleared independently.
_ID_CHANNEL = 1
_ID_VOLUME = 2
_ID_STANDBY = 3
_ID_MESSAGE = 4
_ID_GUIDE = 5

_BLACK = "&H00000000"


class OverlayManager:
    """Draws and expires the TV's on-screen overlays."""

    def __init__(
        self,
        player: Player,
        config: Config,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._player = player
        self._config = config
        self._ui = config.ui
        self._clock = clock
        # overlay id -> wall time (monotonic) at which it should disappear.
        self._expiry: Dict[int, float] = {}

    # -- public API ---------------------------------------------------------
    def show_channel_bug(
        self,
        number: int,
        name: str,
        *,
        show: Optional[str] = None,
        episode: Optional[str] = None,
        duration: Optional[float] = None,
        position: Optional[float] = None,
        runtime: Optional[float] = None,
    ) -> None:
        """Flash the channel number, name, programme and episode.

        ``position``/``runtime`` add the timeline row. They are supplied by the
        info button only - a channel change passes neither, so tuning looks
        exactly as it always has.

        Note ``duration`` is how long the BANNER stays up; ``runtime`` is how
        long the episode runs. Two different clocks, so two different names.
        """
        dur = self._config.channel_bug_seconds if duration is None else duration
        ass = _channel_bug_ass(
            number,
            name,
            self._ui,
            show=show,
            episode=episode,
            position=position,
            duration=runtime,
        )
        self._player.set_overlay(_ID_CHANNEL, ass, CANVAS_W, CANVAS_H)
        self._arm(_ID_CHANNEL, dur)

    def show_volume(
        self, level: int, muted: bool, *, duration: Optional[float] = None
    ) -> None:
        dur = self._config.osd_duration if duration is None else duration
        ass = _volume_ass(level, muted, self._ui)
        self._player.set_overlay(_ID_VOLUME, ass, CANVAS_W, CANVAS_H)
        self._arm(_ID_VOLUME, dur)

    def show_message(self, text: str, *, duration: Optional[float] = None) -> None:
        dur = self._config.osd_duration if duration is None else duration
        ass = _message_ass(text, self._ui)
        self._player.set_overlay(_ID_MESSAGE, ass, CANVAS_W, CANVAS_H)
        self._arm(_ID_MESSAGE, dur)

    def show_guide(self, ass: str) -> None:
        """Show the channel guide, and leave it up until it is closed.

        Takes an already-built ASS string rather than building one, so the
        guide's drawing code can import this module's styling helpers without
        this module having to import the guide back.

        Deliberately never expires. The :class:`~nostalgiabox.guide.Guide`
        owns the auto-close timer and closes deliberately; an overlay that
        timed out on its own would leave the guide invisible but still
        swallowing every button press.
        """
        self._player.set_overlay(_ID_GUIDE, ass, CANVAS_W, CANVAS_H)
        self._expiry.pop(_ID_GUIDE, None)

    def clear_guide(self) -> None:
        self._player.clear_overlay(_ID_GUIDE)
        self._expiry.pop(_ID_GUIDE, None)

    def show_standby(self) -> None:
        """Persistent 'standby' notice for when the box is 'off'."""
        ass = _standby_ass(self._ui)
        self._player.set_overlay(_ID_STANDBY, ass, CANVAS_W, CANVAS_H)
        self._expiry.pop(_ID_STANDBY, None)

    def clear_standby(self) -> None:
        self._player.clear_overlay(_ID_STANDBY)
        self._expiry.pop(_ID_STANDBY, None)

    def tick(self) -> None:
        """Clear any overlays whose time is up. Call this every loop iteration."""
        now = self._clock()
        for overlay_id, when in list(self._expiry.items()):
            if now >= when:
                self._player.clear_overlay(overlay_id)
                self._expiry.pop(overlay_id, None)

    def clear_all(self) -> None:
        for overlay_id in (
            _ID_CHANNEL, _ID_VOLUME, _ID_STANDBY, _ID_MESSAGE, _ID_GUIDE,
        ):
            self._player.clear_overlay(overlay_id)
        self._expiry.clear()

    # -- internals ----------------------------------------------------------
    def _arm(self, overlay_id: int, duration: float) -> None:
        if duration <= 0:
            # duration 0 means "leave it until explicitly cleared"
            self._expiry.pop(overlay_id, None)
        else:
            self._expiry[overlay_id] = self._clock() + duration


# --------------------------------------------------------------------------
# Colour + style helpers
# --------------------------------------------------------------------------
def _hex_to_ass(hex_color: str, alpha: int = 0) -> str:
    """Convert ``#RRGGBB`` to an ASS ``&HAABBGGRR`` colour string."""
    h = hex_color.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def _style(ui: UiConfig, *, size: int, alpha: int = 0) -> str:
    """Common ASS override tags: retro font, green fill, and a soft CRT glow."""
    color = _hex_to_ass(ui.color, alpha)
    weight = 1 if ui.bold else 0
    tags = rf"\fn{ui.font}\b{weight}\fs{size}\c{color}\1a&H{alpha:02X}&"
    if ui.letter_spacing:
        tags += rf"\fsp{ui.letter_spacing:g}"
    if ui.glow:
        # A blurred green border reads as phosphor bloom; a faint dark edge keeps
        # it legible over bright video. The blur is a dial (ui.glow_blur) because
        # the right value can only be judged on a television - these tags are
        # drawn on the 1280x720 canvas and stretched, so the blur arrives 1.5x
        # wider on a 1080p screen than it looks anywhere else.
        tags += rf"\bord2\3c{color}\4c{_BLACK}\shad0"
        if ui.glow_blur > 0:
            tags += rf"\blur{ui.glow_blur:g}"
    else:
        tags += rf"\bord2\3c{_BLACK}\shad0"
    return tags


# --------------------------------------------------------------------------
# ASS builders (free functions so they are easy to unit test)
# --------------------------------------------------------------------------
# Geometry of the timeline row, on the 1280x720 overlay canvas. The bar ends
# short of the right safe edge to leave room for the time, which is drawn
# right-aligned to the same edge as the text above it.
_BAR_W = 420
_BAR_H = 6
# Wide enough for the LONGEST reading, "1:29:40" - seven glyphs at size 30 plus
# letter_spacing, which is what a feature film shows on the Cine list at its
# start. Sized for the worst case rather than the common "8:12", because the
# time is right-aligned and grows leftward into the bar. Eyeball it on the TV.
_TIME_GUTTER = 160


def _progress_ass(position: float, duration: float, ui: UiConfig, *, y: int) -> str:
    """The timeline row: unlit track, lit portion, playhead, and time left.

    Returns "" when the length is unknown, so the banner falls back to exactly
    what it has always drawn rather than showing a bar of invented extent.
    """
    if duration <= 0:
        return ""
    x1 = _IX1 - _TIME_GUTTER
    x0 = x1 - _BAR_W
    filled = bar_fill(position, duration, _BAR_W)
    mid = y + _BAR_H / 2
    parts = [
        _filled_rect(x=x0, y=y, w=_BAR_W, h=_BAR_H, fill=_hex_to_ass(ui.dim_color)),
    ]
    if filled:
        parts.append(
            _filled_rect(x=x0, y=y, w=filled, h=_BAR_H, fill=_hex_to_ass(ui.color))
        )
    # A marker, not a handle: the remote has no seek, so it must not look
    # grabbable. Sized to read across a room, and no larger.
    parts.append(_dot(cx=x0 + filled, cy=mid, r=8, fill=_hex_to_ass(ui.color)))
    parts.append(
        rf"{{\an9\pos({_IX1},{y - 14}){_style(ui, size=30)}}}"
        f"{format_remaining(duration - position)}"
    )
    return "\n".join(parts)


def _channel_bug_ass(
    number: int,
    name: str,
    ui: UiConfig,
    *,
    show: Optional[str] = None,
    episode: Optional[str] = None,
    position: Optional[float] = None,
    duration: Optional[float] = None,
) -> str:
    """Green digital 'CH 03', the channel name, and the programme on it.

    Three sizes descending, so the eye reads number -> channel -> programme.
    The show line is omitted entirely when there is nothing to name, rather
    than left blank - a floating gap under the channel name looks like a fault.
    """
    num = f"{number:02d}"
    lines = [
        rf"{{\an9\pos({_IX1},{_IY0}){_style(ui, size=88)}}}CH {num}",
        rf"{{\an9\pos({_IX1},{_IY0 + 104}){_style(ui, size=40)}}}{_escape(name)}",
    ]
    if show:
        lines.append(
            rf"{{\an9\pos({_IX1},{_IY0 + 152}){_style(ui, size=32)}}}{_escape(show)}"
        )
    if episode:
        lines.append(
            rf"{{\an9\pos({_IX1},{_IY0 + 192}){_style(ui, size=28)}}}{_escape(episode)}"
        )
    if position is not None and duration is not None:
        row = _progress_ass(position, duration, ui, y=_IY0 + 248)
        if row:
            lines.append(row)
    return "\n".join(lines)


def _volume_ass(level: int, muted: bool, ui: UiConfig) -> str:
    """A 'Volume' label with solid green bars (level) then green dots (remainder)."""
    level = max(0, min(100, int(level)))
    segments = 20
    filled = 0 if muted else round(level / 100 * segments)

    bar_w = 16
    pitch = 38
    bar_h = 48
    total_w = (segments - 1) * pitch + bar_w
    x0 = _FRAME_CX - total_w // 2          # centre the bar within the 4:3 frame
    row_top = _IY1 - bar_h                  # sit just above the bottom safe edge
    dot_r = 6
    green = _hex_to_ass(ui.color)

    label = "Mute" if muted else "Volume"
    parts = [
        rf"{{\an7\pos({x0},{row_top - 62}){_style(ui, size=48)}}}{label}"
    ]

    for i in range(segments):
        cx = x0 + i * pitch + bar_w / 2
        if i < filled:
            parts.append(
                _filled_rect(x=x0 + i * pitch, y=row_top, w=bar_w, h=bar_h, fill=green)
            )
        else:
            parts.append(_dot(cx=cx, cy=row_top + bar_h / 2, r=dot_r, fill=green))
    return "\n".join(parts)


def _message_ass(text: str, ui: UiConfig) -> str:
    """A centred green digital message (channel entry, 'NO SIGNAL', etc.)."""
    return rf"{{\an8\pos({_FRAME_CX},{_IY0}){_style(ui, size=60)}}}{_escape(text)}"


def _standby_ass(ui: UiConfig) -> str:
    return rf"{{\an5\pos({_FRAME_CX},{CANVAS_H // 2}){_style(ui, size=72)}}}STANDBY"


def bar_fill(position: float, duration: float, width: int) -> int:
    """How many pixels of a ``width``-wide bar are behind the playhead.

    A duration of zero means "length unknown" - the static loop has no
    meaningful end - and fills nothing rather than guessing.
    """
    if duration <= 0:
        return 0
    fraction = min(1.0, max(0.0, position / duration))
    return int(round(fraction * width))


def format_remaining(seconds: float) -> str:
    """Seconds left as ``M:SS``, or ``H:MM:SS`` once there is an hour to show.

    Never negative: the last moments of a file can report a position past its
    own duration, and "-0:01 left" would read as a fault.
    """
    total = max(0, int(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _filled_rect(
    *, x: float, y: float, w: float, h: float, fill: str, alpha: int = 0
) -> str:
    """An ASS drawing (\\p1) filled rectangle at absolute canvas coordinates.

    ``alpha`` is ASS's inverted transparency: 0 is solid, 255 is invisible.
    The channel guide uses a part-transparent black rectangle to dim the
    picture behind it - the programme keeps playing underneath rather than
    being covered over.
    """
    x, y = round(x), round(y)
    w, h = round(w), round(h)
    a = max(0, min(255, int(alpha)))
    draw = f"m 0 0 l {w} 0 l {w} {h} l 0 {h}"
    return rf"{{\an7\pos({x},{y})\p1\c{fill}\1a&H{a:02X}&\bord0\shad0}}{draw}{{\p0}}"


def _dot(*, cx: float, cy: float, r: float, fill: str, alpha: int = 0) -> str:
    """A small filled circle centred at (cx, cy) using 4 bezier arcs.

    ``alpha`` is ASS's inverted transparency, as in :func:`_filled_rect`: 0 is
    solid, 255 invisible. The guide's page dots use it to show the page you are
    on as the only bright one.
    """
    c = 0.5523 * r  # magic constant to approximate a circle with cubic beziers
    x, y = round(cx), round(cy)
    r = round(r, 2)
    c = round(c, 2)
    path = (
        f"m 0 {-r} "
        f"b {c} {-r} {r} {-c} {r} 0 "
        f"b {r} {c} {c} {r} 0 {r} "
        f"b {-c} {r} {-r} {c} {-r} 0 "
        f"b {-r} {-c} {-c} {-r} 0 {-r}"
    )
    a = max(0, min(255, int(alpha)))
    return (
        rf"{{\an5\pos({x},{y})\p1\c{fill}\1a&H{a:02X}&\bord0\shad0}}"
        rf"{path}{{\p0}}"
    )


def _escape(text: str) -> str:
    """Escape characters that are meaningful inside an ASS override block."""
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


__all__ = ["OverlayManager", "CANVAS_W", "CANVAS_H"]
