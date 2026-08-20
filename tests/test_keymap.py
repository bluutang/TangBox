import pytest

from nostalgiabox.actions import Action
from nostalgiabox.input.keymap import (
    cec_key_to_event,
    evdev_key_to_event,
    parse_key_overrides,
    stdin_char_to_event,
    stdin_escape_to_event,
)


def test_evdev_channel_and_volume():
    assert evdev_key_to_event("KEY_CHANNELUP").action == Action.CHANNEL_UP
    assert evdev_key_to_event("KEY_PAGEUP").action == Action.CHANNEL_UP
    assert evdev_key_to_event("KEY_UP").action == Action.NAV_UP
    assert evdev_key_to_event("KEY_VOLUMEDOWN").action == Action.VOLUME_DOWN
    assert evdev_key_to_event("KEY_MUTE").action == Action.MUTE


def test_evdev_digits():
    ev = evdev_key_to_event("KEY_5")
    assert ev.action == Action.DIGIT and ev.value == 5
    ev = evdev_key_to_event("KEY_KP0")
    assert ev.action == Action.DIGIT and ev.value == 0


def test_evdev_power_and_last_letters():
    assert evdev_key_to_event("KEY_P").action == Action.POWER
    assert evdev_key_to_event("KEY_L").action == Action.LAST_CHANNEL
    assert evdev_key_to_event("KEY_POWER").action == Action.POWER


def test_evdev_unknown_key():
    assert evdev_key_to_event("KEY_FLIBBERTIGIBBET") is None


def test_stdin_chars():
    assert stdin_char_to_event("+").action == Action.VOLUME_UP
    assert stdin_char_to_event("-").action == Action.VOLUME_DOWN
    assert stdin_char_to_event("m").action == Action.MUTE
    assert stdin_char_to_event("q").action == Action.QUIT
    assert stdin_char_to_event("3").value == 3
    assert stdin_char_to_event("\r").action == Action.ENTER


def test_stdin_arrows():
    assert stdin_escape_to_event("[A").action == Action.NAV_UP
    assert stdin_escape_to_event("[B").action == Action.NAV_DOWN
    assert stdin_escape_to_event("[C").action == Action.NAV_RIGHT
    assert stdin_escape_to_event("[D").action == Action.NAV_LEFT
    assert stdin_escape_to_event("[Z") is None


def test_parse_key_overrides_basic():
    ov = parse_key_overrides({"KEY_F5": "volume_up", "KEY_DOT": "volume_down"})
    assert ov["KEY_F5"].action == Action.VOLUME_UP
    assert ov["KEY_DOT"].action == Action.VOLUME_DOWN


def test_parse_key_overrides_normalises_names():
    # bare names get the KEY_ prefix and are upper-cased
    ov = parse_key_overrides({"f5": "channel_up", "pageup": "channel_down"})
    assert ov["KEY_F5"].action == Action.CHANNEL_UP
    assert ov["KEY_PAGEUP"].action == Action.CHANNEL_DOWN


def test_parse_key_overrides_digit_and_none():
    ov = parse_key_overrides({"KEY_KP5": "digit_5", "KEY_ESC": "none"})
    assert ov["KEY_KP5"].value == 5
    assert ov["KEY_ESC"] is None  # explicitly unbound


def test_parse_key_overrides_rejects_bad_action():
    with pytest.raises(ValueError, match="unknown action"):
        parse_key_overrides({"KEY_F5": "explode"})


def test_parse_key_overrides_empty():
    assert parse_key_overrides(None) == {}
    assert parse_key_overrides({}) == {}


def test_keyboard_backend_override_precedence():
    from nostalgiabox.input.keyboard import KeyboardBackend

    ov = parse_key_overrides({"KEY_F5": "volume_up", "KEY_ESC": "none"})
    kb = KeyboardBackend(overrides=ov)
    assert kb._lookup("KEY_F5").action == Action.VOLUME_UP     # override applied
    assert kb._lookup("KEY_ESC") is None                       # explicitly unbound
    assert kb._lookup("KEY_VOLUMEUP").action == Action.VOLUME_UP  # default intact
    assert kb._lookup("KEY_PAGEUP").action == Action.CHANNEL_UP


def test_cec_keys():
    assert cec_key_to_event("channel up").action == Action.CHANNEL_UP
    assert cec_key_to_event("Volume Down").action == Action.VOLUME_DOWN
    assert cec_key_to_event("select").action == Action.ENTER
    assert cec_key_to_event("number 4").value == 4
    assert cec_key_to_event("power").action == Action.POWER
    assert cec_key_to_event("nonsense") is None


# --------------------------------------------------------------------------
# The d-pad is split from the dedicated channel/volume keys (channel guide)
# --------------------------------------------------------------------------
def test_the_dpad_produces_navigation_not_channel_changes():
    # Splitting these is what lets channel and volume keep working while the
    # guide is open. What the d-pad DOES with the guide closed is unchanged -
    # see tests/test_app.py.
    assert evdev_key_to_event("KEY_UP").action == Action.NAV_UP
    assert evdev_key_to_event("KEY_DOWN").action == Action.NAV_DOWN
    assert evdev_key_to_event("KEY_LEFT").action == Action.NAV_LEFT
    assert evdev_key_to_event("KEY_RIGHT").action == Action.NAV_RIGHT


def test_dedicated_channel_and_volume_keys_are_unaffected_by_the_split():
    # A remote with real CH+/- and VOL+/- buttons keeps working while the
    # guide is open, which is the whole point of separating them.
    assert evdev_key_to_event("KEY_CHANNELUP").action == Action.CHANNEL_UP
    assert evdev_key_to_event("KEY_CHANNELDOWN").action == Action.CHANNEL_DOWN
    assert evdev_key_to_event("KEY_VOLUMEUP").action == Action.VOLUME_UP
    assert evdev_key_to_event("KEY_VOLUMEDOWN").action == Action.VOLUME_DOWN


def test_home_opens_the_guide():
    assert evdev_key_to_event("KEY_HOME").action == Action.HOME
    assert evdev_key_to_event("KEY_HOMEPAGE").action == Action.HOME


def test_the_dot_key_picks_a_random_channel():
    # For a 2-year-old this may be the only control they ever need.
    assert evdev_key_to_event("KEY_KPDOT").action == Action.RANDOM


def test_the_new_actions_can_be_bound_by_hand_in_the_config():
    # Flirc lets any remote button send any keystroke, so key_overrides is how
    # the GE Big Button's spare keys get pointed at these.
    ov = parse_key_overrides({"f1": "home", "f2": "random", "f3": "nav_up"})
    assert ov["KEY_F1"].action == Action.HOME
    assert ov["KEY_F2"].action == Action.RANDOM
    assert ov["KEY_F3"].action == Action.NAV_UP


def test_the_cec_dpad_also_produces_navigation():
    # So the TV remote could drive the guide too, if cec is ever switched on.
    assert cec_key_to_event("up").action == Action.NAV_UP
    assert cec_key_to_event("left").action == Action.NAV_LEFT
    assert cec_key_to_event("channel up").action == Action.CHANNEL_UP
