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
