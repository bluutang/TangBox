"""Keyboard / USB / IR remote input via Linux evdev.

Most cheap "media remotes" (and IR remotes bridged through a USB receiver or
LIRC's uinput) show up to Linux as ordinary keyboard-like input devices. This
backend reads their key-down events straight from ``/dev/input/event*`` using
the ``evdev`` package - no X server or desktop required, which is exactly what
we want on a headless Pi wired to a TV.
"""

from __future__ import annotations

import logging
import select
import time
from typing import Callable, Dict, List, Optional, Sequence

from ..actions import InputEvent
from .base import InputBackend
from .keymap import evdev_key_to_event

log = logging.getLogger(__name__)

# Key-event values reported by evdev: 0=up, 1=down, 2=autorepeat.
_KEY_UP = 0
_KEY_DOWN = 1
_KEY_REPEAT = 2

# Debounce window in seconds for repeated identical key-downs (e.g. IR bounce,
# rapid remote multi-packet bursts).
_DUPLICATE_WINDOW = 0.25
_DIGIT_DUPLICATE_WINDOW = 0.15

# Throttle for autorepeated keys (only volume repeats). Linux evdev defaults to
# 30 Hz (33ms repeat interval), which causes runaway changes if passed raw.
_REPEAT_RATE_LIMIT = 0.12


class KeyboardBackend(InputBackend):
    """Reads remote/keyboard events from evdev input devices."""

    name = "keyboard"

    def __init__(
        self,
        *,
        device_paths: Optional[Sequence[str]] = None,
        name_filter: Optional[str] = None,
        grab: bool = False,
        allow_repeat: bool = True,
        overrides: Optional[Dict[str, Optional[InputEvent]]] = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__()
        self._device_paths = list(device_paths) if device_paths else None
        self._name_filter = name_filter.lower() if name_filter else None
        self._grab = grab
        self._allow_repeat = allow_repeat
        # Per-key action overrides from config (key name -> InputEvent or None).
        self._overrides = dict(overrides or {})
        self._clock = clock
        self._last_event: Optional[InputEvent] = None
        self._last_time: float = 0.0
        self._last_repeat_time: float = 0.0
        self._devices: List = []

    def _lookup(self, key_name: str) -> Optional[InputEvent]:
        """Config overrides win over the built-in defaults."""
        if key_name in self._overrides:
            return self._overrides[key_name]  # may be None (explicitly unbound)
        return evdev_key_to_event(key_name)

    @staticmethod
    def is_available() -> bool:
        try:
            import evdev  # noqa: F401
        except ImportError:
            return False
        return True

    def _open_devices(self, paths: Optional[Sequence[str]] = None):
        import evdev
        from evdev import ecodes

        paths = paths or self._device_paths or evdev.list_devices()
        devices = []
        for path in paths:
            try:
                dev = evdev.InputDevice(path)
            except (OSError, PermissionError) as exc:
                log.warning("cannot open input device %s: %s", path, exc)
                continue
            caps = dev.capabilities()
            if ecodes.EV_KEY not in caps:
                dev.close()
                continue
            if self._name_filter and self._name_filter not in (dev.name or "").lower():
                dev.close()
                continue
            if self._grab:
                try:
                    dev.grab()
                except OSError:
                    log.warning("could not grab %s (continuing ungrabbed)", dev.name)
            log.info("listening to input device: %s (%s)", dev.name, path)
            devices.append(dev)
        return devices

    def _run(self) -> None:
        if not self.is_available():
            log.error("evdev is not installed; keyboard/remote input disabled")
            return
        self._devices = self._open_devices()
        if not self._devices:
            log.warning("no usable input devices found for the keyboard backend")
            return

        from evdev import ecodes, list_devices

        fd_to_device = {dev.fd: dev for dev in self._devices}
        last_scan = time.monotonic()
        while not self.stopping:
            now = time.monotonic()
            if now - last_scan >= 3.0:
                last_scan = now
                available_paths = set(list_devices())
                current_paths = {getattr(d, "path", None) for d in fd_to_device.values()}
                new_paths = available_paths - current_paths
                if new_paths:
                    for new_dev in self._open_devices(paths=list(new_paths)):
                        fd_to_device[new_dev.fd] = new_dev
                        self._devices.append(new_dev)

            try:
                r, _, _ = select.select(fd_to_device, [], [], 0.5)
            except (OSError, ValueError):
                break
            for fd in r:
                dev = fd_to_device.get(fd)
                if dev is None:
                    continue
                try:
                    for event in dev.read():
                        if event.type != ecodes.EV_KEY:
                            continue
                        self._handle_key_event(event)
                except OSError:
                    log.warning("input device %s disappeared", getattr(dev, "path", "?"))
                    fd_to_device.pop(fd, None)

    def _handle_key_event(self, event) -> None:
        from evdev import ecodes

        key_name = _code_to_name(ecodes.KEY, event.code)
        if key_name is None:
            return
        self._handle_key_press(key_name, event.value)

    def _handle_key_press(self, key_name: str, value: int) -> None:
        if value == _KEY_DOWN:
            pass
        elif value == _KEY_REPEAT and self._allow_repeat:
            pass
        else:
            return  # key-up, or repeats when disabled

        input_event = self._lookup(key_name)
        if input_event is None:
            return

        from ..actions import Action

        now = self._clock()

        if value == _KEY_REPEAT:
            # Only volume keys should auto-repeat when held.
            # Channel buttons, power, menu/guide, digits, etc. must NEVER auto-repeat:
            # holding a channel button must never cascade through channels.
            if input_event.action not in (Action.VOLUME_UP, Action.VOLUME_DOWN):
                return
            if now - self._last_repeat_time < _REPEAT_RATE_LIMIT:
                return
            self._last_repeat_time = now
            self.emit(input_event)
            return

        # value == _KEY_DOWN: debounce identical consecutive presses to tame
        # contact bounce and duplicate IR frames from remote controls.
        self._last_repeat_time = now
        window = (
            _DIGIT_DUPLICATE_WINDOW
            if input_event.action == Action.DIGIT
            else _DUPLICATE_WINDOW
        )
        if input_event == self._last_event and (now - self._last_time) < window:
            return

        self._last_event = input_event
        self._last_time = now
        self.emit(input_event)

    def _close(self) -> None:
        for dev in self._devices:
            try:
                if self._grab:
                    dev.ungrab()
            except OSError:
                pass
            try:
                dev.close()
            except OSError:
                pass
        self._devices = []


def _code_to_name(key_table, code: int) -> Optional[str]:
    """evdev's KEY table maps a code to a name or a list of aliases."""
    name = key_table.get(code)
    if name is None:
        return None
    if isinstance(name, (list, tuple)):
        return name[0] if name else None
    return name


__all__ = ["KeyboardBackend"]
