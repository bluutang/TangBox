"""Commercial breaks: the pool that assembles them, and the app that plays them."""

from __future__ import annotations

import random

import pytest

from nostalgiabox.actions import Action, InputEvent
from nostalgiabox.app import TVApp
from nostalgiabox.channel import PlayRequest
from nostalgiabox.config import config_from_dict
from nostalgiabox.input.manager import InputManager
from nostalgiabox.interstitial import DEFAULT_CLIP_SECONDS, CommercialPool
from nostalgiabox.player import END_EOF, MockPlayer
from tests.helpers import FakeClock, make_show


def make_ads(root, count, ext=".mp4"):
    """A folder of dummy advert files."""
    folder = root / "_commercials"
    folder.mkdir(parents=True, exist_ok=True)
    for i in range(1, count + 1):
        (folder / f"ad{i:02d}{ext}").write_bytes(b"\x00")
    return folder


def fixed_probe(seconds):
    return lambda path: seconds


# ---------------------------------------------------------------- the pool ---


def test_pool_is_unavailable_without_a_folder(tmp_path):
    pool = CommercialPool(tmp_path / "nope")
    assert not pool.is_available
    assert pool.build_break() == []


def test_pool_is_unavailable_when_folder_is_empty(tmp_path):
    (tmp_path / "_commercials").mkdir()
    pool = CommercialPool(tmp_path / "_commercials")
    assert not pool.is_available
    assert pool.build_break() == []


def test_pool_disabled_by_config_flag(tmp_path):
    make_ads(tmp_path, 5)
    pool = CommercialPool(tmp_path / "_commercials", enabled=False)
    assert not pool.is_available


def test_break_seconds_zero_disables_breaks(tmp_path):
    make_ads(tmp_path, 5)
    pool = CommercialPool(tmp_path / "_commercials", break_seconds=0)
    assert not pool.is_available


def test_break_fills_the_target_duration(tmp_path):
    make_ads(tmp_path, 10)
    pool = CommercialPool(
        tmp_path / "_commercials", break_seconds=75, probe=fixed_probe(30.0)
    )
    clips = pool.build_break()
    # 30s adverts: two gets to 60 (short), three reaches 90 (>= 75). So three.
    assert len(clips) == 3


def test_longer_adverts_make_a_shorter_break(tmp_path):
    make_ads(tmp_path, 10)
    pool = CommercialPool(
        tmp_path / "_commercials", break_seconds=75, probe=fixed_probe(60.0)
    )
    assert len(pool.build_break()) == 2


def test_break_never_repeats_a_clip_within_itself(tmp_path):
    make_ads(tmp_path, 3)
    pool = CommercialPool(
        tmp_path / "_commercials", break_seconds=600, probe=fixed_probe(5.0)
    )
    clips = pool.build_break()
    # Only three adverts exist, so the break is capped at three - not padded by
    # replaying the same file to chase the target.
    assert len(clips) == 3
    assert len(set(clips)) == 3


def test_break_respects_max_clips(tmp_path):
    make_ads(tmp_path, 20)
    pool = CommercialPool(
        tmp_path / "_commercials",
        break_seconds=600,
        probe=fixed_probe(1.0),
        max_clips=4,
    )
    assert len(pool.build_break()) == 4


def test_unprobeable_clips_fall_back_to_a_default_length(tmp_path):
    make_ads(tmp_path, 10)
    pool = CommercialPool(
        tmp_path / "_commercials",
        break_seconds=DEFAULT_CLIP_SECONDS * 2,
        probe=lambda path: None,  # ffprobe missing or unreadable file
    )
    assert len(pool.build_break()) == 2


def test_durations_are_probed_once_per_clip(tmp_path):
    make_ads(tmp_path, 2)
    calls = []

    def counting_probe(path):
        calls.append(path)
        return 30.0

    pool = CommercialPool(
        tmp_path / "_commercials", break_seconds=45, probe=counting_probe,
        rng=random.Random(1),
    )
    for _ in range(5):
        pool.build_break()
    # Two distinct files, so at most two probes no matter how many breaks run.
    assert len(set(calls)) == 2
    assert len(calls) == 2


def test_every_advert_airs_before_any_repeats(tmp_path):
    make_ads(tmp_path, 6)
    pool = CommercialPool(
        tmp_path / "_commercials", break_seconds=1, probe=fixed_probe(30.0),
        rng=random.Random(3),
    )
    seen = [pool.build_break()[0] for _ in range(6)]
    assert len(set(seen)) == 6


# ----------------------------------------------------------------- the app ---


def build_app(tmp_path, *, ads=0, **overrides):
    for name in ("dragon", "arthur"):
        make_show(tmp_path, name, 4)
    if ads:
        make_ads(tmp_path, ads)
    data = {
        "shuffle_seed": 7,
        "start_channel": 2,
        "start_offset": 0,
        "power_off_command": [],
        "channels": [
            {"number": 2, "name": "Dragon Tales", "path": str(tmp_path / "dragon")},
            {"number": 3, "name": "Arthur", "path": str(tmp_path / "arthur")},
        ],
    }
    if ads:
        data["commercials"] = {
            "path": str(tmp_path / "_commercials"),
            "break_seconds": 60,
        }
    data.update(overrides)
    app = TVApp(
        config_from_dict(data),
        MockPlayer(),
        InputManager([]),
        clock=FakeClock(),
    )
    return app


def end_episode(app):
    """Signal that whatever is playing has finished."""
    app._ended.put(END_EOF)
    app.step()


def is_ad(app):
    return app._playing_path.parent.name == "_commercials"


def test_no_commercials_configured_behaves_exactly_as_before(tmp_path):
    app = build_app(tmp_path, ads=0)
    app.start()
    end_episode(app)
    assert not is_ad(app)
    assert not app.in_break


def test_episode_end_goes_to_a_break(tmp_path):
    app = build_app(tmp_path, ads=6)
    app.start()
    assert not is_ad(app)

    end_episode(app)
    assert is_ad(app)
    assert app.in_break


def test_break_ends_and_the_episode_follows(tmp_path):
    app = build_app(tmp_path, ads=6)
    app.start()
    end_episode(app)

    # Roll through the adverts; the next non-advert must be an episode.
    for _ in range(10):
        if not is_ad(app):
            break
        end_episode(app)
    else:  # pragma: no cover - would mean the break never ended
        pytest.fail("break never ended")

    assert not is_ad(app)
    assert not app.in_break


def test_adverts_start_from_the_beginning(tmp_path):
    # Episodes get a random start offset ("you tuned in late"); adverts must not.
    app = build_app(tmp_path, ads=6, start_offset=[30, 30])
    app.start()
    end_episode(app)
    assert is_ad(app)
    played_path, played_start = app.player.played[-1]
    assert played_path == app._playing_path
    assert played_start == 0.0


def test_changing_channel_abandons_the_break(tmp_path):
    app = build_app(tmp_path, ads=6)
    app.start()
    end_episode(app)
    assert app.in_break

    app.handle_event(InputEvent(Action.CHANNEL_UP))
    assert not app.in_break
    assert not is_ad(app)


def test_resume_never_remembers_an_advert(tmp_path):
    app = build_app(tmp_path, ads=6, tune_in="resume")
    app.start()
    end_episode(app)
    assert is_ad(app)

    channel = app.lineup.current
    app._remember_position()
    # Nothing about the advert should have been recorded against the channel.
    assert app._playing_path not in getattr(channel, "_positions", {})


def test_underscore_folders_are_not_channels(tmp_path):
    """The `_commercials` pool must not be auto-discovered as a channel."""
    make_show(tmp_path, "dragon", 2)
    make_ads(tmp_path, 3)
    config = config_from_dict({"media_root": str(tmp_path), "shuffle_seed": 1})
    assert [c.name for c in config.channels] == ["Dragon"]


# ------------------------------------------- breaks that scale to the show ---


def test_break_ignores_episode_length_until_a_ratio_is_set(tmp_path):
    """The old fixed-length behaviour is what you get by default."""
    make_ads(tmp_path, 10)
    pool = CommercialPool(
        tmp_path / "_commercials", break_seconds=75, probe=fixed_probe(30.0)
    )
    assert len(pool.build_break(episode_seconds=1230)) == 3


def test_a_longer_episode_earns_a_longer_break(tmp_path):
    make_ads(tmp_path, 20)
    pool = CommercialPool(
        tmp_path / "_commercials",
        break_seconds=75,
        break_ratio=0.18,
        probe=fixed_probe(30.0),
    )
    short = pool.build_break(episode_seconds=410)   # target 75 (the floor)
    long = pool.build_break(episode_seconds=1230)   # target 221
    assert len(short) == 3
    assert len(long) > len(short)


def test_break_never_falls_below_break_seconds(tmp_path):
    """A seven-minute segment still gets a proper break, not a token one."""
    make_ads(tmp_path, 10)
    pool = CommercialPool(
        tmp_path / "_commercials",
        break_seconds=75,
        break_ratio=0.18,
        probe=fixed_probe(30.0),
    )
    assert len(pool.build_break(episode_seconds=60)) == 3


def test_an_advert_too_long_for_the_budget_is_not_used(tmp_path):
    """A nine-minute compilation must never become the whole break."""
    folder = make_ads(tmp_path, 4)
    lengths = {"ad01": 600.0, "ad02": 30.0, "ad03": 30.0, "ad04": 30.0}
    pool = CommercialPool(
        folder, break_seconds=75, probe=lambda p: lengths[p.stem]
    )
    for _ in range(10):
        clips = pool.build_break()
        assert all(c.stem != "ad01" for c in clips)


def test_a_long_advert_airs_when_the_episode_is_long_enough(tmp_path):
    """The same compilation is fine in front of a feature-length programme."""
    folder = make_ads(tmp_path, 4)
    lengths = {"ad01": 300.0, "ad02": 30.0, "ad03": 30.0, "ad04": 30.0}
    pool = CommercialPool(
        folder, break_seconds=75, break_ratio=0.18, probe=lambda p: lengths[p.stem]
    )
    aired = set()
    for _ in range(20):
        aired.update(c.stem for c in pool.build_break(episode_seconds=3000))
    assert "ad01" in aired


def test_a_rejected_advert_is_not_burned(tmp_path):
    """Passing over an over-long clip must not consume its turn in the bag."""
    folder = make_ads(tmp_path, 3)
    lengths = {"ad01": 600.0, "ad02": 30.0, "ad03": 30.0}
    pool = CommercialPool(
        folder, break_seconds=45, probe=lambda p: lengths[p.stem]
    )
    # ad02 and ad03 are the only usable clips; each break should draw one of
    # them, and over many breaks both must air repeatedly rather than the pool
    # running dry.
    seen = [c.stem for _ in range(20) for c in pool.build_break()]
    assert seen.count("ad02") > 5
    assert seen.count("ad03") > 5


def test_the_finished_episode_sets_the_break_length(tmp_path, monkeypatch):
    """The break is built for the programme that just ended, not a fixed guess."""
    app = build_app(tmp_path, ads=6)
    seen = {}

    real = app.commercials.build_break

    def spy(episode_seconds=None, *, network=None):
        seen["episode_seconds"] = episode_seconds
        return real(episode_seconds=episode_seconds, network=network)

    monkeypatch.setattr(app.commercials, "build_break", spy)
    monkeypatch.setattr(
        "nostalgiabox.app.probe_duration", lambda path, **kw: 1230.0
    )

    app.start()
    end_episode(app)
    assert seen["episode_seconds"] == 1230.0


def test_an_unprobeable_episode_still_gets_a_break(tmp_path, monkeypatch):
    app = build_app(tmp_path, ads=6)
    monkeypatch.setattr("nostalgiabox.app.probe_duration", lambda path, **kw: None)
    app.start()
    end_episode(app)
    assert is_ad(app)


# ------------------------------------------------ adverts that match the channel ---


def make_network_ads(root, network, count, seconds=30.0):
    """A folder of adverts belonging to one network."""
    folder = root / "_commercials" / network
    folder.mkdir(parents=True, exist_ok=True)
    for i in range(1, count + 1):
        (folder / f"{network.lower()}{i:02d}.mp4").write_bytes(b"\x00")
    return folder


def test_a_flat_folder_behaves_exactly_as_it_always_has(tmp_path):
    """The whole reason this is safe to ship before anything is sorted."""
    make_ads(tmp_path, 6)
    pool = CommercialPool(tmp_path / "_commercials", probe=fixed_probe(30.0))
    assert len(pool) == 6
    assert all(c.parent.name == "_commercials" for c in pool.build_break())


def test_a_channel_with_no_network_gets_only_the_generic_pool(tmp_path):
    make_ads(tmp_path, 6)
    make_network_ads(tmp_path, "Nickelodeon", 4)
    pool = CommercialPool(tmp_path / "_commercials", probe=fixed_probe(30.0))
    aired = {c.name for _ in range(20) for c in pool.build_break()}
    assert not any(n.startswith("nickelodeon") for n in aired)


def test_a_channel_on_a_network_gets_its_bumps_as_well_as_the_ads(tmp_path):
    """Network AND generic, not network alone.

    Nine Nickelodeon bumps on their own would come round every few breaks. Real
    Nickelodeon ran its bumps between the same cereal and toy adverts everybody
    else was running, so the network pool sprinkles identity through the period
    advertising rather than replacing it.
    """
    make_ads(tmp_path, 6)
    make_network_ads(tmp_path, "Nickelodeon", 4)
    pool = CommercialPool(tmp_path / "_commercials", probe=fixed_probe(30.0))
    aired = {c.name for _ in range(30)
             for c in pool.build_break(network="Nickelodeon")}
    assert any(n.startswith("nickelodeon") for n in aired), "no bumps aired"
    assert any(n.startswith("ad") for n in aired), "no generic adverts aired"


def test_one_network_never_airs_anothers_bumps(tmp_path):
    make_ads(tmp_path, 6)
    make_network_ads(tmp_path, "Nickelodeon", 4)
    make_network_ads(tmp_path, "Disney", 4)
    pool = CommercialPool(tmp_path / "_commercials", probe=fixed_probe(30.0))
    aired = {c.name for _ in range(30) for c in pool.build_break(network="Disney")}
    assert not any(n.startswith("nickelodeon") for n in aired)


def test_an_unknown_network_falls_back_to_the_generic_pool(tmp_path):
    """A typo in config.yaml must not take the adverts off a channel."""
    make_ads(tmp_path, 6)
    make_network_ads(tmp_path, "Nickelodeon", 4)
    pool = CommercialPool(tmp_path / "_commercials", probe=fixed_probe(30.0))
    clips = pool.build_break(network="Nickleodeon")   # misspelled on purpose
    assert clips
    assert all(c.parent.name == "_commercials" for c in clips)


def test_each_network_keeps_its_own_running_order(tmp_path):
    """The every-advert-before-repeats guarantee is per channel, not global."""
    make_ads(tmp_path, 2)
    make_network_ads(tmp_path, "Nickelodeon", 1)
    pool = CommercialPool(
        tmp_path / "_commercials", break_seconds=30, probe=fixed_probe(30.0)
    )
    # Draining Nickelodeon's bag must not affect what the generic pool owes.
    for _ in range(10):
        pool.build_break(network="Nickelodeon")
    generic = [c.name for _ in range(2) for c in pool.build_break()]
    assert sorted(generic) == ["ad01.mp4", "ad02.mp4"]


# ---------------------------------------------------- the hard ceiling ---


def test_no_ceiling_by_default(tmp_path):
    """Zero means what it has always meant here: the feature is off."""
    make_ads(tmp_path, 20)
    pool = CommercialPool(
        tmp_path / "_commercials", break_seconds=75, break_ratio=0.18,
        probe=fixed_probe(60.0),
    )
    clips = pool.build_break(episode_seconds=3600)   # target 648s
    assert sum(pool._duration_of(c) for c in clips) > 300


def test_a_break_never_runs_past_the_ceiling(tmp_path):
    make_ads(tmp_path, 20)
    pool = CommercialPool(
        tmp_path / "_commercials", break_seconds=75, break_ratio=0.18,
        break_max_seconds=225, probe=fixed_probe(30.0), max_clips=20,
    )
    for _ in range(40):
        clips = pool.build_break(episode_seconds=3600)
        assert sum(pool._duration_of(c) for c in clips) <= 225


def test_the_last_advert_cannot_overshoot_the_ceiling(tmp_path):
    """The overshoot allowance must not be able to breach the hard cap.

    A break is allowed to run over its TARGET by up to break_seconds, because
    a thirty-second advert finishing a break with five seconds left is what
    television did. Left unchecked that same allowance would carry it straight
    through a ceiling - 225s of target plus 75s of slack is five minutes.
    """
    folder = make_ads(tmp_path, 8)
    lengths = {f"ad{i:02d}": 70.0 for i in range(1, 9)}
    pool = CommercialPool(
        folder, break_seconds=75, break_ratio=0.18, break_max_seconds=225,
        probe=lambda p: lengths[p.stem], max_clips=20,
    )
    for _ in range(30):
        clips = pool.build_break(episode_seconds=3600)
        assert sum(pool._duration_of(c) for c in clips) <= 225


def test_a_ceiling_never_leaves_a_break_empty(tmp_path):
    """Even an advert longer than the whole ceiling still gets a break out."""
    folder = make_ads(tmp_path, 3)
    pool = CommercialPool(
        folder, break_seconds=75, break_max_seconds=60, probe=fixed_probe(300.0)
    )
    assert pool.build_break(episode_seconds=1230)
