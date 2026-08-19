"""Signing off: the CRT collapse before the Pi halts.

The mirror of the sign-on. Everyone who grew up with a CRT knows this one - the
picture collapses to a line, the line to a dot, the dot winks out.

The important constraint is that this sits in front of an actual shutdown. It
must never be able to PREVENT one: a clip that fails to play, or an asset that
is missing, has to fall straight through to halting the machine. A telly that
will not switch off is worse than one that switches off without ceremony.
"""

from __future__ import annotations

from typing import List

from nostalgiabox.actions import Action, InputEvent
from nostalgiabox.app import TVApp
from nostalgiabox.config import config_from_dict
from nostalgiabox.input.manager import InputManager
from nostalgiabox.player import MockPlayer
from tests.helpers import FakeClock, make_show


def build(tmp_path, *, assets=("power_off.mp4",), **overrides):
    make_show(tmp_path, "dragon", 3)
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir(exist_ok=True)
    for name in assets:
        (assets_dir / name).write_bytes(b"\x00")

    slept: List[float] = []
    data = {
        "shuffle_seed": 7,
        "start_channel": 2,
        "start_offset": 0,
        "initial_volume": 0,
        "power_off_on_min_volume": True,
        "power_off_command": ["/bin/true"],
        "channels": [
            {"number": 2, "name": "Dragon Tales", "path": str(tmp_path / "dragon")}
        ],
    }
    data.update(overrides)
    app = TVApp(
        config_from_dict(data),
        MockPlayer(),
        InputManager([]),
        clock=FakeClock(),
        assets_dir=assets_dir,
        sleep=slept.append,
    )
    return app, app.player, slept, assets_dir


def power_off(app):
    """Volume-down at zero is the only route to a real shutdown."""
    app.handle_event(InputEvent(Action.VOLUME_DOWN))


def played_names(player):
    return [p.name for p, _ in player.played]


def test_the_collapse_plays_before_the_machine_halts(tmp_path):
    app, player, _, _ = build(tmp_path)
    app.start()
    power_off(app)
    assert "power_off.mp4" in played_names(player)


def test_it_waits_for_the_clip_before_halting(tmp_path):
    """Fire the poweroff command instantly and nobody ever sees the animation."""
    app, _, slept, _ = build(tmp_path)
    app.start()
    power_off(app)
    assert slept, "did not wait for the sign-off clip"
    assert 0.2 < sum(slept) < 3.0, f"waited {sum(slept)}s - should be about a second"


def test_the_box_still_halts(tmp_path):
    app, _, _, _ = build(tmp_path)
    app.start()
    power_off(app)
    assert app.powered_off is True
    assert app._running is False


def test_a_missing_asset_does_not_prevent_shutdown(tmp_path):
    """The whole point: ceremony must never block the actual halt."""
    app, player, slept, _ = build(tmp_path, assets=())
    app.start()
    power_off(app)
    assert app.powered_off is True
    assert app._running is False
    assert not slept, "waited for a clip that does not exist"


def test_a_player_that_throws_does_not_prevent_shutdown(tmp_path):
    app, player, _, _ = build(tmp_path)
    app.start()

    def boom(*a, **k):
        raise RuntimeError("mpv fell over")

    player.play = boom
    power_off(app)
    assert app.powered_off is True
    assert app._running is False


def test_the_poweroff_command_still_runs(tmp_path):
    ran = []
    app, _, _, _ = build(tmp_path)
    app.start()
    app._run_power_off_command = lambda: ran.append(True)
    power_off(app)
    assert ran == [True], "the machine was never actually told to halt"
