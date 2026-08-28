import re

from nostalgiabox.config import config_from_dict
from nostalgiabox.overlay import OverlayManager, _filled_rect
from nostalgiabox.player import MockPlayer
from tests.helpers import FakeClock, make_show

# The 4:3 frame within the 1280x720 canvas spans x in [160, 1120].
_FRAME_X0, _FRAME_X1 = 160, 1120


def _all_x_positions(ass: str):
    return [int(m) for m in re.findall(r"\\pos\((\d+),", ass)]


def _config(tmp_path):
    make_show(tmp_path, "a", 1)
    return config_from_dict(
        {
            "channel_bug_seconds": 4,
            "osd_duration": 2,
            "channels": [{"number": 3, "name": "Arthur", "path": str(tmp_path / "a")}],
        }
    )


def test_channel_bug_drawn_and_expires(tmp_path):
    clock = FakeClock()
    player = MockPlayer()
    om = OverlayManager(player, _config(tmp_path), clock=clock)

    om.show_channel_bug(3, "Arthur")
    assert 1 in player.overlays  # channel overlay id
    ass = player.overlays[1]
    assert "CH 03" in ass and "Arthur" in ass

    clock.advance(3.9)
    om.tick()
    assert 1 in player.overlays  # not yet expired

    clock.advance(0.2)
    om.tick()
    assert 1 not in player.overlays  # expired after 4s


def test_volume_overlay_has_label_and_bars(tmp_path):
    player = MockPlayer()
    om = OverlayManager(player, _config(tmp_path), clock=FakeClock())
    om.show_volume(45, muted=False)
    ass = player.overlays[2]
    assert "Volume" in ass
    # 20 segments: some drawn as bars (rectangles start "m 0 0 l"), rest as dots.
    assert ass.count("\\p1") == 20


def test_volume_bars_scale_with_level(tmp_path):
    player = MockPlayer()
    om = OverlayManager(player, _config(tmp_path), clock=FakeClock())
    om.show_volume(100, muted=False)
    full = player.overlays[2].count("m 0 0 l")  # rectangle (filled bar) count
    om.show_volume(0, muted=False)
    empty = player.overlays[2].count("m 0 0 l")
    assert full == 20 and empty == 0


def test_muted_volume_overlay(tmp_path):
    player = MockPlayer()
    om = OverlayManager(player, _config(tmp_path), clock=FakeClock())
    om.show_volume(45, muted=True)
    assert "Mute" in player.overlays[2]


def test_standby_overlay_does_not_expire(tmp_path):
    clock = FakeClock()
    player = MockPlayer()
    om = OverlayManager(player, _config(tmp_path), clock=clock)
    om.show_standby()
    clock.advance(1000)
    om.tick()
    assert 3 in player.overlays  # standby id persists
    om.clear_standby()
    assert 3 not in player.overlays


def test_channel_name_with_braces_is_escaped(tmp_path):
    player = MockPlayer()
    om = OverlayManager(player, _config(tmp_path), clock=FakeClock())
    om.show_channel_bug(5, "Weird{name}")
    # Braces in the name must be neutralised (they delimit ASS override blocks).
    ass = player.overlays[1]
    assert "Weird(name)" in ass
    assert "Weird{name}" not in ass


def test_message_overlay(tmp_path):
    player = MockPlayer()
    om = OverlayManager(player, _config(tmp_path), clock=FakeClock())
    om.show_message("CH 12  -  NO CHANNEL")
    assert "NO CHANNEL" in player.overlays[4]


def test_channel_bug_sits_inside_4x3_frame(tmp_path):
    player = MockPlayer()
    om = OverlayManager(player, _config(tmp_path), clock=FakeClock())
    om.show_channel_bug(3, "Arthur")
    xs = _all_x_positions(player.overlays[1])
    assert xs and all(_FRAME_X0 <= x <= _FRAME_X1 for x in xs)


def test_volume_bar_sits_inside_4x3_frame(tmp_path):
    player = MockPlayer()
    om = OverlayManager(player, _config(tmp_path), clock=FakeClock())
    om.show_volume(100, muted=False)  # widest case: all 20 bars drawn
    xs = _all_x_positions(player.overlays[2])
    assert xs and all(_FRAME_X0 <= x <= _FRAME_X1 for x in xs)


def test_overlay_uses_configured_font_and_color(tmp_path):
    player = MockPlayer()
    om = OverlayManager(player, _config(tmp_path), clock=FakeClock())
    om.show_channel_bug(3, "Arthur")
    ass = player.overlays[1]
    assert "\\fnVT323" in ass          # bundled retro font
    assert "&H005AFF4D" in ass         # #4DFF5A -> ASS BBGGRR


# --------------------------------------------------------------------------
# Transparency on the rectangle helper (the channel guide's dimming scrim)
# --------------------------------------------------------------------------
def test_a_rectangle_is_solid_by_default():
    # ASS alpha is inverted: 00 is fully opaque.
    ass = _filled_rect(x=0, y=0, w=10, h=10, fill="&H00FFFFFF")
    assert r"\1a&H00&" in ass


def test_a_rectangle_can_be_drawn_part_transparent():
    # The guide dims the picture behind it rather than hiding it - the
    # programme keeps playing underneath.
    ass = _filled_rect(x=0, y=0, w=10, h=10, fill="&H00000000", alpha=87)
    assert r"\1a&H57&" in ass


# --------------------------------------------------------------------------
# The channel guide's overlay slot
# --------------------------------------------------------------------------
def test_the_guide_is_drawn_in_its_own_slot(tmp_path):
    # Its own id, so showing the guide never disturbs the channel banner or
    # the volume bar and can be cleared on its own.
    player = MockPlayer()
    om = OverlayManager(player, _config(tmp_path), clock=FakeClock())

    om.show_channel_bug(3, "Arthur")
    om.show_guide("SOME GUIDE ASS")

    assert player.overlays[5] == "SOME GUIDE ASS"
    assert 1 in player.overlays, "showing the guide wiped the channel banner"


def test_the_guide_does_not_time_itself_out_of_the_overlay(tmp_path):
    # The Guide object owns the auto-close timer and closes deliberately. If
    # the overlay expired on its own the guide would go invisible while still
    # swallowing every button press - a properly stuck television.
    clock = FakeClock()
    player = MockPlayer()
    om = OverlayManager(player, _config(tmp_path), clock=clock)

    om.show_guide("SOME GUIDE ASS")
    clock.advance(10_000)
    om.tick()

    assert 5 in player.overlays


def test_clearing_the_guide_removes_it(tmp_path):
    player = MockPlayer()
    om = OverlayManager(player, _config(tmp_path), clock=FakeClock())
    om.show_guide("SOME GUIDE ASS")
    om.clear_guide()
    assert 5 not in player.overlays


def test_clear_all_takes_the_guide_with_it(tmp_path):
    player = MockPlayer()
    om = OverlayManager(player, _config(tmp_path), clock=FakeClock())
    om.show_guide("SOME GUIDE ASS")
    om.clear_all()
    assert 5 not in player.overlays


def test_channel_age_range_is_parsed(tmp_path):
    """A channel can declare who it is for, e.g. "2-4" or "7+"."""
    make_show(tmp_path, "a", 1)
    cfg = config_from_dict(
        {
            "channels": [
                {"number": 3, "name": "Arthur", "path": str(tmp_path / "a"), "age": "4-8"}
            ]
        }
    )
    assert cfg.channels[0].age == "4-8"


def test_channel_age_range_absent_is_none(tmp_path):
    """Channels that do not declare an age are unchanged."""
    make_show(tmp_path, "a", 1)
    cfg = config_from_dict(
        {"channels": [{"number": 3, "name": "Arthur", "path": str(tmp_path / "a")}]}
    )
    assert cfg.channels[0].age is None


def test_channel_bug_shows_age_range(tmp_path):
    """The age range appears on the banner when the channel declares one."""
    clock = FakeClock()
    player = MockPlayer()
    om = OverlayManager(player, _config(tmp_path), clock=clock)

    om.show_channel_bug(3, "Arthur", age="4-8")
    ass = player.overlays[1]
    assert "4-8" in ass


def test_channel_bug_without_age_has_no_stray_text(tmp_path):
    """No age means no extra line - a blank gap reads as a fault."""
    clock = FakeClock()
    player = MockPlayer()
    om = OverlayManager(player, _config(tmp_path), clock=clock)

    om.show_channel_bug(3, "Arthur")
    ass = player.overlays[1]
    assert "CH 03" in ass and "Arthur" in ass
    assert "AGE" not in ass.upper()
