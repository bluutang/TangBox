"""Telling mpv which display mode to use.

The Pi drove this TV at 3840x2160@30 no matter what the kernel was told. The
boot parameter WAS working - proven by stopping TangBox, at which point the
display fell straight back to the pinned 1920x1080@60. mpv was overriding it:
it does its own mode-setting when it takes the screen, and defaults to the
connector's *preferred* mode, which this television advertises as 4K30.

For a box showing 480-line cartoons that is a bad trade - no detail to gain from
a source that never had it, half the refresh rate, and the 1280x720 overlay
canvas stretched 3x instead of 1.5x, which is why the HUD text stayed soft
through every change to its weight, spacing and glow.
"""

from __future__ import annotations

import pytest

from nostalgiabox.config import ConfigError, config_from_dict
from tests.helpers import make_show


def cfg(tmp_path, **over):
    make_show(tmp_path, "dragon", 1)
    data = {
        "channels": [
            {"number": 2, "name": "D", "path": str(tmp_path / "dragon")}
        ]
    }
    data.update(over)
    return config_from_dict(data)


def test_no_display_mode_by_default(tmp_path):
    """Unset means "let mpv pick", which is every existing install's behaviour."""
    assert cfg(tmp_path).display_mode is None


def test_display_mode_is_read(tmp_path):
    assert cfg(tmp_path, display_mode="1920x1080@60").display_mode == "1920x1080@60"


def test_preferred_and_highest_are_allowed(tmp_path):
    """mpv's own keywords, worth passing through rather than rejecting."""
    assert cfg(tmp_path, display_mode="preferred").display_mode == "preferred"
    assert cfg(tmp_path, display_mode="highest").display_mode == "highest"


def test_a_nonsense_mode_is_rejected(tmp_path):
    """mpv silently ignores a mode it cannot parse, which looks like no effect."""
    with pytest.raises(ConfigError):
        cfg(tmp_path, display_mode="enormous")


def test_the_player_receives_it(tmp_path):
    """The whole point: it has to reach mpv as drm-mode."""
    from nostalgiabox.player import build_mpv_options

    opts = build_mpv_options(display_mode="1920x1080@60")
    assert opts.get("drm_mode") == "1920x1080@60"


def test_the_player_omits_it_when_unset(tmp_path):
    from nostalgiabox.player import build_mpv_options

    assert "drm_mode" not in build_mpv_options(display_mode=None)
