"""The phosphor-glow blur has to be a dial, not a switch.

Brian saw the channel banner on a real 1080p television on 2026-08-19 and called
it blurry. It is: the overlay is drawn on a 1280x720 virtual canvas and stretched
to the screen, so a 4-pixel blur lands as 6. The same trap as the scanlines,
which had to drop from 0.12 to 0.03 for exactly this reason.

Tuning it needs eyes on a TV, so the code's job is to make trying values cheap.
"""

from __future__ import annotations

import re

from nostalgiabox.config import UiConfig, load_config
from nostalgiabox.overlay import _style


def blur_in(tags: str):
    """The \\blurN value present in an ASS tag string, or None."""
    m = re.search(r"\\blur([0-9.]+)", tags)
    return float(m.group(1)) if m else None


def test_glow_blur_defaults_to_the_current_look():
    """Changing this must not silently restyle the box for anyone."""
    assert blur_in(_style(UiConfig(), size=40)) == 4.0


def test_glow_blur_is_configurable():
    """The whole point: try a value without editing Python."""
    assert blur_in(_style(UiConfig(glow_blur=1.5), size=40)) == 1.5


def test_zero_blur_gives_crisp_text_but_keeps_the_green_edge():
    """glow_blur: 0 should sharpen the text, not turn the glow colour off.

    Distinct from `glow: false`, which drops back to a plain black outline.
    """
    tags = _style(UiConfig(glow_blur=0), size=40)
    assert blur_in(tags) in (None, 0.0)
    assert r"\bord2" in tags


def test_glow_false_still_wins_over_any_blur_value():
    tags = _style(UiConfig(glow=False, glow_blur=9), size=40)
    assert blur_in(tags) is None


def test_config_reads_glow_blur(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        "channels:\n"
        "  - number: 2\n"
        "    name: Test\n"
        f"    path: {tmp_path}\n"
        "ui:\n"
        "  glow: true\n"
        "  glow_blur: 2\n"
    )
    cfg = load_config(cfg_file)
    assert cfg.ui.glow_blur == 2


def test_negative_glow_blur_clamps_to_zero(tmp_path):
    """Clamped, not rejected - matching every other numeric setting here.

    A typo in a config file should never stop the TV coming on.
    """
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        "channels:\n"
        "  - number: 2\n"
        "    name: Test\n"
        f"    path: {tmp_path}\n"
        "ui:\n"
        "  glow_blur: -1\n"
    )
    assert load_config(cfg_file).ui.glow_blur == 0.0


def test_nonsense_glow_blur_is_rejected(tmp_path):
    """A value that isn't a number at all is a real mistake, so say so."""
    import pytest

    from nostalgiabox.config import ConfigError

    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        "channels:\n"
        "  - number: 2\n"
        "    name: Test\n"
        f"    path: {tmp_path}\n"
        "ui:\n"
        "  glow_blur: soft\n"
    )
    with pytest.raises(ConfigError):
        load_config(cfg_file)
