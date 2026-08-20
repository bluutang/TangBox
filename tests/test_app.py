import re

import pytest

from nostalgiabox.actions import Action, InputEvent
from nostalgiabox.app import TVApp
from nostalgiabox.config import config_from_dict
from nostalgiabox.input.manager import InputManager
from nostalgiabox.player import END_EOF, MockPlayer
from tests.helpers import FakeClock, make_show


def build_app(tmp_path, *, assets_dir=None, **overrides):
    for name in ("dragon", "arthur", "rugrats"):
        make_show(tmp_path, name, 4)
    data = {
        "shuffle_seed": 7,
        "start_channel": 2,
        "start_offset": 0,  # keep test assertions on start=0 unless overridden
        "power_off_command": [],  # no-op in tests (never actually shut down)
        "channels": [
            {"number": 2, "name": "Dragon Tales", "path": str(tmp_path / "dragon")},
            {"number": 3, "name": "Arthur", "path": str(tmp_path / "arthur")},
            {"number": 4, "name": "Rugrats", "path": str(tmp_path / "rugrats")},
        ],
    }
    data.update(overrides)
    config = config_from_dict(data)
    clock = FakeClock()
    player = MockPlayer()
    app = TVApp(
        config,
        player,
        InputManager([]),
        clock=clock,
        assets_dir=assets_dir,
    )
    return app, player, clock


def send(app, action, value=None):
    app.handle_event(InputEvent(action, value))


def test_start_tunes_to_start_channel_and_plays(tmp_path):
    app, player, _ = build_app(tmp_path)
    app.start()
    assert app.lineup.current.number == 2
    assert player.current is not None  # an episode is playing
    assert player.volume == 70
    assert player.overlays.get(1) and "Dragon Tales" in player.overlays[1]


def test_channel_up_down_wraps(tmp_path):
    app, player, _ = build_app(tmp_path)
    app.start()
    send(app, Action.CHANNEL_UP)
    assert app.lineup.current.number == 3
    send(app, Action.CHANNEL_UP)
    assert app.lineup.current.number == 4
    send(app, Action.CHANNEL_UP)
    assert app.lineup.current.number == 2  # wrapped
    send(app, Action.CHANNEL_DOWN)
    assert app.lineup.current.number == 4  # wrapped back


def test_volume_controls(tmp_path):
    app, player, _ = build_app(tmp_path)
    app.start()
    send(app, Action.VOLUME_UP)
    assert app.volume == 75 and player.volume == 75
    send(app, Action.VOLUME_DOWN)
    assert app.volume == 70
    # volume overlay was drawn
    assert "Volume" in player.overlays[2]


def test_volume_clamps(tmp_path):
    app, player, _ = build_app(tmp_path, initial_volume=98, volume_step=5)
    app.start()
    send(app, Action.VOLUME_UP)
    assert app.volume == 100
    for _ in range(30):
        send(app, Action.VOLUME_DOWN)
    assert app.volume == 0


def test_volume_down_at_zero_powers_off(tmp_path):
    app, player, _ = build_app(tmp_path, initial_volume=10, volume_step=5)
    app.start()
    send(app, Action.VOLUME_DOWN)   # 10 -> 5
    send(app, Action.VOLUME_DOWN)   # 5 -> 0
    assert app.volume == 0 and not app.powered_off
    send(app, Action.VOLUME_DOWN)   # one more at 0 -> power off
    assert app.powered_off is True
    assert app._running is False
    assert player.current is None   # playback stopped


def test_power_off_disabled(tmp_path):
    app, player, _ = build_app(
        tmp_path, initial_volume=0, power_off_on_min_volume=False
    )
    app.start()
    send(app, Action.VOLUME_DOWN)   # at 0, but feature disabled
    assert app.powered_off is False


def test_mute_toggle_and_unmute_on_volume(tmp_path):
    app, player, _ = build_app(tmp_path)
    app.start()
    send(app, Action.MUTE)
    assert app.muted and player.muted
    send(app, Action.VOLUME_UP)  # changing volume unmutes
    assert not app.muted and not player.muted


def build_double_digit_app(tmp_path, **overrides):
    """A lineup where some numbers are prefixes of others: 1, 2, 12, 14.

    Typing "1" here is genuinely ambiguous - it could still become 12 or 14 -
    which is the only situation where the box should wait.
    """
    channels = []
    for n in (1, 2, 12, 14):
        make_show(tmp_path, f"show{n}", 3)
        channels.append(
            {"number": n, "name": f"Channel {n}", "path": str(tmp_path / f"show{n}")}
        )
    overrides.setdefault("channels", channels)
    overrides.setdefault("start_channel", 2)
    return build_app(tmp_path, **overrides)


def test_direct_channel_entry_with_enter(tmp_path):
    # OK confirms an entry that is still ambiguous, without waiting it out.
    app, _, _ = build_double_digit_app(tmp_path)
    app.start()
    send(app, Action.DIGIT, 1)
    assert app.lineup.current.number == 2  # could still become 12 or 14
    send(app, Action.ENTER)
    assert app.lineup.current.number == 1


def test_direct_channel_entry_times_out(tmp_path):
    # The timeout is the fallback for an entry that COULD have grown but
    # didn't, which is the only case still waiting on the clock.
    app, _, clock = build_double_digit_app(tmp_path)
    app.start()
    send(app, Action.DIGIT, 1)
    assert app.lineup.current.number == 2
    clock.advance(2.1)  # past the entry timeout
    app.step()
    assert app.lineup.current.number == 1


# -- tuning by number, once the number pad is the main way around ------------
def test_a_digit_that_can_only_mean_one_channel_tunes_immediately(tmp_path):
    # No channel starts with 4 except 4 itself, so there is nothing to wait
    # for. Waiting anyway is a two-second pause in front of a child who will
    # assume it did not work and press it again.
    app, _, _ = build_app(tmp_path)
    app.start()
    send(app, Action.DIGIT, 4)
    assert app.lineup.current.number == 4


def test_an_ambiguous_digit_still_waits_for_a_second_one(tmp_path):
    app, _, _ = build_double_digit_app(tmp_path)
    app.start()
    send(app, Action.DIGIT, 1)
    assert app.lineup.current.number == 2, "tuned to 1 before 12 was ruled out"


def test_completing_a_double_digit_channel_tunes_immediately(tmp_path):
    # "12" cannot grow into anything else, so it should not wait either.
    app, _, _ = build_double_digit_app(tmp_path)
    app.start()
    send(app, Action.DIGIT, 1)
    send(app, Action.DIGIT, 2)
    assert app.lineup.current.number == 12


def test_a_digit_matching_no_channel_at_all_says_so_immediately(tmp_path):
    # Nothing starts with 9, so the answer is already known.
    app, player, _ = build_app(tmp_path)
    app.start()
    send(app, Action.DIGIT, 9)
    assert app.lineup.current.number == 2
    assert "NO CHANNEL" in player.overlays.get(4, "")


def test_a_single_digit_channel_that_is_a_prefix_still_waits(tmp_path):
    # Channel 1 exists AND 12/14 exist. Tuning to 1 instantly would make
    # channels 12 and 14 unreachable from the number pad.
    app, _, clock = build_double_digit_app(tmp_path)
    app.start()
    send(app, Action.DIGIT, 1)
    send(app, Action.DIGIT, 4)
    assert app.lineup.current.number == 14


def test_invalid_channel_entry_shows_message(tmp_path):
    app, player, _ = build_app(tmp_path)
    app.start()
    assert app.select_channel_number(99) is False
    assert "NO CHANNEL" in player.overlays.get(4, "")
    assert app.lineup.current.number == 2  # unchanged


def test_last_channel_jump(tmp_path):
    app, player, _ = build_app(tmp_path)
    app.start()
    send(app, Action.CHANNEL_UP)  # now on 3, last=2
    assert app.lineup.current.number == 3
    send(app, Action.LAST_CHANNEL)
    assert app.lineup.current.number == 2
    send(app, Action.LAST_CHANNEL)  # bounces back to 3
    assert app.lineup.current.number == 3


def test_episode_advances_on_end(tmp_path):
    app, player, _ = build_app(tmp_path)
    app.start()
    first = player.current
    player.finish_current(END_EOF)  # simulate the episode ending
    app._drain_playback_events()
    assert player.current is not None
    assert player.current != first  # rolled into the next shuffled episode


def test_standby_blanks_and_ignores_input(tmp_path):
    app, player, _ = build_app(tmp_path)
    app.start()
    send(app, Action.POWER)
    assert app.standby
    assert player.current is None  # screen blanked
    assert 3 in player.overlays  # standby overlay
    # input is ignored while in standby
    send(app, Action.CHANNEL_UP)
    assert app.lineup.current.number == 2
    # power again wakes it up and resumes playback
    send(app, Action.POWER)
    assert not app.standby
    assert player.current is not None


def test_quit_stops_running(tmp_path):
    app, player, _ = build_app(tmp_path)
    app.start()
    app._running = True
    send(app, Action.QUIT)
    assert app._running is False


def test_glitch_transition_then_episode(tmp_path):
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "glitch.mp4").write_bytes(b"\x00")
    app, player, clock = build_app(tmp_path, assets_dir=assets, transition="glitch")
    app.start()
    send(app, Action.CHANNEL_UP)
    # A glitch->episode transition was issued (glitch clip + preloaded episode).
    assert player.transitions, "expected a transition on channel change"
    clip, target, _start = player.transitions[-1]
    assert clip == assets / "glitch.mp4"
    assert player.current == target  # the episode is what plays


def test_transition_none_cuts_straight(tmp_path):
    # bridge_seconds=0 -> switch immediately, no transition clip, no preload
    app, player, _ = build_app(tmp_path, transition="none", bridge_seconds=0)
    app.start()
    first = player.current
    send(app, Action.CHANNEL_UP)
    assert not player.transitions
    assert player.preloaded is None
    assert player.current is not None and player.current != first


def test_channel_change_bridges_current_until_next_ready(tmp_path):
    # With bridge_seconds>0 and no transition, the current show keeps playing
    # while the next channel preloads, then cuts over after the window.
    app, player, clock = build_app(tmp_path, bridge_seconds=0.8)
    app.start()
    first = player.current
    send(app, Action.CHANNEL_UP)
    assert player.current == first          # old show still playing...
    assert player.preloaded is not None     # ...next channel preloading
    clock.advance(1.0)
    app.step()                              # bridge window elapsed -> switch
    assert player.preloaded is None
    assert player.current is not None and player.current != first


def test_advance_within_channel_has_no_transition(tmp_path):
    # An episode ending should roll straight into the next one (no glitch burst).
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "glitch.mp4").write_bytes(b"\x00")
    app, player, _ = build_app(tmp_path, assets_dir=assets, transition="glitch")
    app.start()
    before = len(player.transitions)
    player.finish_current(END_EOF)
    app._drain_playback_events()
    assert len(player.transitions) == before  # no new transition
    assert player.current is not None


def test_start_offset_applied(tmp_path):
    app, player, _ = build_app(tmp_path, start_offset=5)
    app.start()
    # The episode should begin 5 seconds in, not at the very beginning.
    assert player.played[-1][1] == 5.0


def test_start_offset_range_applied(tmp_path):
    app, player, _ = build_app(tmp_path, start_offset=[6, 10])
    app.start()
    assert 6.0 <= player.played[-1][1] <= 10.0


def test_empty_channel_shows_no_signal(tmp_path):
    (tmp_path / "dragon").mkdir()
    make_show(tmp_path, "arthur", 2)
    config = config_from_dict(
        {
            "channels": [
                {"number": 2, "name": "Dragon Tales", "path": str(tmp_path / "dragon")},
                {"number": 3, "name": "Arthur", "path": str(tmp_path / "arthur")},
            ]
        }
    )
    app = TVApp(config, MockPlayer(), InputManager([]), clock=FakeClock())
    app.start()  # starts on ch 2 which is empty
    assert "NO SIGNAL" in app.player.overlays.get(4, "")


def test_channel_banner_deferred_until_switch(tmp_path):
    app, player, clock = build_app(tmp_path, bridge_seconds=0.8)
    app.start()
    player.overlays.pop(1, None)          # clear the power-on banner
    send(app, Action.CHANNEL_UP)
    assert 1 not in player.overlays       # banner NOT shown during the bridge
    clock.advance(1.0)
    app.step()                            # cut-over happens here
    assert "CH 03" in player.overlays.get(1, "")  # banner appears at the switch


def test_resume_mode_restarts_where_left(tmp_path):
    # bridge_seconds=0 keeps this test focused on resume (immediate switches)
    app, player, _ = build_app(tmp_path, tune_in="resume", bridge_seconds=0)
    app.start()
    playing = player.current
    player.time_pos = 42.0
    send(app, Action.CHANNEL_UP)  # leave ch 2, remembering position 42
    send(app, Action.CHANNEL_DOWN)  # back to ch 2 -> resume at 42
    assert player.current == playing
    assert player.played[-1] == (playing, 42.0)


# ==========================================================================
# The channel guide
# ==========================================================================
# build_app gives three channels - 2, 3 and 4 - which grid_shape lays out as
#     0 (ch2)  1 (ch3)
#     2 (ch4)
# and the box starts on channel 2, so the cursor starts at index 0.


# -- with the guide CLOSED, nothing about the box has changed ---------------
def test_the_dpad_still_changes_channel_when_the_guide_is_closed(tmp_path):
    # The d-pad now emits NAV_UP instead of CHANNEL_UP. This asserts the two
    # are indistinguishable to anyone watching television, which is the whole
    # safety condition on splitting them.
    a, _, _ = build_app(tmp_path)
    a.start()
    send(a, Action.NAV_UP)

    b, _, _ = build_app(tmp_path)
    b.start()
    send(b, Action.CHANNEL_UP)

    assert a.lineup.current.number == b.lineup.current.number


def test_the_dpad_still_changes_channel_downwards_when_the_guide_is_closed(tmp_path):
    a, _, _ = build_app(tmp_path)
    a.start()
    send(a, Action.NAV_DOWN)

    b, _, _ = build_app(tmp_path)
    b.start()
    send(b, Action.CHANNEL_DOWN)

    assert a.lineup.current.number == b.lineup.current.number


def test_the_dpad_still_changes_volume_when_the_guide_is_closed(tmp_path):
    a, _, _ = build_app(tmp_path)
    a.start()
    send(a, Action.NAV_RIGHT)
    send(a, Action.NAV_LEFT)
    send(a, Action.NAV_LEFT)

    b, _, _ = build_app(tmp_path)
    b.start()
    send(b, Action.VOLUME_UP)
    send(b, Action.VOLUME_DOWN)
    send(b, Action.VOLUME_DOWN)

    assert a.volume == b.volume


# -- opening and closing ----------------------------------------------------
def test_home_opens_the_guide_with_the_cursor_on_what_is_playing(tmp_path):
    # Home then OK must always mean "never mind".
    app, player, _ = build_app(tmp_path)
    app.start()
    send(app, Action.HOME)

    assert app.guide.is_open
    assert app.lineup.numbers[app.guide.cursor] == app.lineup.current.number
    assert 5 in player.overlays, "the guide was not drawn"


def test_home_again_closes_the_guide(tmp_path):
    app, player, _ = build_app(tmp_path)
    app.start()
    send(app, Action.HOME)
    send(app, Action.HOME)

    assert not app.guide.is_open
    assert 5 not in player.overlays


def test_ok_opens_the_guide_too(tmp_path):
    # So the box still works on a remote with no Home button at all.
    app, _, _ = build_app(tmp_path)
    app.start()
    send(app, Action.ENTER)
    assert app.guide.is_open


def test_ok_confirms_a_pending_channel_entry_instead_of_opening_the_guide(tmp_path):
    # Needs an entry that is actually still pending: an unambiguous digit now
    # tunes on its own, so by the time OK arrived there would be nothing left
    # to confirm and it would - correctly - open the guide.
    app, _, _ = build_double_digit_app(tmp_path)
    app.start()
    send(app, Action.DIGIT, 1)
    send(app, Action.ENTER)

    assert app.lineup.current.number == 1
    assert not app.guide.is_open


def test_ok_opens_the_guide_once_a_typed_channel_has_already_tuned(tmp_path):
    # The other half of the same rule: nothing pending, so OK means "guide".
    app, _, _ = build_app(tmp_path)
    app.start()
    send(app, Action.DIGIT, 4)
    assert app.lineup.current.number == 4
    send(app, Action.ENTER)
    assert app.guide.is_open


def test_back_closes_the_guide_without_changing_channel(tmp_path):
    app, _, _ = build_app(tmp_path)
    app.start()
    before = app.lineup.current.number
    send(app, Action.HOME)
    send(app, Action.NAV_RIGHT)
    send(app, Action.LAST_CHANNEL)

    assert not app.guide.is_open
    assert app.lineup.current.number == before


# -- moving around ----------------------------------------------------------
def test_the_dpad_moves_the_cursor_instead_of_changing_channel_when_open(tmp_path):
    app, _, _ = build_app(tmp_path)
    app.start()
    before = app.lineup.current.number
    send(app, Action.HOME)
    send(app, Action.NAV_RIGHT)

    assert app.guide.cursor == 1
    assert app.lineup.current.number == before, "the channel changed underneath"


def test_moving_the_cursor_redraws_the_guide(tmp_path):
    app, player, _ = build_app(tmp_path)
    app.start()
    send(app, Action.HOME)
    first = player.overlays[5]
    send(app, Action.NAV_RIGHT)

    assert player.overlays[5] != first


def test_the_dedicated_channel_buttons_still_change_channel_while_the_guide_is_open(tmp_path):
    # This is what splitting the d-pad bought.
    app, _, _ = build_app(tmp_path)
    app.start()
    before = app.lineup.current.number
    send(app, Action.HOME)
    send(app, Action.CHANNEL_UP)

    assert app.lineup.current.number != before
    assert app.guide.is_open, "changing channel should not close the guide"


def test_the_dedicated_volume_buttons_still_work_while_the_guide_is_open(tmp_path):
    app, _, _ = build_app(tmp_path)
    app.start()
    before = app.volume
    send(app, Action.HOME)
    send(app, Action.VOLUME_UP)

    assert app.volume > before


def _on_now_position(ass):
    """Where the ON NOW marker is drawn, or None if it isn't."""
    for line in ass.split("\n"):
        if line.endswith("ON NOW"):
            x, y = re.search(r"\\pos\((\d+),(\d+)\)", line).groups()
            return (int(x), int(y))
    return None


def test_the_on_air_marker_follows_the_channel_while_the_guide_is_open(tmp_path):
    # Changing channel with the dedicated buttons while browsing has to redraw
    # the guide. Counting that ON NOW appears once is not enough - a stale
    # drawing has exactly one too, just sitting on the wrong tile.
    app, player, _ = build_app(tmp_path)
    app.start()
    send(app, Action.HOME)
    before = _on_now_position(player.overlays[5])
    send(app, Action.CHANNEL_UP)
    after = _on_now_position(player.overlays[5])

    assert before is not None and after is not None
    assert after != before, "the ON NOW marker stayed on the old channel's tile"
    assert player.overlays[5].count("ON NOW") == 1


# -- choosing ---------------------------------------------------------------
def test_ok_tunes_to_the_cursor_and_closes_the_guide(tmp_path):
    app, _, _ = build_app(tmp_path)
    app.start()
    send(app, Action.HOME)
    send(app, Action.NAV_RIGHT)
    send(app, Action.ENTER)

    assert app.lineup.current.number == 3
    assert not app.guide.is_open


def test_ok_on_the_channel_already_playing_does_not_restart_it(tmp_path):
    # tune_in is random, so re-tuning would jump to a different episode.
    # Pressing OK on what you are already watching must never interrupt it.
    app, player, clock = build_app(tmp_path)
    app.start()
    send(app, Action.HOME)
    before = len(player.played) + len(player.transitions)
    playing_before = player.current

    send(app, Action.ENTER)
    # Let any deferred switch land. Tuning PRELOADS and cuts over a moment
    # later, so counting straight after the press would miss a re-tune
    # completely and this test would pass whatever the code did.
    clock.advance(5)
    app.step()

    assert not app.guide.is_open
    assert len(player.played) + len(player.transitions) == before
    assert player.current == playing_before, "the episode restarted"


# -- closing itself ---------------------------------------------------------
def test_the_guide_closes_itself_after_the_timeout(tmp_path):
    app, player, clock = build_app(tmp_path, guide={"timeout_seconds": 20})
    app.start()
    send(app, Action.HOME)

    clock.advance(21)
    app.step()

    assert not app.guide.is_open
    assert 5 not in player.overlays, "the guide closed but stayed on screen"


def test_power_closes_the_guide_rather_than_being_swallowed_by_it(tmp_path):
    app, player, _ = build_app(tmp_path)
    app.start()
    send(app, Action.HOME)
    send(app, Action.POWER)

    assert app.standby
    assert not app.guide.is_open
    assert 5 not in player.overlays


# -- the random channel button ----------------------------------------------
def test_random_never_picks_the_channel_already_playing(tmp_path):
    # Without this the button sometimes appears to do nothing, or restarts the
    # current channel on a different episode, which reads as a fault.
    app, _, _ = build_app(tmp_path)
    app.start()
    for _ in range(40):
        before = app.lineup.current.number
        send(app, Action.RANDOM)
        assert app.lineup.current.number != before


def test_random_reaches_every_other_channel_eventually(tmp_path):
    app, _, _ = build_app(tmp_path)
    app.start()
    seen = set()
    for _ in range(60):
        send(app, Action.RANDOM)
        seen.add(app.lineup.current.number)
    assert seen == {2, 3, 4}


def test_random_on_a_one_channel_box_does_nothing_rather_than_crashing(tmp_path):
    make_show(tmp_path, "only", 3)
    app, _, _ = build_app(
        tmp_path,
        channels=[{"number": 2, "name": "Only", "path": str(tmp_path / "only")}],
    )
    app.start()
    send(app, Action.RANDOM)
    assert app.lineup.current.number == 2


def test_random_closes_the_guide_if_it_is_open(tmp_path):
    app, _, _ = build_app(tmp_path)
    app.start()
    send(app, Action.HOME)
    send(app, Action.RANDOM)
    assert not app.guide.is_open
