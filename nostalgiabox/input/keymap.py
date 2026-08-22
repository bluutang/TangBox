"""Mapping from raw remote/keyboard keys to high-level actions.

Two worlds feed in here:

* Linux input-event key *names* (``KEY_VOLUMEUP`` etc.) - used by both the
  evdev backend (real USB/IR remotes and keyboards) and the stdin dev backend
  after it translates characters to these names.
* HDMI-CEC user-control *names* (``volume up`` etc.) - used by the CEC backend.

Cheap USB/IR "media remotes" report a grab-bag of different key codes, so the
map is deliberately generous: several physical keys can map to the same action.
"""

from __future__ import annotations

from typing import Dict, Optional

from ..actions import Action, InputEvent

# --------------------------------------------------------------------------
# Linux evdev key names -> InputEvent
# --------------------------------------------------------------------------
_EVDEV_ACTIONS: Dict[str, InputEvent] = {
    # Channel changing - the DEDICATED keys. These always change channel, even
    # while the channel guide is open, which is why they are kept separate from
    # the D-pad below.
    "KEY_CHANNELUP": InputEvent(Action.CHANNEL_UP),
    "KEY_PAGEUP": InputEvent(Action.CHANNEL_UP),
    "KEY_CHANNELDOWN": InputEvent(Action.CHANNEL_DOWN),
    "KEY_PAGEDOWN": InputEvent(Action.CHANNEL_DOWN),
    # Volume - the DEDICATED keys, same reasoning.
    "KEY_VOLUMEUP": InputEvent(Action.VOLUME_UP),
    "KEY_EQUAL": InputEvent(Action.VOLUME_UP),
    "KEY_KPPLUS": InputEvent(Action.VOLUME_UP),
    "KEY_VOLUMEDOWN": InputEvent(Action.VOLUME_DOWN),
    "KEY_MINUS": InputEvent(Action.VOLUME_DOWN),
    "KEY_KPMINUS": InputEvent(Action.VOLUME_DOWN),
    "KEY_MUTE": InputEvent(Action.MUTE),
    # The D-pad. With the guide CLOSED these behave exactly as they always
    # have - up/down change channel, left/right change volume - because
    # app.py routes them there. With the guide open they move the cursor.
    "KEY_UP": InputEvent(Action.NAV_UP),
    "KEY_DOWN": InputEvent(Action.NAV_DOWN),
    "KEY_LEFT": InputEvent(Action.NAV_LEFT),
    "KEY_RIGHT": InputEvent(Action.NAV_RIGHT),
    # The channel guide.
    "KEY_HOME": InputEvent(Action.HOME),
    "KEY_HOMEPAGE": InputEvent(Action.HOME),
    "KEY_MENU": InputEvent(Action.HOME),
    # A Flirc reports as a USB keyboard, so a remote button taught the letter
    # `h` arrives here as KEY_H. Matches KEY_M / KEY_I / KEY_L / KEY_P below.
    "KEY_H": InputEvent(Action.HOME),
    "KEY_KPDOT": InputEvent(Action.RANDOM),
    # The remote's INPUT button, taught the letter `c`, steps the CRT effect
    # through its presets so the picture can be judged on the actual telly.
    "KEY_C": InputEvent(Action.CRT_CYCLE),
    # The remote's star button, taught the letter `b`: finish up, then bed.
    "KEY_B": InputEvent(Action.BEDTIME),
    "KEY_DOT": InputEvent(Action.RANDOM),
    "KEY_M": InputEvent(Action.MUTE),
    # Select / confirm a typed channel number.
    "KEY_ENTER": InputEvent(Action.ENTER),
    "KEY_KPENTER": InputEvent(Action.ENTER),
    "KEY_OK": InputEvent(Action.ENTER),
    "KEY_SELECT": InputEvent(Action.ENTER),
    "KEY_SPACE": InputEvent(Action.ENTER),
    # Info banner.
    "KEY_INFO": InputEvent(Action.INFO),
    "KEY_I": InputEvent(Action.INFO),
    # Jump to previous channel (the classic "last" / "back" button).
    "KEY_LAST": InputEvent(Action.LAST_CHANNEL),
    "KEY_PREVIOUS": InputEvent(Action.LAST_CHANNEL),
    "KEY_BACK": InputEvent(Action.LAST_CHANNEL),
    "KEY_L": InputEvent(Action.LAST_CHANNEL),
    # Power / standby.
    "KEY_POWER": InputEvent(Action.POWER),
    "KEY_SLEEP": InputEvent(Action.POWER),
    "KEY_P": InputEvent(Action.POWER),
    # Quit the application (mostly for keyboards during setup).
    "KEY_ESC": InputEvent(Action.QUIT),
    "KEY_Q": InputEvent(Action.QUIT),
}

# Digit keys (top row and numeric keypad) -> DIGIT events.
for _d in range(10):
    _EVDEV_ACTIONS[f"KEY_{_d}"] = InputEvent.digit(_d)
    _EVDEV_ACTIONS[f"KEY_KP{_d}"] = InputEvent.digit(_d)


def evdev_key_to_event(key_name: str) -> Optional[InputEvent]:
    """Map an evdev key name (e.g. ``KEY_VOLUMEUP``) to an InputEvent."""
    return _EVDEV_ACTIONS.get(key_name)


# Named actions usable in config `key_overrides` (maps a key -> one of these).
_ACTION_BY_NAME: Dict[str, InputEvent] = {
    "channel_up": InputEvent(Action.CHANNEL_UP),
    "nav_up": InputEvent(Action.NAV_UP),
    "nav_down": InputEvent(Action.NAV_DOWN),
    "nav_left": InputEvent(Action.NAV_LEFT),
    "nav_right": InputEvent(Action.NAV_RIGHT),
    "home": InputEvent(Action.HOME),
    "guide": InputEvent(Action.HOME),
    "random": InputEvent(Action.RANDOM),
    "crt_cycle": InputEvent(Action.CRT_CYCLE),
    "crt": InputEvent(Action.CRT_CYCLE),
    "bedtime": InputEvent(Action.BEDTIME),
    "channel_down": InputEvent(Action.CHANNEL_DOWN),
    "volume_up": InputEvent(Action.VOLUME_UP),
    "volume_down": InputEvent(Action.VOLUME_DOWN),
    "mute": InputEvent(Action.MUTE),
    "enter": InputEvent(Action.ENTER),
    "ok": InputEvent(Action.ENTER),
    "select": InputEvent(Action.ENTER),
    "info": InputEvent(Action.INFO),
    "last_channel": InputEvent(Action.LAST_CHANNEL),
    "last": InputEvent(Action.LAST_CHANNEL),
    "power": InputEvent(Action.POWER),
    "quit": InputEvent(Action.QUIT),
    "none": None,  # explicitly unbind a key
}


def action_names() -> tuple[str, ...]:
    return tuple(_ACTION_BY_NAME)


def parse_key_overrides(raw: object) -> Dict[str, Optional[InputEvent]]:
    """Turn a config ``{KEY_NAME: action_name}`` mapping into key -> InputEvent.

    Keys are normalised to evdev names (``f5`` / ``KEY_F5`` both work; a bare
    name gets the ``KEY_`` prefix). Digits use ``digit_0`` .. ``digit_9``.
    Unknown action names raise so typos are caught by ``--check``.
    """
    result: Dict[str, Optional[InputEvent]] = {}
    if not raw:
        return result
    if not isinstance(raw, dict):
        raise ValueError("'key_overrides' must be a mapping of KEY_NAME: action")
    for key, action in raw.items():
        kname = str(key).strip().upper()
        if not kname.startswith("KEY_"):
            kname = "KEY_" + kname
        aname = str(action).strip().lower()
        if aname.startswith("digit_") and aname[6:].isdigit():
            result[kname] = InputEvent.digit(int(aname[6:]))
            continue
        if aname not in _ACTION_BY_NAME:
            raise ValueError(
                f"unknown action '{action}' for key '{key}'. "
                f"Valid actions: {', '.join(_ACTION_BY_NAME)} (or digit_0..digit_9)"
            )
        result[kname] = _ACTION_BY_NAME[aname]
    return result


# --------------------------------------------------------------------------
# stdin characters -> evdev key names (so they reuse the map above)
# --------------------------------------------------------------------------
# Single printable characters typed at a terminal (dev/testing mode).
_CHAR_TO_KEY: Dict[str, str] = {
    "+": "KEY_VOLUMEUP",
    "=": "KEY_VOLUMEUP",
    "-": "KEY_VOLUMEDOWN",
    "_": "KEY_VOLUMEDOWN",
    "m": "KEY_MUTE",
    "M": "KEY_MUTE",
    "i": "KEY_INFO",
    "I": "KEY_INFO",
    "b": "KEY_B",
    "B": "KEY_B",
    "c": "KEY_C",
    "C": "KEY_C",
    "h": "KEY_HOME",
    "H": "KEY_HOME",
    ".": "KEY_KPDOT",
    "l": "KEY_LAST",
    "L": "KEY_LAST",
    "p": "KEY_POWER",
    "P": "KEY_POWER",
    "q": "KEY_Q",
    "Q": "KEY_Q",
    "\r": "KEY_ENTER",
    "\n": "KEY_ENTER",
    " ": "KEY_ENTER",
    "\x1b": "KEY_ESC",
}
for _d in range(10):
    _CHAR_TO_KEY[str(_d)] = f"KEY_{_d}"

# Terminal escape sequences for the arrow keys.
_ESCAPE_TO_KEY: Dict[str, str] = {
    "[A": "KEY_UP",
    "[B": "KEY_DOWN",
    "[C": "KEY_RIGHT",
    "[D": "KEY_LEFT",
}


def stdin_char_to_event(char: str) -> Optional[InputEvent]:
    key = _CHAR_TO_KEY.get(char)
    return evdev_key_to_event(key) if key else None


def stdin_escape_to_event(seq: str) -> Optional[InputEvent]:
    key = _ESCAPE_TO_KEY.get(seq)
    return evdev_key_to_event(key) if key else None


# --------------------------------------------------------------------------
# HDMI-CEC user-control names -> InputEvent
# --------------------------------------------------------------------------
# Names as emitted by libCEC / `cec-client` "key pressed:" lines.
_CEC_ACTIONS: Dict[str, InputEvent] = {
    # Same split as the evdev map: the TV remote's d-pad navigates, its
    # dedicated channel/volume keys always do channel and volume.
    "up": InputEvent(Action.NAV_UP),
    "down": InputEvent(Action.NAV_DOWN),
    "right": InputEvent(Action.NAV_RIGHT),
    "left": InputEvent(Action.NAV_LEFT),
    "channel up": InputEvent(Action.CHANNEL_UP),
    "channel down": InputEvent(Action.CHANNEL_DOWN),
    "volume up": InputEvent(Action.VOLUME_UP),
    "volume down": InputEvent(Action.VOLUME_DOWN),
    "root menu": InputEvent(Action.HOME),
    "contents menu": InputEvent(Action.HOME),
    "mute": InputEvent(Action.MUTE),
    "select": InputEvent(Action.ENTER),
    "ok": InputEvent(Action.ENTER),
    "enter": InputEvent(Action.ENTER),
    "info": InputEvent(Action.INFO),
    "electronic program guide": InputEvent(Action.INFO),
    "display information": InputEvent(Action.INFO),
    "previous channel": InputEvent(Action.LAST_CHANNEL),
    "exit": InputEvent(Action.LAST_CHANNEL),
    "power": InputEvent(Action.POWER),
    "power toggle function": InputEvent(Action.POWER),
    "power off function": InputEvent(Action.POWER),
}
for _d in range(10):
    _CEC_ACTIONS[f"number {_d}"] = InputEvent.digit(_d)
    _CEC_ACTIONS[str(_d)] = InputEvent.digit(_d)


def cec_key_to_event(name: str) -> Optional[InputEvent]:
    """Map a CEC user-control name to an InputEvent (case-insensitive)."""
    return _CEC_ACTIONS.get(name.strip().lower())


__all__ = [
    "evdev_key_to_event",
    "stdin_char_to_event",
    "stdin_escape_to_event",
    "cec_key_to_event",
    "parse_key_overrides",
    "action_names",
]
