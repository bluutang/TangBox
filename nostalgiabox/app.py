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
import subprocess
import time
from pathlib import Path
from typing import Callable, List, Optional

from .actions import Action, InputEvent
from .channel import (
    Channel,
    ChannelLineup,
    PlayRequest,
    build_lineup,
    show_name_for,
)
from .config import Config
from .input.manager import InputManager, create_backends
from .interstitial import CommercialPool
from .overlay import OverlayManager
from .player import END_EOF, END_ERROR, MockPlayer, Player
from .static_gen import (
    COLORBARS_FILENAME,
    DEFAULT_ASSETS_DIR,
    GLITCH_FILENAME,
    STATIC_FILENAME,
)

log = logging.getLogger(__name__)


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
    ) -> None:
        self.config = config
        self.player = player
        self.input = input_manager
        self.overlay = overlay or OverlayManager(player, config, clock=clock)
        self._clock = clock

        self.lineup: ChannelLineup = build_lineup(config)

        # Runtime state.
        self.volume = config.initial_volume
        self.muted = False
        self.standby = False
        self.powered_off = False
        self._playing_path: Optional[Path] = None
        self._last_channel_number: Optional[int] = None
        self._running = False

        # Direct channel entry ("type 1 then 2 -> channel 12").
        self._digit_buffer = ""
        self._digit_deadline = 0.0
        self._digit_entry_timeout = 2.0

        # Pending "bridge" switch: keep the old show playing until this deadline,
        # then cut to the channel that was preloaded. The channel banner is shown
        # at the moment of the cut-over, not when the button is pressed.
        self._switch_deadline: Optional[float] = None
        self._pending_banner: Optional[tuple[int, str, Optional[str]]] = None

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

        This runs before any television happens, so every branch degrades to
        tuning in. A missing logo must never cost the kids their cartoons.
        """
        cfg = self.config.sign_on
        if not cfg.enabled:
            return False
        if cfg.bars_seconds > 0 and self._colorbars_path is not None:
            self._sign_on_stage = "bars"
            self._sign_on_deadline = self._clock() + cfg.bars_seconds
            self.player.play_loop(self._colorbars_path)
            return True
        return self._play_sign_on_logo()

    def _play_sign_on_logo(self) -> bool:
        if self._logo_path is None:
            return False
        self._sign_on_stage = "logo"
        self._sign_on_deadline = None
        self.player.play(self._logo_path)
        return True

    def _maybe_advance_sign_on(self, now: float) -> None:
        """Colour bars are timed; the logo ends on its own (see the drain)."""
        if self._sign_on_stage != "bars" or self._sign_on_deadline is None:
            return
        if now < self._sign_on_deadline:
            return
        if not self._play_sign_on_logo():
            self._finish_sign_on()

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
        self._maybe_advance_sign_on(now)
        self._maybe_commit_switch(now)
        self._maybe_commit_digits(now)
        self._drain_playback_events()

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
                number, name, show = self._pending_banner
                self.overlay.show_channel_bug(number, name, show=show)
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
            self._toggle_standby()
            return

        # While in standby, ignore everything except POWER/QUIT (handled above).
        if self.standby:
            return

        handlers = {
            Action.CHANNEL_UP: self._channel_up,
            Action.CHANNEL_DOWN: self._channel_down,
            Action.VOLUME_UP: self._volume_up,
            Action.VOLUME_DOWN: self._volume_down,
            Action.MUTE: self._toggle_mute,
            Action.INFO: self._show_info,
            Action.LAST_CHANNEL: self._jump_last_channel,
            Action.ENTER: self._confirm_digits,
        }
        if action == Action.DIGIT:
            self._push_digit(event.value or 0)
        else:
            handler = handlers.get(action)
            if handler is not None:
                handler()

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
                channel.number, channel.name, show=self._show_name(channel, request.path)
            )
            self._play_request(request)
        elif self._transition_path is not None:
            # Transition clip (glitch/static) + preloaded episode.
            self._switch_deadline = None
            self.overlay.show_channel_bug(
                channel.number, channel.name, show=self._show_name(channel, request.path)
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
            )
        else:
            self._switch_deadline = None
            self.overlay.show_channel_bug(
                channel.number, channel.name, show=self._show_name(channel, request.path)
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
        try:
            self.overlay.clear_all()
            self.overlay.show_message("GOODBYE", duration=0)
            self.player.stop()
        except Exception:  # noqa: BLE001
            pass
        self._run_power_off_command()
        self._running = False  # exit the main loop

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
    def _show_info(self) -> None:
        """Re-show the banner for whatever is on RIGHT NOW.

        Unlike tuning in, there is no PlayRequest to hand - the show has to come
        from whatever is currently playing. During a commercial break that is an
        advert, which belongs to no channel, so the line is correctly omitted.
        """
        channel = self.lineup.current
        self.overlay.show_channel_bug(
            channel.number,
            channel.name,
            show=self._show_name(channel, self._playing_path),
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
        self._digit_deadline = self._clock() + self._digit_entry_timeout
        self.overlay.show_message(f"CH {self._digit_buffer}_", duration=self._digit_entry_timeout)

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
            if self._sign_on_stage == "logo" and reason in (END_EOF, END_ERROR):
                # The logo finished. That is the cue to tune in - emphatically
                # not a finished episode, which would burn one before anyone
                # had seen it.
                self._finish_sign_on()
                continue
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
