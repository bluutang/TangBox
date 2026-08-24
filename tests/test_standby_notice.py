"""Whether anything is drawn once the box has gone quiet.

The sign-off ends with the orange collapsing to a dot and winking out. Putting
a green STANDBY card up immediately afterwards undoes that - the last thing on
screen becomes a word, and on this box the television is switching itself off
anyway, so nobody is there to read it.

Off is a real option, not the default: a box whose screen simply goes black is
indistinguishable from one that has crashed, and that is a fair thing to want
to see on a setup where the television stays on.
"""

from nostalgiabox.actions import Action, InputEvent
from nostalgiabox.app import TVApp
from nostalgiabox.config import config_from_dict
from nostalgiabox.input.manager import InputManager
from nostalgiabox.player import MockPlayer
from tests.helpers import FakeClock, make_show

_ID_STANDBY = 3


def build(tmp_path, **overrides):
    make_show(tmp_path, "dragon", 3)
    data = {
        "shuffle_seed": 7,
        "start_channel": 2,
        "start_offset": 0,
        "initial_volume": 5,
        "channels": [
            {"number": 2, "name": "Dragon Tales", "path": str(tmp_path / "dragon")}
        ],
    }
    data.update(overrides)
    app = TVApp(
        config_from_dict(data), MockPlayer(), InputManager([]),
        clock=FakeClock(), sleep=lambda _s: None,
    )
    return app, app.player


def sleep(app):
    app.handle_event(InputEvent(Action.POWER))


def test_the_notice_can_be_turned_off(tmp_path):
    app, player = build(tmp_path, standby_notice=False)
    app.start()
    sleep(app)
    assert app.standby is True
    assert _ID_STANDBY not in player.overlays


def test_it_is_drawn_by_default(tmp_path):
    app, player = build(tmp_path)
    app.start()
    sleep(app)
    assert _ID_STANDBY in player.overlays


def test_waking_still_works_without_a_notice(tmp_path):
    app, player = build(tmp_path, standby_notice=False)
    app.start()
    app._finish_sign_on()
    sleep(app)
    app.handle_event(InputEvent(Action.POWER))
    assert app.standby is False
    assert _ID_STANDBY not in player.overlays
