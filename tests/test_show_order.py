"""Shuffle the SHOWS, but play each show's episodes in order.

A channel has always been a shuffle bag of every episode on it, which means a
child can get Camp Snoopy E07, then E02, then E19. Fine for Rugrats, poor for
anything with any continuity, and it makes it impossible to work through a
series.

Fully sequential is not the answer either - all of show A, then all of show B,
is a box set rather than a television channel.

So: the bag holds SHOWS. Drawing a show hands back that show's next episode in
order, and the show's cursor moves on. Which show you get is still a surprise;
which episode of it is not.

The no-immediate-repeat property the shuffle bag works hard for still applies,
now at the show level: you never get the same show twice in a row while the
channel has more than one.
"""

from pathlib import Path

from nostalgiabox.playlist import ShowOrder


def ep(show, n):
    return Path(f"/media/Chan/{show}/Season 01/{show} - S01E{n:02d}.mp4")


def show_of(path):
    return path.parent.parent.name


A = [ep("Alpha", n) for n in range(1, 4)]      # 3 episodes
B = [ep("Beta", n) for n in range(1, 3)]       # 2 episodes
C = [ep("Gamma", n) for n in range(1, 2)]      # 1 episode


def order(items, seed=7):
    import random
    return ShowOrder(items, key=show_of, rng=random.Random(seed))


# --- episodes within a show ------------------------------------------------


def test_a_show_plays_its_episodes_in_order():
    o = order(A)
    assert [o.next() for _ in range(3)] == A


def test_a_show_loops_back_to_its_first_episode():
    o = order(A)
    for _ in range(3):
        o.next()
    assert o.next() == A[0]


def test_each_show_keeps_its_own_place():
    """Interleaving shows must not lose either one's position."""
    o = order(A + B)
    seen = [o.next() for _ in range(10)]
    got_a = [p for p in seen if show_of(p) == "Alpha"]
    got_b = [p for p in seen if show_of(p) == "Beta"]
    assert got_a == [A[i % 3] for i in range(len(got_a))]
    assert got_b == [B[i % 2] for i in range(len(got_b))]


def test_episodes_are_ordered_by_name_not_by_input_order():
    """Directory listings arrive in any order; S01E01 must still come first."""
    o = order(list(reversed(A)))
    assert o.next() == A[0]


# --- which show comes next -------------------------------------------------


def test_every_show_appears_before_any_repeats():
    o = order(A + B + C)
    first_three = {show_of(o.next()) for _ in range(3)}
    assert first_three == {"Alpha", "Beta", "Gamma"}


def test_the_same_show_never_comes_twice_running():
    o = order(A + B + C)
    seen = [show_of(o.next()) for _ in range(40)]
    assert all(x != y for x, y in zip(seen, seen[1:]))


def test_a_single_show_channel_just_plays_in_order():
    o = order(C + [ep("Gamma", 2), ep("Gamma", 3)])
    assert [p.name for p in (o.next(), o.next(), o.next())] == [
        "Gamma - S01E01.mp4", "Gamma - S01E02.mp4", "Gamma - S01E03.mp4"
    ]


# --- the guide asks without disturbing anything ----------------------------


def test_peek_does_not_spend_an_episode():
    o = order(A + B)
    assert o.peek() == o.next()


def test_peek_is_stable_when_called_twice():
    o = order(A + B)
    assert o.peek() == o.peek()


# --- shape -----------------------------------------------------------------


def test_it_reports_how_many_episodes_it_holds():
    assert len(order(A + B + C)) == 6


def test_an_empty_channel_is_empty():
    o = order([])
    assert o.is_empty
    assert len(o) == 0


# --- through the config, end to end ----------------------------------------

def test_a_channel_can_be_told_to_play_shows_in_order(tmp_path):
    """The whole point, exercised the way the box actually builds a channel."""
    from nostalgiabox.channel import build_lineup
    from nostalgiabox.config import config_from_dict
    from tests.helpers import make_show

    chan = tmp_path / "chan"
    make_show(chan, "Alpha", 3)
    make_show(chan, "Beta", 3)

    cfg = config_from_dict({
        "shuffle_seed": 5,
        "episode_order": "sequential",
        "start_offset": 0,
        "channels": [{"number": 2, "name": "Test", "path": str(chan)}],
    })
    lineup = build_lineup(cfg)
    channel = lineup.current

    seen = [channel.tune_in().path for _ in range(6)]
    for show in ("Alpha", "Beta"):
        got = [p.name for p in seen if p.parent.name == show]
        assert got == sorted(got), f"{show} played out of order: {got}"


def test_shuffle_is_still_the_default(tmp_path):
    from nostalgiabox.channel import build_lineup
    from nostalgiabox.config import config_from_dict
    from tests.helpers import make_show

    chan = tmp_path / "chan"
    make_show(chan, "Alpha", 3)
    cfg = config_from_dict({
        "shuffle_seed": 5,
        "channels": [{"number": 2, "name": "Test", "path": str(chan)}],
    })
    assert cfg.episode_order == "shuffle"
    assert build_lineup(cfg).current.episode_order == "shuffle"


def test_a_nonsense_order_is_refused(tmp_path):
    import pytest
    from nostalgiabox.config import ConfigError, config_from_dict
    with pytest.raises(ConfigError):
        config_from_dict({
            "episode_order": "alphabetical",
            "channels": [{"number": 2, "name": "T", "path": str(tmp_path)}],
        })


# --- multi-part items stay together ----------------------------------------
#
# A compilation splits into independent episodes, so shuffle order is harmless.
# A FILM split in half is one story: the halves only make sense back to back.
# So while a show is part-way through a multi-part run, the bag holds onto that
# show instead of drawing a new one - which is what lets the box go to a
# commercial break in the middle of a film and come back to it.


def part(show, name, n):
    return Path(f"/media/Chan/{show}/Season 01/{name} - pt{n:02d}.mp4")


F = [part("Peliculas", "Sailor Moon R", n) for n in (1, 2)]
G = [part("Peliculas", "Sailor Moon S", n) for n in (1, 2, 3)]


def test_a_two_part_film_plays_back_to_back():
    o = order(A + F)
    seen = [o.next() for _ in range(12)]
    i = seen.index(F[0])
    assert seen[i + 1] == F[1], "part 2 must follow part 1 immediately"


def test_a_three_part_film_plays_all_three_back_to_back():
    o = order(A + G)
    seen = [o.next() for _ in range(16)]
    i = seen.index(G[0])
    assert seen[i + 1 : i + 3] == [G[1], G[2]]


def test_the_channel_moves_on_after_the_last_part():
    """Stickiness releases once the run finishes, or the film would loop."""
    o = order(A + F)
    seen = [o.next() for _ in range(12)]
    i = seen.index(F[1])
    assert show_of(seen[i + 1]) != "Peliculas"


def test_ordinary_episodes_still_alternate_shows():
    """Only multi-part runs stick - normal episodes are unchanged."""
    o = order(A + B)
    seen = [show_of(o.next()) for _ in range(12)]
    assert all(x != y for x, y in zip(seen, seen[1:]))


def test_peek_follows_a_sticky_run():
    """The guide must promise the part that is actually coming next."""
    o = order(A + F)
    for _ in range(12):
        got = o.next()
        if got == F[0]:
            assert o.peek() == F[1]
            return
    raise AssertionError("part 1 never came up")
