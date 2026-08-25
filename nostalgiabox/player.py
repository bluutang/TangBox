"""The video player abstraction.

The application talks to an abstract :class:`Player`; two implementations exist:

* :class:`MpvPlayer` - the real thing, backed by libmpv (via the ``python-mpv``
  package). This is what runs on the Raspberry Pi against the TV.
* :class:`MockPlayer` - a no-op player that records what it was asked to do and
  lets tests/dev drive "the episode ended" by hand. This lets the entire app be
  exercised on a laptop with no display, no libmpv, and no media files.

Keeping this boundary thin (load / stop / volume / a couple of OSD hooks) means
the interesting logic in ``app.py`` never has to know which one it is using.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from dataclasses import dataclass

from .artwork import crop_box


@dataclass(frozen=True)
class TileLabel:
    """The caption burned into a guide tile's picture.

    Burned in rather than drawn as ASS over the top, because mpv will not allow
    the other order. From its own manual: "Z order between different overlays
    of different formats is static, and cannot be changed ... bitmap overlays
    added by overlay-add are always on top of the ASS overlays added by
    osd-overlay."

    The picture is a bitmap overlay and the guide's text is ASS, so ANY text
    over a tile's artwork is invisible - which is why the channel number on its
    little dark plate was never once seen, and why Brian asked for a number
    that was already being drawn.

    ``dim`` is the unfocused state: everything fades back so the focused tile
    is the only bright thing on the screen, which is the cue doing the work for
    a child who cannot read.
    """

    text: str
    color: str = "#33FF66"
    font: Optional[Path] = None
    tag: Optional[str] = None
    ratio: float = 0.17
    dim: bool = False

log = logging.getLogger(__name__)

# Reason strings passed to the "playback finished" callback.
END_EOF = "eof"        # the file played to its natural end -> roll next episode
END_ERROR = "error"    # the file failed to play -> skip to next episode
END_STOPPED = "stopped"  # we stopped it on purpose (channel change) -> ignore


class Player(ABC):
    """Minimal video-player interface used by the application."""

    #: Called when playback of the current item finishes. Receives one of the
    #: END_* reason strings. Set by the application before playing anything.
    on_end: Optional[Callable[[str], None]] = None

    @abstractmethod
    def play(self, path: Path, *, start: float = 0.0) -> None:
        """Begin playing ``path`` from ``start`` seconds in."""

    @abstractmethod
    def play_loop(self, path: Path) -> None:
        """Play ``path`` on an endless loop (used for the static/no-signal clip)."""

    def play_transition(
        self,
        static_path: Path,
        target_path: Path,
        *,
        start: float = 0.0,
        static_seconds: float = 0.5,
    ) -> None:
        """Show a brief static burst, then the target episode.

        The default implementation just plays the target; players that can
        preload (see :class:`MpvPlayer`) override this to make the switch
        near-instant.
        """
        self.play(target_path, start=start)

    def set_crt_shader(self, path: Optional[Path]) -> None:
        """Swap the CRT picture effect while playback continues.

        ``None`` means no effect at all. The default does nothing, so a player
        that cannot change shaders simply keeps the look it started with.
        """

    def preload_next(self, target_path: Path, *, start: float = 0.0) -> None:
        """Begin loading ``target_path`` in the background while the CURRENT item
        keeps playing. Call :meth:`commit_switch` to cut over once it's ready.

        The default implementation has no way to preload, so it just plays the
        target immediately; :class:`MpvPlayer` overrides it.
        """
        self.play(target_path, start=start)

    def commit_switch(self) -> None:
        """Switch to the item queued by :meth:`preload_next` (no-op by default)."""

    @abstractmethod
    def stop(self) -> None:
        """Stop playback and show a blank screen."""

    @abstractmethod
    def set_volume(self, volume: int) -> None:
        """Set the volume (0-100)."""

    @abstractmethod
    def set_mute(self, muted: bool) -> None: ...

    @abstractmethod
    def get_time_pos(self) -> Optional[float]:
        """Current playback position in seconds, or None if nothing is playing."""

    def get_duration(self) -> Optional[float]:
        """How long the current item runs, or None when that is unknowable.

        Concrete, not abstract, so a player written before the timeline existed
        can still be instantiated - it simply reports nothing and the banner
        falls back to what it always drew.
        """
        return None

    @abstractmethod
    def show_text(self, text: str, duration: float) -> None:
        """Show a plain OSD message for ``duration`` seconds."""

    @abstractmethod
    def set_overlay(self, overlay_id: int, ass: str, res_x: int, res_y: int) -> None:
        """Draw an ASS overlay with the given id (replacing any previous one)."""

    @abstractmethod
    def clear_overlay(self, overlay_id: int) -> None:
        """Remove a previously drawn overlay."""

    def show_image(
        self,
        slot: int,
        path: Path,
        x: int,
        y: int,
        w: int,
        h: int,
        res_x: int,
        res_y: int,
        label: Optional[TileLabel] = None,
    ) -> None:
        """Draw the picture at ``path`` scaled into ``w`` x ``h`` at ``x, y``.

        ``x``/``y``/``w``/``h`` are on a ``res_x`` x ``res_y`` virtual canvas,
        exactly as :meth:`set_overlay` takes its own resolution. A player that
        draws to a real screen has to scale them itself, because mpv positions
        image overlays in DISPLAY pixels and will otherwise bunch every picture
        toward the top-left.

        A second overlay layer ON TOP OF the ASS one - see :class:`TileLabel`
        for why that order cannot be changed, and why ``label`` therefore has
        to be burned into the picture rather than drawn over it.

        Concrete rather than abstract, and a no-op by default, so a player that
        cannot draw pictures simply does not draw them - the guide already has
        to handle a tile with no picture, because most shows have none.
        """

    def clear_image(self, slot: int) -> None:
        """Remove just the picture in ``slot``, leaving the others alone."""

    def clear_images(self) -> None:
        """Remove every picture drawn by :meth:`show_image`."""

    @abstractmethod
    def close(self) -> None:
        """Release resources."""


def scale_to_display(
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    canvas: Tuple[int, int],
    display: Optional[Tuple[Optional[int], Optional[int]]],
) -> Tuple[int, int, int, int]:
    """Map a rectangle on the ASS canvas onto real display pixels.

    Overlays are authored on a fixed virtual canvas which mpv scales up to the
    television. ASS rides that scaling for free because it is told its own
    resolution; IMAGE overlays do not - mpv positions those in real display
    pixels. Handing canvas coordinates straight to one draws it at
    canvas/display of the intended position and size, bunched toward the
    top-left, which is what a photograph of the television showed.

    An unknown display size returns the rectangle unscaled rather than
    refusing to draw: mpv may not know its output size yet, and a picture in
    the wrong place beats no picture at all.
    """
    unscaled = (round(x), round(y), round(w), round(h))
    if not display:
        return unscaled
    dw, dh = display
    cw, ch = canvas
    if not dw or not dh or not cw or not ch:
        return unscaled
    sx, sy = dw / cw, dh / ch
    return (round(x * sx), round(y * sy), round(w * sx), round(h * sy))


def build_mpv_options(
    *,
    fullscreen: bool = True,
    hwdec: str = "auto-safe",
    audio_device: Optional[str] = None,
    glsl_shaders: Optional[str] = None,
    force_4_3: bool = True,
    display_mode: Optional[str] = None,
    extra_options: Optional[dict] = None,
) -> dict:
    """Assemble the libmpv options. Split out so it can be tested without mpv."""
    options = dict(
        osc=False,
        input_default_bindings=False,
        input_vo_keyboard=False,
        idle="yes",
        force_window="yes",
        keep_open="yes",
        prefetch_playlist="yes",
        fullscreen=fullscreen,
        hwdec=hwdec,
        keepaspect="yes",
        video_unscaled="no",
        cursor_autohide="always",
        osd_font_size=40,
    )
    if audio_device:
        options["audio_device"] = audio_device
    if glsl_shaders:
        options["glsl_shaders"] = glsl_shaders
    if display_mode:
        # mpv does its OWN mode-setting when it takes the screen and defaults to
        # the connector's preferred mode - so a 4K TV gets 4K no matter what the
        # kernel was told on the cmdline. Proven on the Pi: stopping TangBox made
        # the display drop straight back to the pinned 1920x1080@60.
        options["drm_mode"] = display_mode
    if force_4_3:
        options["vf"] = (
            "lavfi=[scale=960:720:force_original_aspect_ratio=decrease,"
            "pad=960:720:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1]"
        )
    if extra_options:
        options.update(extra_options)
    return options


#: How tall the caption text wants to be, as a fraction of its bar. Aims high
#: and is allowed to shrink, rather than being set low enough for the longest
#: name anybody might ever add.
_LABEL_TEXT_RATIO = 0.80

#: Never shrink past this, however long the name. Below it the caption stops
#: being readable from a sofa, which is the only place it is ever read.
_LABEL_MIN_SIZE = 24


def fit_label_size(
    measure: Callable[[str, int], float],
    *,
    bar_h: int,
    width: float,
    text: str,
    tag: Optional[str],
    pad: float,
    gap: float = 20.0,
) -> int:
    """The largest font size at which ``text`` and ``tag`` both fit the bar.

    Fitted rather than fixed. A fixed fraction has to be set low enough for the
    longest channel name in the lineup, which makes every SHORTER name smaller
    than it needed to be - and silently breaks the first time somebody adds a
    longer one. Measured at 0.70 of the bar, "Disney Aventuras" came within
    five pixels of the ON NOW tag.

    ``measure`` reports the width of a string at a size, which is the only part
    that needs a real font - so the arithmetic here is testable on a machine
    with no Pillow installed.
    """
    size = max(_LABEL_MIN_SIZE, int(bar_h * _LABEL_TEXT_RATIO))
    while size > _LABEL_MIN_SIZE:
        needed = pad * 2 + measure(text, size)
        if tag:
            needed += gap + measure(tag, size)
        if needed <= width:
            break
        size -= 1
    return size


def _burn_label(picture, label: "TileLabel") -> None:
    """Draw ``label`` onto the top of ``picture``, in place.

    A shaded bar across the top with the channel number, its name, and ON NOW
    on the right when the channel is the one playing. Burned into the bitmap
    because ASS drawn over a bitmap overlay is invisible in mpv - see
    :class:`TileLabel`.

    Every failure here is survivable: a missing font, an unreadable one, a
    Pillow too old for `textlength`. The tile then shows its artwork with no
    caption, which is what a tile has always done when it had no picture to
    caption. Losing the whole picture over a font would be a far worse trade.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:  # pragma: no cover - Pi-only
        return
    try:
        w, h = picture.size
        bar_h = max(18, int(h * label.ratio))
        # ASS dims unfocused tiles by fading them; here the bar and its text
        # simply come out fainter, for the same reason - the focused tile has
        # to be the only bright thing on the screen.
        shade = 150 if label.dim else 205
        ink = _dim_hex(label.color, 0.45) if label.dim else label.color

        picture.alpha_composite(
            Image.new("RGBA", (w, bar_h), (0, 0, 0, shade)), (0, 0)
        )

        draw = ImageDraw.Draw(picture)
        pad = max(6, int(w * 0.02))

        def _measure(text: str, size: int) -> float:
            return ImageFont.truetype(str(label.font), size).getlength(text)

        if label.font and Path(label.font).is_file():
            size = fit_label_size(
                _measure, bar_h=bar_h, width=w, text=label.text,
                tag=label.tag, pad=pad,
            )
            font = ImageFont.truetype(str(label.font), size)
        else:
            font = ImageFont.load_default()
        draw.text((pad, bar_h / 2), label.text, font=font, fill=ink, anchor="lm")
        if label.tag:
            draw.text(
                (w - pad, bar_h / 2), label.tag, font=font, fill=ink, anchor="rm"
            )
    except Exception:  # pragma: no cover - never lose the picture over a caption
        log.debug("could not burn a tile label", exc_info=True)


def _dim_hex(hex_color: str, factor: float) -> str:
    """``hex_color`` scaled toward black by ``factor``."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "#%02X%02X%02X" % (
        int(r * factor), int(g * factor), int(b * factor)
    )


class MpvPlayer(Player):
    """A :class:`Player` backed by libmpv, tuned for a Raspberry Pi + TV."""

    def __init__(
        self,
        *,
        fullscreen: bool = True,
        hwdec: str = "auto-safe",
        glsl_shaders: Optional[str] = None,
        fonts_dir: Optional[Path] = None,
        force_4_3: bool = True,
        audio_device: Optional[str] = None,
        display_mode: Optional[str] = None,
        extra_options: Optional[dict] = None,
    ) -> None:
        try:
            import mpv  # type: ignore
        except ImportError as exc:  # pragma: no cover - only on machines w/o libmpv
            raise RuntimeError(
                "python-mpv/libmpv is not installed. On the Raspberry Pi run "
                "`scripts/install.sh` or `pip install .[pi]` and ensure libmpv "
                "is present (`sudo apt install libmpv2 mpv`)."
            ) from exc

        # Make our bundled retro font discoverable by libass (used for the OSD
        # overlays) by dropping it into mpv's config "fonts" directory.
        if fonts_dir is not None:
            _install_fonts_for_mpv(fonts_dir)

        options = build_mpv_options(
            fullscreen=fullscreen,
            hwdec=hwdec,
            audio_device=audio_device,
            glsl_shaders=glsl_shaders,
            force_4_3=force_4_3,
            display_mode=display_mode,
            extra_options=extra_options,
        )

        self._mpv = mpv.MPV(**options)
        self._closed = False
        # The guide's tile pictures, keyed by slot. Kept so a redraw can
        # replace one in place and closing can take them all away.
        self._image_overlays: Dict[int, object] = {}
        # True while a looping filler clip (static / colour bars) is showing, so
        # its (non-)ending never advances the channel.
        self._suppress = True

        @self._mpv.property_observer("eof-reached")
        def _on_eof(_name, value):  # pragma: no cover - needs libmpv + media
            if value and not self._suppress and self.on_end is not None:
                try:
                    self.on_end(END_EOF)
                except Exception:  # noqa: BLE001 - never let a callback kill mpv
                    log.exception("error in on_end (eof) callback")

        @self._mpv.event_callback("end-file")
        def _on_end_file(event):  # pragma: no cover - needs libmpv + media
            # We only care about *errors* here (e.g. a corrupt/missing file) so
            # we can skip to the next episode. Natural ends are handled by the
            # eof-reached observer above; intentional stops/replacements are
            # ignored.
            if self._suppress:
                return
            if _extract_end_reason(event) == END_ERROR and self.on_end is not None:
                try:
                    self.on_end(END_ERROR)
                except Exception:  # noqa: BLE001
                    log.exception("error in on_end (error) callback")

    # -- playback -----------------------------------------------------------
    def set_crt_shader(self, path: Optional[Path]) -> None:
        # Attribute assignment sets the PROPERTY (`glsl-shaders`), which takes
        # effect on the video already playing. Item assignment would set
        # `options/glsl-shaders` instead - the load-time option - and the
        # picture on screen would not change. Each rung has its own filename,
        # so mpv cannot serve a cached compile of the previous look either.
        try:
            self._mpv.glsl_shaders = str(path) if path else ""
        except Exception:
            log.warning("could not switch the CRT shader", exc_info=True)

    def play(self, path: Path, *, start: float = 0.0) -> None:
        # Enable end detection only for real content.
        self._suppress = False
        try:
            self._mpv.loop_file = "no"
            if start and start > 0:
                # start is an mpv per-file option; +N seeks N seconds in.
                self._mpv.loadfile(str(path), "replace", start=f"+{start:.3f}")
            else:
                self._mpv.loadfile(str(path), "replace")
            self._mpv.pause = False  # keep-open can leave us paused; force play
        except Exception:  # noqa: BLE001
            log.exception("failed to play %s", path)
            if self.on_end is not None:
                self.on_end(END_ERROR)

    def play_loop(self, path: Path) -> None:
        self._suppress = True  # a looping clip should never trigger "next"
        try:
            self._mpv.loop_file = "inf"
            self._mpv.loadfile(str(path), "replace")
            self._mpv.pause = False
        except Exception:  # noqa: BLE001
            log.exception("failed to loop %s", path)

    def play_transition(
        self,
        static_path: Path,
        target_path: Path,
        *,
        start: float = 0.0,
        static_seconds: float = 0.5,
    ) -> None:
        # Build a 2-entry playlist: [static (cut to static_seconds), episode].
        # mpv plays the static burst and, thanks to prefetch-playlist, has the
        # episode ready to show the instant the static ends. keep-open=yes only
        # holds the LAST entry, so eof-reached (which advances the channel) only
        # ever trips for the episode - never the static.
        self._suppress = False
        try:
            self._mpv.loop_file = "no"
            self._mpv.loadfile(
                str(static_path), "replace", end=f"{max(0.05, static_seconds):.3f}"
            )
            if start and start > 0:
                self._mpv.loadfile(str(target_path), "append", start=f"+{start:.3f}")
            else:
                self._mpv.loadfile(str(target_path), "append")
            self._mpv.pause = False
        except Exception:  # noqa: BLE001
            log.exception("failed transition to %s", target_path)
            self.play(target_path, start=start)

    def preload_next(self, target_path: Path, *, start: float = 0.0) -> None:
        # Keep the currently-playing item on screen and append the target as a
        # second playlist entry. With prefetch-playlist=yes, mpv opens/decodes it
        # in the background while the current show keeps playing, so commit_switch
        # can cut over near-instantly (no frozen frame).
        self._suppress = True  # ignore the outgoing show's own eof during the bridge
        try:
            self._mpv.command("playlist-clear")  # drop any earlier pending append
            if start and start > 0:
                self._mpv.loadfile(str(target_path), "append", start=f"+{start:.3f}")
            else:
                self._mpv.loadfile(str(target_path), "append")
        except Exception:  # noqa: BLE001
            log.exception("failed to preload %s", target_path)
            self.play(target_path, start=start)

    def commit_switch(self) -> None:
        self._suppress = False
        try:
            self._mpv.command("playlist-next", "force")  # jump to the prefetched item
            self._mpv.command("playlist-clear")          # keep only the new current
            self._mpv.pause = False
        except Exception:  # noqa: BLE001
            log.debug("commit_switch failed", exc_info=True)

    def stop(self) -> None:
        self._suppress = True
        try:
            self._mpv.command("stop")
        except Exception:  # noqa: BLE001 - stopping should never crash us
            log.debug("mpv stop failed", exc_info=True)

    # -- audio --------------------------------------------------------------
    def set_volume(self, volume: int) -> None:
        try:
            self._mpv.volume = max(0, min(100, int(volume)))
        except Exception:  # noqa: BLE001
            log.debug("could not set volume", exc_info=True)

    def set_mute(self, muted: bool) -> None:
        try:
            self._mpv.mute = bool(muted)
        except Exception:  # noqa: BLE001
            log.debug("could not set mute", exc_info=True)

    def get_time_pos(self) -> Optional[float]:
        try:
            pos = self._mpv.time_pos
            return float(pos) if pos is not None else None
        except Exception:  # noqa: BLE001
            return None

    def get_duration(self) -> Optional[float]:
        try:
            length = self._mpv.duration
        except Exception:  # noqa: BLE001
            return None
        return float(length) if length else None

    # -- OSD ----------------------------------------------------------------
    def show_text(self, text: str, duration: float) -> None:
        try:
            self._mpv.command("show-text", text, int(duration * 1000))
        except Exception:  # noqa: BLE001
            log.debug("show-text failed", exc_info=True)

    def set_overlay(self, overlay_id: int, ass: str, res_x: int, res_y: int) -> None:
        try:
            # osd-overlay positional args: id, format, data, res_x, res_y.
            # (Trailing z/hidden/compute_bounds use their defaults.)
            self._mpv.command(
                "osd-overlay", overlay_id, "ass-events", ass, res_x, res_y
            )
        except Exception:  # noqa: BLE001
            # Fall back to a plain message so the viewer still gets feedback.
            log.debug("osd-overlay failed, falling back to show-text", exc_info=True)
            self.show_text(_strip_ass(ass), 3.0)

    def _display_size(self) -> Optional[Tuple[Optional[int], Optional[int]]]:
        """mpv's real output size, or None while it does not know one yet."""
        try:
            dim = self._mpv.osd_dimensions
            return (int(dim["w"]), int(dim["h"]))
        except Exception:  # noqa: BLE001 - property missing, empty, or pre-render
            log.debug("osd-dimensions unavailable; drawing tiles unscaled", exc_info=True)
            return None

    def show_image(
        self, slot: int, path: Path, x: int, y: int, w: int, h: int,
        res_x: int, res_y: int, label: Optional[TileLabel] = None,
    ) -> None:
        """Scale ``path`` into the tile and hand the pixels to mpv.

        libass draws text and shapes but not photographs, so this is a second
        overlay layer rather than more ASS. Pillow is imported HERE rather than
        at the top of the module: it is a Pi-only dependency, and every test on
        a laptop imports this file.

        Every failure is survivable and quiet. A box without Pillow, or with a
        half-copied JPEG on the drive, draws the tile's text and no picture -
        which is exactly what a show with no artwork does anyway.
        """
        try:
            from PIL import Image  # Pi-only; see requirements.txt
        except ImportError:
            log.debug("Pillow is not installed, so tile pictures are skipped")
            return
        # Canvas units in, display pixels out. Before the resize, because these
        # are the dimensions the picture is actually rendered at.
        x, y, w, h = scale_to_display(
            x, y, w, h, canvas=(res_x, res_y), display=self._display_size()
        )
        try:
            with Image.open(path) as src:
                picture = src.convert("RGBA")
                picture = picture.crop(
                    crop_box(picture.width, picture.height, w, h)
                ).resize((w, h), Image.LANCZOS)
        except (OSError, ValueError):
            log.warning("could not read tile picture %s", path, exc_info=True)
            return
        if label is not None:
            _burn_label(picture, label)
        overlay = self._image_overlays.get(slot)
        try:
            if overlay is None:
                overlay = self._mpv.create_image_overlay()
                self._image_overlays[slot] = overlay
            overlay.update(picture, pos=(x, y))
        except Exception:  # pragma: no cover - libmpv specific
            log.debug("drawing a tile picture failed", exc_info=True)

    def clear_image(self, slot: int) -> None:
        overlay = self._image_overlays.pop(slot, None)
        if overlay is None:
            return
        try:
            overlay.remove()
        except Exception:  # pragma: no cover - libmpv specific
            log.debug("removing a tile picture failed", exc_info=True)

    def clear_images(self) -> None:
        for overlay in self._image_overlays.values():
            try:
                overlay.remove()
            except Exception:  # pragma: no cover - libmpv specific
                log.debug("removing a tile picture failed", exc_info=True)
        self._image_overlays.clear()

    def clear_overlay(self, overlay_id: int) -> None:
        try:
            self._mpv.command("osd-overlay", overlay_id, "none", "")
        except Exception:  # noqa: BLE001
            log.debug("clearing overlay failed", exc_info=True)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._mpv.terminate()
        except Exception:  # noqa: BLE001
            log.debug("mpv terminate failed", exc_info=True)


class MockPlayer(Player):
    """A headless stand-in that records commands - for tests and dev mode."""

    def __init__(self, *, verbose: bool = False) -> None:
        self.verbose = verbose
        self.current: Optional[Path] = None
        self.looping: Optional[Path] = None
        self.volume: int = 0
        self.muted: bool = False
        self.time_pos: float = 0.0
        self.closed = False
        # Recorded history, handy for assertions in tests.
        self.played: List[Tuple[Path, float]] = []
        self.transitions: List[Tuple[Path, Path, float]] = []
        self.preloaded: Optional[Tuple[Path, float]] = None
        self.messages: List[Tuple[str, float]] = []
        self.overlays: dict[int, str] = {}
        self.images: dict[int, Tuple[Path, int, int, int, int]] = {}
        self.image_labels: dict[int, Optional[TileLabel]] = {}
        self.stops = 0
        self.crt_shader: Optional[Path] = None
        self.duration: float = 0.0

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(f"[player] {msg}")

    def set_crt_shader(self, path: Optional[Path]) -> None:
        self.crt_shader = path

    def play(self, path: Path, *, start: float = 0.0) -> None:
        self.current = path
        self.looping = None
        self.time_pos = start
        self.played.append((path, start))
        self._log(f"PLAY {path} @ {start:.1f}s")

    def play_loop(self, path: Path) -> None:
        self.looping = path
        self.current = path
        self._log(f"LOOP {path}")

    def play_transition(
        self,
        static_path: Path,
        target_path: Path,
        *,
        start: float = 0.0,
        static_seconds: float = 0.5,
    ) -> None:
        self.transitions.append((static_path, target_path, start))
        # The episode is what ends up playing (static is momentary).
        self.current = target_path
        self.looping = None
        self.time_pos = start
        self.played.append((target_path, start))
        self._log(f"TRANSITION static={static_path} -> {target_path} @ {start:.1f}s")

    def preload_next(self, target_path: Path, *, start: float = 0.0) -> None:
        # The current item keeps "playing"; the target is queued, not shown yet.
        self.preloaded = (target_path, start)
        self._log(f"PRELOAD {target_path} @ {start:.1f}s (current keeps playing)")

    def commit_switch(self) -> None:
        if self.preloaded is None:
            return
        target, start = self.preloaded
        self.preloaded = None
        self.current = target
        self.looping = None
        self.time_pos = start
        self.played.append((target, start))
        self._log(f"COMMIT SWITCH -> {target} @ {start:.1f}s")

    def stop(self) -> None:
        self.current = None
        self.looping = None
        self.preloaded = None
        self.stops += 1
        self._log("STOP")

    def set_volume(self, volume: int) -> None:
        self.volume = max(0, min(100, int(volume)))
        self._log(f"VOLUME {self.volume}")

    def set_mute(self, muted: bool) -> None:
        self.muted = bool(muted)
        self._log(f"MUTE {self.muted}")

    def get_time_pos(self) -> Optional[float]:
        return self.time_pos if self.current is not None else None

    def get_duration(self) -> Optional[float]:
        if self.current is None or not self.duration:
            return None
        return self.duration

    def show_text(self, text: str, duration: float) -> None:
        self.messages.append((text, duration))
        self._log(f"TEXT {text!r} ({duration}s)")

    def set_overlay(self, overlay_id: int, ass: str, res_x: int, res_y: int) -> None:
        self.overlays[overlay_id] = ass
        self._log(f"OVERLAY {overlay_id}")

    def clear_overlay(self, overlay_id: int) -> None:
        self.overlays.pop(overlay_id, None)
        self._log(f"CLEAR OVERLAY {overlay_id}")

    def show_image(
        self, slot: int, path: Path, x: int, y: int, w: int, h: int,
        res_x: int = 0, res_y: int = 0, label: Optional[TileLabel] = None,
    ) -> None:
        # No screen, so nothing to scale to: record the canvas units as given.
        self.images[slot] = (path, x, y, w, h)
        # Kept separately so a test can assert what a tile is CAPTIONED with -
        # the caption is burned into the bitmap on the real player, where no
        # test can read it back.
        self.image_labels[slot] = label
        self._log(f"IMAGE {slot} {path.name} {w}x{h}+{x}+{y}")

    def clear_image(self, slot: int) -> None:
        self.images.pop(slot, None)
        self.image_labels.pop(slot, None)

    def clear_images(self) -> None:
        self.images.clear()
        self.image_labels.clear()
        self._log("CLEAR IMAGES")

    def close(self) -> None:
        self.closed = True
        self._log("CLOSE")

    # -- test/dev helper ----------------------------------------------------
    def finish_current(self, reason: str = END_EOF) -> None:
        """Simulate the current episode ending, triggering ``on_end``."""
        self.current = None
        if self.on_end is not None:
            self.on_end(reason)


def _extract_end_reason(event) -> str:  # pragma: no cover - libmpv specific
    """Normalise the many shapes of a python-mpv end-file event into a reason."""
    reason = None
    try:
        data = getattr(event, "data", event)
        if isinstance(data, dict):
            reason = data.get("reason")
        else:
            reason = getattr(data, "reason", None)
    except Exception:  # noqa: BLE001
        reason = None
    reason = str(reason).lower() if reason is not None else ""
    if "eof" in reason:
        return END_EOF
    if "error" in reason:
        return END_ERROR
    if "stop" in reason or "quit" in reason:
        return END_STOPPED
    # Unknown/redirect reasons: treat as a natural end so the channel keeps going.
    return END_EOF


def _install_fonts_for_mpv(fonts_dir: Path) -> None:
    """Copy bundled .ttf fonts into mpv's config 'fonts' dir so libass finds them.

    mpv automatically loads any fonts placed in ``<mpv config dir>/fonts``, which
    is the most reliable way to make our retro OSD font available to the ASS
    overlays without touching the system-wide fontconfig setup.
    """
    import os
    import shutil

    if not fonts_dir.is_dir():
        return
    config_home = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    dest = Path(config_home) / "mpv" / "fonts"
    try:
        dest.mkdir(parents=True, exist_ok=True)
        for ttf in fonts_dir.glob("*.ttf"):
            target = dest / ttf.name
            if not target.exists():
                shutil.copy2(ttf, target)
    except OSError:
        log.debug("could not install bundled fonts for mpv", exc_info=True)


def _strip_ass(ass: str) -> str:  # pragma: no cover - trivial
    """Very small ASS-tag stripper for the show-text fallback path."""
    import re

    text = re.sub(r"\{[^}]*\}", "", ass)
    text = text.replace("\\N", " ").replace("\\n", " ")
    return text.strip()


__all__ = [
    "Player",
    "MpvPlayer",
    "MockPlayer",
    "END_EOF",
    "END_ERROR",
    "END_STOPPED",
]
