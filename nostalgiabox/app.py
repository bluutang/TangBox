"""The television itself: the state machine that ties everything together.

:class:`TVApp` owns the channel lineup, the player, the overlays and the input
queue, and turns remote-control actions into TV behaviour: changing channels
(with a burst of static and a channel banner), adjusting and muting the volume,
direct channel entry by number, an info banner, a "last channel" jump, and a
standby/off mode. When an episode ends it automatically rolls into the next one
on that channel's shuffle, so the box never stops "broadcasting".

The class is written to be testable without a display: pass it a
:class:`~nostalgiabox.player.MockPlayer` and a fake clock and you can single-step
the whole thing (see ``step`` / ``handle_event`` / ``process_pending``).
"""

from __future__ import annotations

import logging
import queue
import random
import subprocess
import time
from pathlib import Path
from typing import Callable, List, Optional, Sequence

from .actions import Action, InputEvent
from .channel import (
    Channel,
    ChannelLineup,
    PlayRequest,
    build_lineup,
    episode_label_for,
    show_name_for,
)
from .artwork import tile_image_for
from .bedtime import deadline_for, due_mark, initial_marks
from .config import Config
from .crt import (
    CONFIG_RUNG,
    crt_ladder,
    default_shader_path,
    write_ladder_shaders,
)
from .guide import Guide, art_rect, guide_ass, page_tiles
from .input.manager import InputManager, create_backends
from .interstitial import CommercialPool
from .overlay import OverlayManager
from .player import END_EOF, END_ERROR, MockPlayer, Player
from .static_gen import (
    COLORBARS_FILENAME,
    DEFAULT_ASSETS_DIR,
    GLITCH_FILENAME,
    POWER_OFF_FILENAME,
    STATIC_FILENAME,
)

log = logging.getLogger(__name__)

# The sign-on, in order. Each stage is optional; the sequence skips any
# whose asset is missing and tunes in if none of them have anything.
_SIGN_ON_STAGES = ("zap", "bars", "logo")

# How long to hold before halting, so the collapse is actually seen. Matches
# generate_power_off's duration with a little slack for mpv to get going.
SIGN_OFF_SECONDS = 1.1


class TVApp:
    """The retro-TV application state machine."""

    def __init__(
        self,
        config: Config,
        player: Player,
        input_manager: InputManager,
        *,
        overlay: Optional[OverlayManager] = None,
        clock: Callable[[], float] = time.monotonic,
        assets_dir: Optional[Path] = None,
        sleep: Callable[[float], None] = time.sleep,
        crt_shader_dir: Optional[Path] = None,
    ) -> None:
        self.config = config
        self.player = player
        self.input = input_manager
        self.overlay = overlay or OverlayManager(player, config, clock=clock)
        self._clock = clock
        self._sleep = sleep

        self.lineup: ChannelLineup = build_lineup(config)

        # Runtime state.
        self.volume = config.initial_volume
        self.muted = False
        self.standby = False
        self.powered_off = False
        self._playing_path: Optional[Path] = None
        self._last_channel_number: Optional[int] = None
        self._running = False

        # The channel guide. A LAYER, not a mode: while it is closed nothing
        # else in here behaves any differently.
        self.guide = Guide(
            count=len(self.lineup),
            timeout=config.guide.timeout_seconds,
            clock=clock,
            page_cols=config.guide.page_cols,
            page_rows=config.guide.page_rows,
        )
        self._rng = random.Random(config.shuffle_seed)

        # The CRT intensity ladder, stepped by the remote's INPUT button. The
        # box starts on whatever config.yaml says and NEVER writes back to it:
        # a child cannot permanently change how the television looks, and the
        # file stays the source of truth across a restart.
        self._crt_ladder = crt_ladder(config.crt)
        self._crt_index = CONFIG_RUNG
        self._crt_shader_dir = crt_shader_dir or default_shader_path().parent
        self._crt_paths: Optional[tuple[Optional[Path], ...]] = None

        # Bedtime. The deadline is fixed the moment the button is pressed and
        # NOTHING afterwards moves it - not a channel change, not an episode
        # ending. Otherwise a 4-year-old learns that channel-up buys another
        # twenty minutes, and this becomes a negotiating position.
        self.bedtime_deadline: Optional[float] = None
        self._bedtime_marks: set[int] = set()

        # Direct channel entry ("type 1 then 2 -> channel 12").
        self._digit_buffer = ""
        self._digit_deadline = 0.0
        self._digit_entry_timeout = 2.0

        # Pending "bridge" switch: keep the old show playing until this deadline,
        # then cut to the channel that was preloaded. The channel banner is shown
        # at the moment of the cut-over, not when the button is pressed.
        self._switch_deadline: Optional[float] = None
        self._pending_banner: Optional[
            tuple[int, str, Optional[str], Optional[str]]
        ] = None

        # Commercial breaks between episodes. `_pending_episode` is set for
        # exactly as long as a break is running - it is the episode waiting on
        # the other side of it - so it doubles as "are we in a break?".
        self.commercials = CommercialPool(
            config.commercials.path,
            break_seconds=config.commercials.break_seconds,
            extensions=config.video_extensions,
            enabled=config.commercials.enabled,
            recursive=config.scan_recursive,
        )
        self._break_queue: List[Path] = []
        self._pending_episode: Optional[PlayRequest] = None

        # Playback-finished events from the player (may arrive on any thread).
        self._ended: "queue.Queue[str]" = queue.Queue()
        self.player.on_end = self._ended.put

        # Filler assets.
        self._assets_dir = assets_dir or config.assets_dir or DEFAULT_ASSETS_DIR
        self._colorbars_path = self._resolve_asset(COLORBARS_FILENAME)
        self._logo_path = self._resolve_asset(config.sign_on.logo)
        self._zap_path = self._resolve_asset(config.sign_on.power_on)
        self._power_off_path = self._resolve_asset(POWER_OFF_FILENAME)
        # Sign-on state: None (on air), "bars", or "logo".
        self._sign_on_stage: Optional[str] = None
        self._sign_on_deadline: Optional[float] = None
        # The channel-change transition clip depends on the configured effect.
        self._transition_path = self._resolve_transition_asset()

    # -- construction -------------------------------------------------------
    @classmethod
    def from_config(
        cls,
        config: Config,
        *,
        player: Optional[Player] = None,
        input_manager: Optional[InputManager] = None,
        dry_run: bool = False,
        assets_dir: Optional[Path] = None,
    ) -> "TVApp":
        """Build a fully wired app, creating real hardware backends by default.

        ``dry_run`` swaps in a :class:`MockPlayer` and disables all real input
        backends (a stdin backend is added if a TTY is available), which is how
        the box can be exercised on a development machine.
        """
        if player is None:
            if dry_run:
                player = MockPlayer(verbose=True)
            else:
                from .crt import write_shader
                from .player import MpvPlayer

                assets = assets_dir or config.assets_dir or DEFAULT_ASSETS_DIR
                shader_path = write_shader(config.crt)
                player = MpvPlayer(
                    glsl_shaders=str(shader_path) if shader_path else None,
                    fonts_dir=assets / "fonts",
                    fullscreen=config.fullscreen,
                    force_4_3=config.force_4_3,
                    audio_device=config.audio_device,
                    display_mode=config.display_mode,
                )

        if input_manager is None:
            if dry_run:
                backends = create_backends({"keyboard": False, "cec": False, "stdin": True})
            else:
                backends = create_backends(config.input_options)
            input_manager = InputManager(backends)

        return cls(config, player, input_manager, assets_dir=assets_dir)

    # -- lifecycle ----------------------------------------------------------
    def start(self) -> None:
        """Power on: set volume, start input, and tune to the first channel."""
        self.player.set_volume(self.volume)
        self.player.set_mute(self.muted)
        self.input.start()
        self._select_start_channel()
        if not self._begin_sign_on():
            self.tune_current(show_static=False)

    # -- sign-on ------------------------------------------------------------
    @property
    def signing_on(self) -> bool:
        """True while the station is signing on, before any channel is showing."""
        return self._sign_on_stage is not None

    def _begin_sign_on(self) -> bool:
        """Start the sequence. False means "nothing to show, just tune in".

        This runs before any television happens, so every stage is optional and
        every branch degrades to tuning in. A missing asset must never cost the
        kids their cartoons.
        """
        if not self.config.sign_on.enabled:
            return False
        return self._enter_sign_on_stage_after(None)

    def _enter_sign_on_stage_after(self, previous: Optional[str]) -> bool:
        """Start the first stage after ``previous`` that has something to show.

        Walking an ordered list rather than chaining "if this fails try that"
        keeps every stage genuinely optional - the zap, the bars and the ident
        can each be absent without the others caring.
        """
        start = 0 if previous is None else _SIGN_ON_STAGES.index(previous) + 1
        for stage in _SIGN_ON_STAGES[start:]:
            if self._start_sign_on_stage(stage):
                return True
        self._sign_on_stage = None
        self._sign_on_deadline = None
        return False

    def _start_sign_on_stage(self, stage: str) -> bool:
        """Begin one stage, or return False if it has no asset to play."""
        if stage == "zap":
            if self._zap_path is None:
                return False
            self.player.play(self._zap_path)
        elif stage == "bars":
            if self.config.sign_on.bars_seconds <= 0 or self._colorbars_path is None:
                return False
            self.player.play_loop(self._colorbars_path)
        elif stage == "logo":
            if self._logo_path is None:
                return False
            self.player.play(self._logo_path)
        else:  # pragma: no cover - guarded by _SIGN_ON_STAGES
            return False

        self._sign_on_stage = stage
        # Only the bars are timed. The clips end on their own and are advanced
        # from the playback drain.
        self._sign_on_deadline = (
            self._clock() + self.config.sign_on.bars_seconds if stage == "bars" else None
        )
        return True

    def _advance_sign_on(self, after: str) -> None:
        if not self._enter_sign_on_stage_after(after):
            self._finish_sign_on()

    def _maybe_advance_sign_on(self, now: float) -> None:
        """Colour bars are timed; the clips end on their own (see the drain)."""
        if self._sign_on_stage != "bars" or self._sign_on_deadline is None:
            return
        if now < self._sign_on_deadline:
            return
        self._advance_sign_on("bars")

    def _finish_sign_on(self) -> None:
        """Hand over to the first channel. Safe to call at any stage."""
        self._sign_on_stage = None
        self._sign_on_deadline = None
        self.tune_current(show_static=False)

    def run(self) -> None:
        """Run the blocking main loop until a QUIT action is received."""
        self.start()
        self._running = True
        log.info("TangBox is on the air. %d channels.", len(self.lineup))
        try:
            while self._running:
                self.step(block=True)
        except KeyboardInterrupt:  # pragma: no cover - interactive convenience
            log.info("interrupted; shutting down")
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        self._running = False
        try:
            self.overlay.clear_all()
        except Exception:  # noqa: BLE001
            pass
        self.input.stop()
        self.player.close()

    # -- main-loop step (small and testable) --------------------------------
    def step(self, *, block: bool = False, timeout: float = 0.1) -> None:
        """Advance the state machine by one iteration.

        Handles overlay expiry, channel-entry timeouts, finished episodes, and
        at most one queued input event.
        """
        now = self._clock()
        self.overlay.tick()
        self._tick_guide()
        self._maybe_advance_sign_on(now)
        self._maybe_commit_switch(now)
        self._maybe_commit_digits(now)
        self._drain_playback_events()
        self._tick_bedtime(now)

        event = self.input.get(timeout=timeout if block else 0.0)
        if event is not None:
            self.handle_event(event)

    def _maybe_commit_switch(self, now: float) -> None:
        """Cut over to the preloaded channel once the bridge window has elapsed."""
        if self._switch_deadline is not None and now >= self._switch_deadline:
            self._switch_deadline = None
            self.player.commit_switch()
            # Flash the channel banner right as the picture actually changes.
            if self._pending_banner is not None:
                number, name, show, episode = self._pending_banner
                self.overlay.show_channel_bug(
                    number, name, show=show, episode=episode
                )
                self._pending_banner = None

    # -- input handling -----------------------------------------------------
    def handle_event(self, event: InputEvent) -> None:
        action = event.action

        if action == Action.QUIT:
            self._running = False
            return
        # Any press during the sign-on skips it, and is consumed doing so - a
        # channel-up here means "get on with it", not "channel 3".
        if self.signing_on:
            self._finish_sign_on()
            return

        if action == Action.POWER:
            # Power still works while the guide is open rather than being
            # swallowed by it: close the guide first either way.
            self._close_guide()
            if self.config.power_button == "shutdown":
                self._power_off()
            else:
                self._toggle_standby()
            return

        # While in standby, ignore everything except POWER/QUIT (handled above).
        if self.standby:
            return

        # While the guide is open it gets first refusal on each press. What it
        # does NOT take - the dedicated channel and volume keys - falls through
        # and works exactly as it does with the guide closed. That is what
        # splitting the d-pad off from those keys bought.
        if self.guide.is_open and self._guide_consumes(action):
            return

        handlers = {
            Action.CHANNEL_UP: self._channel_up,
            Action.CHANNEL_DOWN: self._channel_down,
            Action.VOLUME_UP: self._volume_up,
            Action.VOLUME_DOWN: self._volume_down,
            Action.MUTE: self._toggle_mute,
            Action.INFO: self._show_info,
            Action.LAST_CHANNEL: self._jump_last_channel,
            Action.ENTER: self._enter_pressed,
            # The d-pad with the guide CLOSED - unchanged behaviour: up/down
            # change channel, left/right change volume.
            Action.NAV_UP: self._channel_up,
            Action.NAV_DOWN: self._channel_down,
            Action.NAV_RIGHT: self._volume_up,
            Action.NAV_LEFT: self._volume_down,
            Action.HOME: self._open_guide,
            Action.RANDOM: self._random_channel,
            Action.CRT_CYCLE: self._cycle_crt,
            Action.BEDTIME: self._toggle_bedtime,
        }
        if action == Action.DIGIT:
            self._push_digit(event.value or 0)
        else:
            handler = handlers.get(action)
            if handler is not None:
                handler()

        # Something that fell through may have changed what the guide should
        # show - most obviously the ON NOW marker when the dedicated channel
        # buttons are used while browsing - so redraw it.
        if self.guide.is_open:
            self._draw_guide()

    def _toggle_bedtime(self) -> None:
        """Arm the sign-off, or cancel one already armed."""
        if self.bedtime_deadline is not None:
            self.bedtime_deadline = None
            self._bedtime_marks = set()
            self.overlay.show_message("CARRY ON")
            return
        now = self._clock()
        self.bedtime_deadline = deadline_for(
            now,
            position=self.player.get_time_pos() or 0.0,
            runtime=self.player.get_duration(),
        )
        remaining = self.bedtime_deadline - now
        self._bedtime_marks = initial_marks(remaining)
        self.overlay.show_message(f"{int(remaining // 60)} MIN")

    def _tick_bedtime(self, now: float) -> None:
        """Count down to the sign-off, then take the box off the air."""
        if self.bedtime_deadline is None or self.powered_off:
            return
        remaining = self.bedtime_deadline - now
        if remaining <= 0:
            self._power_off()
            return
        mark = due_mark(remaining, self._bedtime_marks)
        if mark is not None:
            self._bedtime_marks.add(mark)
            self.overlay.show_message(f"{mark} MIN")

    def _cycle_crt(self) -> None:
        """Step the CRT picture effect to the next look and name it on screen."""
        if self._crt_paths is None:
            # Written on first use rather than at startup: most sessions never
            # touch this button, and it costs three file writes.
            self._crt_paths = write_ladder_shaders(
                self._crt_ladder, self._crt_shader_dir
            )
        self._crt_index = (self._crt_index + 1) % len(self._crt_ladder)
        self.player.set_crt_shader(self._crt_paths[self._crt_index])
        self.overlay.show_message(self._crt_ladder[self._crt_index].name)

    # -- the channel guide --------------------------------------------------
    def _guide_consumes(self, action: Action) -> bool:
        """Offer a press to the open guide. True means it was used up."""
        if action in (Action.HOME, Action.LAST_CHANNEL):
            # Home toggles it shut; Back leaves without changing anything.
            self._close_guide()
            return True
        if action == Action.ENTER:
            self._tune_from_guide()
            return True
        moves = {
            Action.NAV_UP: self.guide.up,
            Action.NAV_DOWN: self.guide.down,
            Action.NAV_LEFT: self.guide.left,
            Action.NAV_RIGHT: self.guide.right,
        }
        move = moves.get(action)
        if move is None:
            return False
        move()
        self._draw_guide()
        return True

    def _open_guide(self) -> None:
        index = self.lineup.index_of(self.lineup.current.number)
        self.guide.open(cursor=0 if index is None else index)
        self._draw_guide()

    def _close_guide(self) -> None:
        self.guide.close()
        self.overlay.clear_guide()
        self.player.clear_images()

    def _draw_guide(self) -> None:
        """Draw both layers of the guide: the pictures, then the text on top."""
        channels = list(self.lineup)
        artwork = [self._tile_picture(channel) for channel in channels]
        self._draw_guide_pictures(artwork)
        self.overlay.show_guide(
            guide_ass(
                [(c.number, c.name) for c in channels],
                self.guide.cursor,
                self.config.ui,
                on_now=self.lineup.index_of(self.lineup.current.number),
                dim=self.config.guide.dim,
                page_cols=self.config.guide.page_cols,
                page_rows=self.config.guide.page_rows,
                artwork=[picture is not None for picture in artwork],
            )
        )

    def _tile_picture(self, channel: Channel) -> Optional[Path]:
        """The picture for whatever ``channel`` would put on screen, or None.

        For the channel on air that is what is playing. For every other channel
        it is what tuning there would start, which is why Channel.peek_next
        exists - nothing is playing on a channel nobody is watching. Either way
        the tile promises the programme you would actually get.
        """
        if channel.number == self.lineup.current.number and self._playing_path:
            episode = self._playing_path
        else:
            episode = channel.peek_next()
        if episode is None:
            return None
        return tile_image_for(episode, channel.config.path)

    def _draw_guide_pictures(self, artwork: Sequence[Optional[Path]]) -> None:
        """Put a picture in the picture area of every visible tile that has one.

        Positioned from page_tiles, the same function the text layer draws
        from, so a picture cannot land a few pixels off the name below it.
        """
        self.player.clear_images()
        rects = page_tiles(
            len(artwork),
            self.guide.cursor,
            self.config.guide.page_cols,
            self.config.guide.page_rows,
        )
        for slot, rect in enumerate(rects):
            picture = artwork[rect.index]
            if picture is None:
                continue
            art_x, art_y, art_w, art_h = art_rect(rect)
            self.player.show_image(
                slot, picture, round(art_x), round(art_y), round(art_w), round(art_h)
            )

    def _tick_guide(self) -> None:
        """Let the guide close itself after sitting untouched."""
        if not self.guide.is_open:
            return
        self.guide.tick()
        if not self.guide.is_open:
            # Without this the pictures would stay on screen after the guide
            # timed out, sitting over the programme with nothing left to
            # remove them.
            self.overlay.clear_guide()
            self.player.clear_images()

    def _tune_from_guide(self) -> None:
        numbers = self.lineup.numbers
        target = numbers[self.guide.cursor] if numbers else None
        self._close_guide()
        if target is None:
            return
        # Selecting the channel already playing must not re-tune it: tune_in is
        # random, so it would restart on a different episode. That rule lives in
        # select_channel_number, which refuses to re-tune the current channel,
        # so this hands every case to it rather than keeping a second copy.
        self.select_channel_number(target)

    def _enter_pressed(self) -> None:
        """OK confirms a typed channel number, or opens the guide if none."""
        if self._digit_buffer:
            self._confirm_digits()
            return
        # Single digits tune instantly, so OK does almost nothing while
        # watching. Making it open the guide means the box still works on a
        # remote with no Home button at all.
        self._open_guide()

    def _random_channel(self) -> None:
        """Tune somewhere else at random.

        Excludes the channel already playing. Without that the button
        sometimes appears to do nothing, or restarts the current channel on a
        different episode, which reads as a fault.

        For a pre-reader this may be the most valuable button on the remote:
        it always does something good and requires no reading.
        """
        self._close_guide()
        others = [n for n in self.lineup.numbers if n != self.lineup.current.number]
        if not others:
            return
        self.select_channel_number(self._rng.choice(others))

    # -- channel changing ---------------------------------------------------
    def _channel_up(self) -> None:
        self._remember_position()
        self._last_channel_number = self.lineup.current.number
        self.lineup.up()
        self.tune_current()

    def _channel_down(self) -> None:
        self._remember_position()
        self._last_channel_number = self.lineup.current.number
        self.lineup.down()
        self.tune_current()

    def _jump_last_channel(self) -> None:
        if self._last_channel_number is None:
            return
        target = self._last_channel_number
        if not self.lineup.has_number(target):
            return
        self._remember_position()
        self._last_channel_number = self.lineup.current.number
        self.lineup.select_number(target)
        self.tune_current()

    def select_channel_number(self, number: int) -> bool:
        """Tune directly to a channel number. Returns False if it doesn't exist."""
        if not self.lineup.has_number(number):
            self.overlay.show_message(f"CH {number:02d}  -  NO CHANNEL")
            return False
        if number == self.lineup.current.number:
            self._show_info()
            return True
        self._remember_position()
        self._last_channel_number = self.lineup.current.number
        self.lineup.select_number(number)
        self.tune_current()
        return True

    def tune_current(self, *, show_static: bool = True) -> None:
        """Tune into the currently selected channel."""
        channel = self.lineup.current
        self.overlay.clear_standby()
        # Changing channel abandons any break in progress - you don't come back
        # to the middle of the adverts you walked away from.
        self._clear_break()

        request = channel.tune_in()
        self._pending_banner = None

        if request is None:
            # No episodes on this channel: show the "no signal" screen.
            self.overlay.show_channel_bug(channel.number, channel.name)
            self._show_no_signal(channel)
            return

        if not show_static:
            # Not a channel change (first tune / waking from standby): play now.
            self._switch_deadline = None
            self.overlay.show_channel_bug(
                channel.number,
                channel.name,
                show=self._show_name(channel, request.path),
                episode=episode_label_for(request.path),
            )
            self._play_request(request)
        elif self._transition_path is not None:
            # Transition clip (glitch/static) + preloaded episode.
            self._switch_deadline = None
            self.overlay.show_channel_bug(
                channel.number,
                channel.name,
                show=self._show_name(channel, request.path),
                episode=episode_label_for(request.path),
            )
            self._playing_path = request.path
            self.player.play_transition(
                self._transition_path,
                request.path,
                start=request.start,
                static_seconds=self.config.transition_duration,
            )
        elif self.config.bridge_seconds > 0 and self._playing_path is not None:
            # No transition effect: keep the current show playing while the next
            # channel preloads, then cut over (no frozen frame). The banner is
            # shown at the cut-over (see _maybe_commit_switch), not right now.
            self._playing_path = request.path
            self.player.preload_next(request.path, start=request.start)
            self._switch_deadline = self._clock() + self.config.bridge_seconds
            self._pending_banner = (
                channel.number,
                channel.name,
                self._show_name(channel, request.path),
                episode_label_for(request.path),
            )
        else:
            self._switch_deadline = None
            self.overlay.show_channel_bug(
                channel.number,
                channel.name,
                show=self._show_name(channel, request.path),
                episode=episode_label_for(request.path),
            )
            self._play_request(request)

    def _show_name(self, channel: Channel, path: Optional[Path]) -> Optional[str]:
        """Which programme is on: the folder the episode sits in, or None.

        None for an advert, or an episode loose in the channel folder - the
        banner then omits the line rather than showing a blank one.
        """
        if path is None:
            return None
        return show_name_for(path, channel.config.path)

    def _play_request(self, request: PlayRequest) -> None:
        self._playing_path = request.path
        self.player.play(request.path, start=request.start)

    def _show_no_signal(self, channel: Channel) -> None:
        self._switch_deadline = None
        self._pending_banner = None
        self._playing_path = None
        if self._colorbars_path is not None:
            self.player.play_loop(self._colorbars_path)
        else:
            self.player.stop()
        self.overlay.show_message(
            f"CH {channel.number:02d}  {channel.name}  -  NO SIGNAL", duration=6.0
        )

    # -- volume -------------------------------------------------------------
    def _volume_up(self) -> None:
        self._set_volume(self.volume + self.config.volume_step, unmute=True)

    def _volume_down(self) -> None:
        # One press below zero cleanly powers off the box (safe to unplug).
        if self.config.power_off_on_min_volume and not self.muted and self.volume <= 0:
            self._power_off()
            return
        self._set_volume(self.volume - self.config.volume_step, unmute=True)

    def _set_volume(self, value: int, *, unmute: bool = False) -> None:
        self.volume = max(0, min(100, value))
        if unmute and self.muted:
            self.muted = False
            self.player.set_mute(False)
        self.player.set_volume(self.volume)
        self.overlay.show_volume(self.volume, self.muted)

    def _power_off(self) -> None:
        """Cleanly shut the Pi down so it's safe to unplug."""
        log.info("powering off (volume floor)")
        self.powered_off = True
        self._switch_deadline = None
        self._pending_banner = None
        # Everything here is best-effort. This sits in front of an actual
        # shutdown, and ceremony must never be able to PREVENT one - a telly
        # that will not switch off is worse than one that switches off without
        # any flourish. Hence the bare except and the bounded wait.
        try:
            self.overlay.clear_all()
            if self._power_off_path is not None:
                self.player.play(self._power_off_path)
                # A fixed, bounded wait rather than waiting for an end-of-clip
                # event: the main loop is about to stop, and nothing here may
                # hang the halt.
                self._sleep(SIGN_OFF_SECONDS)
            else:
                self.overlay.show_message("GOODBYE", duration=0)
            self.player.stop()
        except Exception:  # noqa: BLE001
            log.debug("sign-off did not play; halting anyway", exc_info=True)
        # After the collapse, so it is actually seen, and before the halt, so
        # the kernel's parting line lands on a television that is already off.
        self._run_tv_standby_command()
        self._run_power_off_command()
        self._running = False  # exit the main loop

    def _run_tv_standby_command(self) -> None:
        """Ask the television to switch off as well, if configured.

        Best-effort like everything else on this path. CEC is the flakiest
        thing in the box and it must never be able to keep the Pi running - a
        telly that will not switch off is worse than one whose screen stays on
        for a moment.
        """
        command = list(self.config.tv_standby_command)
        if not command:
            return  # leave the television alone
        try:
            subprocess.Popen(command)
        except Exception:  # noqa: BLE001
            log.warning("tv standby command failed, halting anyway: %s", command)

    def _run_power_off_command(self) -> None:
        command = list(self.config.power_off_command)
        if not command:
            return  # disabled / test mode
        try:
            subprocess.Popen(command)
        except Exception:  # noqa: BLE001
            log.exception("power-off command failed: %s", command)

    def _toggle_mute(self) -> None:
        self.muted = not self.muted
        self.player.set_mute(self.muted)
        self.overlay.show_volume(self.volume, self.muted)

    # -- info / standby -----------------------------------------------------
    def _billed_path(self) -> Optional[Path]:
        """The episode the banner should name, adverts included.

        During a break the thing on screen is an advert, which belongs to no
        programme - but the CHANNEL has not changed and the held episode is
        coming straight back. Naming it is what a real broadcaster does: the
        channel bug stays up through the ads so you can see what you are
        waiting for. Going quiet would mean a bare channel number for a minute
        at a time.
        """
        if self._pending_episode is not None:
            return self._pending_episode.path
        return self._playing_path

    def _show_info(self) -> None:
        """Re-show the banner for whatever is on RIGHT NOW."""
        channel = self.lineup.current
        path = self._billed_path()
        # The timeline rides along on THIS banner only. Channel changes call
        # show_channel_bug without these, so tuning looks exactly as it always
        # has - which is what the children see all evening.
        self.overlay.show_channel_bug(
            channel.number,
            channel.name,
            show=self._show_name(channel, path),
            episode=episode_label_for(path) if path is not None else None,
            position=self.player.get_time_pos(),
            runtime=self.player.get_duration(),
        )

    def _toggle_standby(self) -> None:
        self.standby = not self.standby
        if self.standby:
            self._remember_position()
            self._switch_deadline = None
            self._pending_banner = None
            self.player.stop()
            self.overlay.clear_all()
            self.overlay.show_standby()
        else:
            self.overlay.clear_standby()
            self.tune_current(show_static=False)

    # -- direct channel entry ----------------------------------------------
    def _push_digit(self, digit: int) -> None:
        self._digit_buffer = (self._digit_buffer + str(digit))[-3:]
        # Tune the moment the entry cannot become a different channel. The box
        # only ever waited in case a second digit was coming, so on a lineup of
        # 2/4/6/8 it was pausing two seconds over a channel that could not
        # exist. Once the number pad is the main way around the box that is a
        # delay on nearly every press, in front of someone who will assume it
        # did not work and press it again.
        if not self._entry_could_grow():
            self._confirm_digits()
            return
        self._digit_deadline = self._clock() + self._digit_entry_timeout
        self.overlay.show_message(f"CH {self._digit_buffer}_", duration=self._digit_entry_timeout)

    def _entry_could_grow(self) -> bool:
        """Could another digit still turn this entry into a different channel?

        True only while some LONGER channel number starts with what has been
        typed - typing 1 where 12 and 14 exist. That is the one case worth
        waiting through, and it is what keeps double-digit channels reachable.
        """
        typed = self._digit_buffer
        return any(
            len(str(number)) > len(typed) and str(number).startswith(typed)
            for number in self.lineup.numbers
        )

    def _confirm_digits(self) -> None:
        if not self._digit_buffer:
            return
        number = int(self._digit_buffer)
        self._digit_buffer = ""
        self._digit_deadline = 0.0
        self.select_channel_number(number)

    def _maybe_commit_digits(self, now: float) -> None:
        if self._digit_buffer and now >= self._digit_deadline:
            self._confirm_digits()

    # -- playback-finished handling ----------------------------------------
    def _drain_playback_events(self) -> None:
        advanced = False
        while True:
            try:
                reason = self._ended.get_nowait()
            except queue.Empty:
                break
            if self._sign_on_stage in ("zap", "logo") and reason in (
                END_EOF,
                END_ERROR,
            ):
                # A sign-on clip finished. That is a cue to move on - emphatically
                # NOT a finished episode, which would burn one before anyone had
                # seen it.
                self._advance_sign_on(self._sign_on_stage)
                continue
            # With bedtime armed, a finished programme is the end of the
            # evening: never start something nobody is going to watch. The
            # deadline is the LATEST it can end, not the earliest.
            if (
                reason in (END_EOF, END_ERROR)
                and self.bedtime_deadline is not None
                and not self.standby
                and self._break_queue == []
                and self._pending_episode is None
            ):
                self._power_off()
                return
            # Coalesce: only advance once even if several events queued up.
            if reason in (END_EOF, END_ERROR) and not advanced and not self.standby:
                self._advance_current()
                advanced = True

    def _advance_current(self) -> None:
        """Something finished. Decide what plays next.

        Three cases, in order: we are part-way through a commercial break; a
        break has just ended and the episode it was holding is due; or a real
        episode ended, in which case we go to break before the next one.
        """
        if self._break_queue:
            self._play_request(PlayRequest(path=self._break_queue.pop(0)))
            return

        if self._pending_episode is not None:
            request, self._pending_episode = self._pending_episode, None
            self._play_request(request)
            return

        request = self.lineup.current.advance()
        if request is None:
            self._show_no_signal(self.lineup.current)
            return

        clips = self.commercials.build_break()
        if not clips:
            self._play_request(request)
            return

        # Hold the episode back and roll the first advert. `_pending_episode`
        # staying set is what marks us as "in a break" until it plays.
        self._pending_episode = request
        self._break_queue = list(clips[1:])
        self._play_request(PlayRequest(path=clips[0]))

    def _clear_break(self) -> None:
        """Abandon any commercial break in progress (e.g. on a channel change)."""
        self._break_queue = []
        self._pending_episode = None

    @property
    def in_break(self) -> bool:
        """True while a commercial break is running."""
        return self._pending_episode is not None

    # -- helpers ------------------------------------------------------------
    def _remember_position(self) -> None:
        # An advert is not an episode: remembering its path would make "resume"
        # come back to the middle of a cereal commercial.
        if self.config.tune_in != "resume" or self._playing_path is None or self.in_break:
            return
        pos = self.player.get_time_pos()
        if pos is not None:
            self.lineup.current.remember(self._playing_path, pos)

    def _select_start_channel(self) -> None:
        if self.config.start_channel is not None and self.lineup.has_number(
            self.config.start_channel
        ):
            self.lineup.select_number(self.config.start_channel)

    def _resolve_asset(self, filename: str) -> Optional[Path]:
        path = self._assets_dir / filename
        return path if path.is_file() else None

    def _resolve_transition_asset(self) -> Optional[Path]:
        effect = self.config.transition_effect
        if effect == "none":
            return None
        filename = GLITCH_FILENAME if effect == "glitch" else STATIC_FILENAME
        return self._resolve_asset(filename)


def run_from_config(config: Config, *, dry_run: bool = False) -> None:
    """Convenience entry point used by the CLI."""
    app = TVApp.from_config(config, dry_run=dry_run)
    app.run()


__all__ = ["TVApp", "run_from_config"]
