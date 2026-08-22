"""The ✱ button: finish up, then sign off.

One rule: stop at the end of this programme, or after the cap, whichever comes
sooner - except that anything short enough to be a normal episode is always
allowed to finish. The runtime decides; nothing is labelled a film.
"""

from nostalgiabox.bedtime import CAP, FINISH_UNDER, deadline_for

NOW = 1000.0


def test_a_normal_episode_is_allowed_to_finish_even_from_the_start():
    # 22-minute episode, 21 minutes left: longer than the 15-minute cap, but
    # short enough that a child gets an ending.
    assert deadline_for(NOW, position=60, runtime=22 * 60) == NOW + 21 * 60


def test_a_nearly_finished_episode_stops_at_its_own_end():
    assert deadline_for(NOW, position=17 * 60, runtime=22 * 60) == NOW + 5 * 60


def test_a_long_episode_is_capped():
    assert deadline_for(NOW, position=15 * 60, runtime=45 * 60) == NOW + CAP


def test_a_film_is_capped():
    assert deadline_for(NOW, position=20 * 60, runtime=90 * 60) == NOW + CAP


def test_a_film_near_its_end_stops_when_it_ends():
    assert deadline_for(NOW, position=81 * 60, runtime=90 * 60) == NOW + 9 * 60


def test_an_unknowable_length_falls_back_to_the_cap():
    assert deadline_for(NOW, position=0, runtime=None) == NOW + CAP


def test_the_exception_is_the_runtime_not_the_time_remaining():
    # A 26-minute programme is over the line, so it does NOT get to finish.
    assert FINISH_UNDER == 25 * 60
    assert deadline_for(NOW, position=0, runtime=26 * 60) == NOW + CAP


# --- the countdown ---------------------------------------------------------

from nostalgiabox.bedtime import MARKS, due_mark, initial_marks  # noqa: E402


def test_pressing_with_eight_minutes_left_skips_the_marks_already_gone():
    assert initial_marks(8 * 60) == {15, 10}


def test_pressing_with_a_long_wait_spends_nothing_yet():
    assert initial_marks(21 * 60) == set()


def test_a_mark_exactly_reached_still_gets_announced():
    assert 15 not in initial_marks(15 * 60)


def test_the_countdown_announces_the_largest_mark_reached():
    assert due_mark(9 * 60, spent={15, 10}) is None
    assert due_mark(5 * 60, spent={15, 10}) == 5


def test_a_mark_is_only_announced_once():
    # Five is spent, and four minutes has not yet reached three.
    assert due_mark(4 * 60, spent={15, 10, 5}) is None
    assert due_mark(3 * 60, spent={15, 10, 5}) == 3


def test_every_mark_is_a_whole_number_of_minutes_descending():
    assert list(MARKS) == sorted(MARKS, reverse=True)


# --- the button, through the app -------------------------------------------

from nostalgiabox.actions import Action  # noqa: E402
from nostalgiabox.player import END_EOF  # noqa: E402
from tests.test_app import build_app, send  # noqa: E402


def _armed(tmp_path, *, runtime=90 * 60, position=0.0):
    app, player, clock = build_app(tmp_path)
    app.start()
    player.duration = runtime
    player.time_pos = position
    send(app, Action.BEDTIME)
    return app, player, clock


def test_pressing_arms_a_deadline_and_says_so(tmp_path):
    app, player, clock = _armed(tmp_path)
    assert app.bedtime_deadline == clock() + CAP
    assert "15" in " ".join(player.overlays.values())


def test_pressing_again_cancels(tmp_path):
    app, player, _ = _armed(tmp_path)
    send(app, Action.BEDTIME)
    assert app.bedtime_deadline is None


def test_the_deadline_does_not_move_when_the_channel_changes(tmp_path):
    app, player, clock = _armed(tmp_path)
    fixed = app.bedtime_deadline
    clock.advance(60)
    send(app, Action.CHANNEL_UP)
    assert app.bedtime_deadline == fixed, "channel-hopping must not buy more time"


def test_reaching_the_deadline_signs_the_box_off(tmp_path):
    app, player, clock = _armed(tmp_path)
    clock.advance(CAP + 1)
    app.step()
    assert app.powered_off is True


def test_an_episode_ending_early_signs_off_rather_than_starting_another(tmp_path):
    app, player, clock = _armed(tmp_path)
    player.finish_current(END_EOF)
    app._drain_playback_events()
    assert app.powered_off is True


def test_nothing_happens_when_the_button_was_never_pressed(tmp_path):
    app, player, clock = build_app(tmp_path)
    app.start()
    clock.advance(3600)
    app.step()
    assert app.powered_off is False
