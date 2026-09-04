"""Channels: the folders of episodes and how they decide what to play.

A :class:`Channel` wraps one show (a folder of episode files) and knows how to
answer two questions:

* "I just tuned in - what should I play?" (:meth:`Channel.tune_in`)
* "The episode ended - what's next?" (:meth:`Channel.advance`)

The answer depends on the configured ``tune_in`` mode (see ``config.py``):
random, resume, or broadcast. :class:`ChannelLineup` holds all the channels and
provides the up/down/by-number navigation a remote needs.
"""

from __future__ import annotations

import logging
import random
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import AbstractSet, Dict, List, Optional, Sequence

# Patterns for pulling a season number out of a file/folder path.
_SEASON_PATTERNS = (
    re.compile(r"s(\d{1,2})[ ._-]?e\d{1,3}", re.IGNORECASE),   # S06E01, s6e1
    re.compile(r"\bseason[ ._-]*(\d{1,2})\b", re.IGNORECASE),  # Season 6
    re.compile(r"\b(\d{1,2})x\d{1,3}\b"),                       # 6x01
)

from .config import ChannelConfig, Config
from .playlist import ShowOrder, ShuffleBag
from .probe import DEFAULT_EPISODE_SECONDS, flush_cache, probe_duration

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlayRequest:
    """An instruction to the player: play ``path`` starting at ``start`` sec."""

    path: Path
    start: float = 0.0


def show_name_for(episode: Path, channel_root: Path) -> Optional[str]:
    """Which programme an episode belongs to: its folder under the channel.

    A channel is a GROUP of shows, so the layout is
    ``<channel>/<show>/<episode>`` - and with ``scan_recursive`` often
    ``<channel>/<show>/Season 2/<episode>``, hence taking the FIRST component
    rather than the parent folder.

    Returns None when there is nothing to name: an episode sitting loose in the
    channel folder, or a path from somewhere else entirely (an advert, say).
    The banner then simply omits the line rather than showing a blank one.
    """
    try:
        rel = episode.relative_to(channel_root)
    except ValueError:
        return None
    parts = rel.parts
    if len(parts) < 2:
        return None
    return parts[0]


# Patterns for pulling an EPISODE number out of a file name. Deliberately
# narrow: a bare number is far more often a sequel or a year than an episode,
# so "Toy Story 2 (1999)" must not become E02 or E99.
_EPISODE_PATTERNS = (
    re.compile(r"s\d{1,2}[ ._-]?e(\d{1,3})", re.IGNORECASE),   # S06E01, s6.e1
    re.compile(r"\b\d{1,2}x(\d{1,3})\b"),                      # 6x01
    re.compile(r"\bepisode[ ._-]*(\d{1,3})\b", re.IGNORECASE),  # Episode 5
    re.compile(r"\be(\d{1,3})\b", re.IGNORECASE),               # E04
)


def detect_episode(text: str) -> Optional[int]:
    """Best-effort extraction of an episode number from a file name."""
    for pattern in _EPISODE_PATTERNS:
        match = pattern.search(text)
        if match:
            return int(match.group(1))
    return None


def episode_label_for(path: Path) -> Optional[str]:
    """A short "S01 E04" for the banner, or None when there is nothing to say.

    Films have no label, and that is the common case on the Cine channel - the
    banner then omits the line rather than showing a blank one.

    Season and episode can live in different parts of the path
    ("Season 2/Episode 5.mp4"), so the season is looked for across the whole
    path while the episode comes from the file name - otherwise a folder called
    "Season 2" would supply the episode number as well.
    """
    season = detect_season(str(path))
    episode = detect_episode(path.name)
    if season is not None and episode is not None:
        return f"S{season:02d} E{episode:02d}"
    if episode is not None:
        return f"E{episode:02d}"
    return None


def detect_season(text: str) -> Optional[int]:
    """Best-effort extraction of a season number from a path/filename."""
    for pattern in _SEASON_PATTERNS:
        match = pattern.search(text)
        if match:
            return int(match.group(1))
    return None


def scan_episodes(
    root: Path,
    extensions: Sequence[str],
    *,
    recursive: bool = True,
    exclude: Sequence[str] = (),
    exclude_seasons: AbstractSet[int] = frozenset(),
) -> List[Path]:
    """Return a sorted list of episode files under ``root``.

    Sorting is natural-ish (case-insensitive by full path) so that, in the rare
    cases we present episodes in order, they are at least stable. Hidden files
    and typical sidecar files are ignored.

    ``exclude`` is a list of case-insensitive glob patterns; any episode whose
    relative path or filename matches one is dropped. ``exclude_seasons`` drops
    episodes whose detected season number is in the set.
    """
    if not root.exists():
        log.warning("channel folder does not exist: %s", root)
        return []
    exts = {e.lower() for e in extensions}
    patterns = [p.lower() for p in exclude]
    walker = root.rglob("*") if recursive else root.glob("*")
    episodes = [
        p
        for p in walker
        if p.is_file()
        and p.suffix.lower() in exts
        and not p.name.startswith(".")
        and not _is_excluded(p, root, patterns, exclude_seasons)
    ]
    episodes.sort(key=lambda p: str(p).lower())
    return episodes


def _is_excluded(
    path: Path,
    root: Path,
    patterns: Sequence[str],
    exclude_seasons: AbstractSet[int],
) -> bool:
    import fnmatch

    try:
        rel = path.relative_to(root).as_posix().lower()
    except ValueError:  # pragma: no cover - path always under root here
        rel = path.name.lower()
    name = path.name.lower()
    for pat in patterns:
        if fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(name, pat):
            return True
    if exclude_seasons:
        season = detect_season(rel)
        if season is not None and season in exclude_seasons:
            return True
    return False


#: The moment every broadcast channel counts from - 2026-01-01T00:00:00Z.
#:
#: Fixed and shared, so a channel is mid-programme the first time anyone tunes
#: to it and stays in step with itself across a restart. The particular date is
#: arbitrary; only its being constant matters.
BROADCAST_EPOCH = 1767225600.0

#: Seconds of phase between one channel number and the next, so channels do not
#: all change programme on the same second. Prime, so it does not fall into
#: step with common episode lengths.
_PHASE_STRIDE = 1009.0


class BroadcastSchedule:
    """A never-ending, always-running shuffled running order for a channel.

    Given episode durations and a fixed start epoch, it can report exactly what
    "would be airing" at any wall-clock moment - the illusion that the station
    kept broadcasting while nobody was watching. The running order is a single
    shuffle that loops forever.
    """

    def __init__(
        self,
        episodes: Sequence[Path],
        durations: Sequence[float],
        *,
        epoch: float,
        rng: random.Random,
    ) -> None:
        if len(episodes) != len(durations):
            raise ValueError("episodes and durations must be the same length")
        order = list(range(len(episodes)))
        rng.shuffle(order)
        self._episodes = [episodes[i] for i in order]
        self._durations = [max(1.0, float(durations[i])) for i in order]
        self._epoch = epoch
        self._cycle = sum(self._durations)

    def at(self, when: float) -> PlayRequest:
        """What is airing at wall-clock time ``when`` (and how far into it)."""
        elapsed = (when - self._epoch) % self._cycle
        for path, dur in zip(self._episodes, self._durations):
            if elapsed < dur:
                return PlayRequest(path=path, start=elapsed)
            elapsed -= dur
        # Floating point rounding safety net.
        return PlayRequest(path=self._episodes[-1], start=0.0)


class Channel:
    """A single TV channel backed by a folder of episodes."""

    def __init__(
        self,
        config: ChannelConfig,
        episodes: Sequence[Path],
        *,
        tune_in: str = "random",
        episode_order: str = "shuffle",
        start_offset_min: float = 0.0,
        start_offset_max: Optional[float] = None,
        rng: Optional[random.Random] = None,
    ) -> None:
        self.config = config
        self.episodes: List[Path] = list(episodes)
        self.tune_in_mode = tune_in
        self.episode_order = episode_order
        # Start each episode a random number of seconds in (within this range) so
        # the picture appears already "in the show" and channel switches land at
        # varied points instead of always the same spot.
        self.start_offset_min = max(0.0, start_offset_min)
        self.start_offset_max = (
            self.start_offset_min
            if start_offset_max is None
            else max(self.start_offset_min, start_offset_max)
        )
        self._rng = rng or random.Random()
        # "shuffle" bags every episode on the channel. "sequential" bags the
        # SHOWS instead and walks each one's episodes in order - which show you
        # get stays a surprise, which episode of it does not.
        self._bag = None
        if self.episodes:
            if episode_order == "sequential":
                self._bag = ShowOrder(
                    self.episodes,
                    key=lambda p: show_name_for(p, self.config.path) or p.parent.name,
                    rng=self._rng,
                )
            else:
                self._bag = ShuffleBag(self.episodes, self._rng)
        # Resume state (used by the "resume" tune-in mode).
        self._resume_path: Optional[Path] = None
        self._resume_position: float = 0.0
        # Broadcast schedule (built lazily on first use in "broadcast" mode).
        self._broadcast: Optional[BroadcastSchedule] = None

    # -- identity -----------------------------------------------------------
    @property
    def number(self) -> int:
        return self.config.number

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def is_empty(self) -> bool:
        return not self.episodes

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Channel {self.number} {self.name!r} ({len(self.episodes)} eps)>"

    # -- playback selection -------------------------------------------------
    def _next_shuffled(self) -> PlayRequest:
        assert self._bag is not None
        if self.start_offset_max > self.start_offset_min:
            start = self._rng.uniform(self.start_offset_min, self.start_offset_max)
        else:
            start = self.start_offset_min
        return PlayRequest(path=self._bag.next(), start=start)

    def tune_in(self, *, now: Optional[float] = None) -> Optional[PlayRequest]:
        """Decide what to play the instant a viewer switches to this channel."""
        if self.is_empty:
            return None
        now = time.time() if now is None else now

        if self.tune_in_mode == "resume" and self._resume_path is not None:
            return PlayRequest(path=self._resume_path, start=self._resume_position)

        if self.tune_in_mode == "broadcast":
            schedule = self._ensure_broadcast(epoch=now)
            if schedule is not None:
                return schedule.at(now)
            # Fall through to random if the schedule could not be built.

        return self._next_shuffled()

    def peek_next(self) -> Optional[Path]:
        """Which episode tuning to this channel would play, without playing it.

        The channel guide asks every channel this, so a tile can show the
        programme you would actually GET rather than guessing.

        It must disturb nothing: no episode is drawn from the bag and no resume
        position is spent.

        🔴 IT NOW BUILDS THE BROADCAST SCHEDULE, and must. It used to refuse -
        "far too slow to do while somebody is holding a remote", which was true
        when that meant an ffprobe per episode - and fell back to the shuffle
        bag instead. But `tune_in()` DOES build the schedule, so the two
        disagreed: the guide drew the shuffle's next episode while tuning gave
        you whatever was airing on the schedule. Brian saw a Sailor Moon tile,
        pressed it, and landed on Dragon Ball Z.

        Durations are cached now (see probe.py), so building a schedule costs
        ~0.01s instead of ~68s and the compromise that forced the guide to lie
        is gone. The guide can afford to tell the truth.
        """
        if self.is_empty:
            return None
        if self.tune_in_mode == "resume" and self._resume_path is not None:
            return self._resume_path
        if self.tune_in_mode == "broadcast":
            now = time.time()
            schedule = self._ensure_broadcast(epoch=now)
            if schedule is not None:
                return schedule.at(now).path
        assert self._bag is not None
        return self._bag.peek()

    def advance(self) -> Optional[PlayRequest]:
        """Decide what to play when the current episode ends naturally."""
        if self.is_empty:
            return None
        if self.tune_in_mode == "broadcast" and self._broadcast is not None:
            # Roll straight into whatever airs next in the running order.
            return self._broadcast.at(time.time())
        return self._next_shuffled()

    def remember(self, path: Path, position: float) -> None:
        """Record where the viewer left off (for the "resume" mode)."""
        self._resume_path = path
        self._resume_position = max(0.0, position)

    # -- broadcast schedule -------------------------------------------------
    def _ensure_broadcast(self, *, epoch: float) -> Optional[BroadcastSchedule]:
        if self._broadcast is not None:
            return self._broadcast
        if self.is_empty:
            return None
        durations: List[float] = []
        for path in self.episodes:
            dur = probe_duration(path)
            durations.append(dur if dur else DEFAULT_EPISODE_SECONDS)
        # One write per channel, not one per episode. probe_duration() caches to
        # disk, so this loop is a 57-second ffprobe storm on a 493-episode
        # channel the FIRST time only - after that every lookup is a dict hit.
        # See the note at the top of probe.py: that storm blocks the main loop
        # and makes the remote appear to lag, then cascade.
        flush_cache()

        # Count from a FIXED origin shared by every channel, not from the
        # moment this one happened to be built.
        #
        # `epoch` used to be the wall-clock time of the first tune-in, which
        # quietly defeated the whole mode: a channel began its running order
        # the instant you first landed on it, so every channel opened at the
        # top of a programme, once each, in the order you visited them. The
        # comment here promised "a channel-stable epoch offset" and the code
        # never did it.
        #
        # From a fixed origin the channel has been running since long before
        # the box was switched on - which is the illusion - and it survives a
        # restart, because the origin does not move.
        #
        # The phase keeps channels out of step with each other, so they do not
        # all change programme on the same second. Derived from the channel
        # number, so it is stable across restarts too.
        cycle = sum(durations) or 1.0
        phase = (self.number * _PHASE_STRIDE) % cycle
        self._broadcast = BroadcastSchedule(
            self.episodes, durations, epoch=BROADCAST_EPOCH - phase, rng=self._rng
        )
        return self._broadcast


class ChannelLineup:
    """An ordered set of channels with remote-style navigation."""

    def __init__(self, channels: Sequence[Channel]) -> None:
        if not channels:
            raise ValueError("a lineup needs at least one channel")
        # Present channels in ascending channel-number order, like a real tuner.
        self._channels: List[Channel] = sorted(channels, key=lambda c: c.number)
        self._by_number: Dict[int, Channel] = {c.number: c for c in self._channels}
        self._index = 0

    def __len__(self) -> int:
        return len(self._channels)

    def __iter__(self):
        return iter(self._channels)

    @property
    def current(self) -> Channel:
        return self._channels[self._index]

    @property
    def numbers(self) -> List[int]:
        return [c.number for c in self._channels]

    def has_number(self, number: int) -> bool:
        return number in self._by_number

    def index_of(self, number: int) -> Optional[int]:
        for i, ch in enumerate(self._channels):
            if ch.number == number:
                return i
        return None

    def up(self) -> Channel:
        self._index = (self._index + 1) % len(self._channels)
        return self.current

    def down(self) -> Channel:
        self._index = (self._index - 1) % len(self._channels)
        return self.current

    def select_number(self, number: int) -> Optional[Channel]:
        idx = self.index_of(number)
        if idx is None:
            return None
        self._index = idx
        return self.current

    def select_index(self, index: int) -> Channel:
        self._index = index % len(self._channels)
        return self.current


def build_lineup(config: Config, *, rng: Optional[random.Random] = None) -> ChannelLineup:
    """Scan every configured channel folder and build the full lineup."""
    base_rng = rng or random.Random(config.shuffle_seed)
    channels: List[Channel] = []
    for i, ch_cfg in enumerate(config.channels):
        episodes = scan_episodes(
            ch_cfg.path,
            config.video_extensions,
            recursive=config.scan_recursive,
            exclude=ch_cfg.exclude,
            exclude_seasons=ch_cfg.exclude_seasons,
        )
        if not episodes:
            log.warning(
                "channel %s (%s) has no playable episodes in %s",
                ch_cfg.number, ch_cfg.name, ch_cfg.path,
            )
        # Give each channel its own RNG stream so they shuffle independently
        # but reproducibly when a seed is configured.
        if config.shuffle_seed is not None:
            # Derive a distinct-but-deterministic integer seed per channel.
            ch_rng = random.Random(hash((config.shuffle_seed, ch_cfg.number, i)) & 0xFFFFFFFF)
        else:
            ch_rng = random.Random()
        channels.append(
            Channel(
                ch_cfg,
                episodes,
                # A channel may override how it behaves when tuned into: a
                # station running to a schedule next to a film channel that
                # resumes. Falls back to the global setting.
                tune_in=ch_cfg.tune_in or config.tune_in,
                episode_order=ch_cfg.episode_order or config.episode_order,
                start_offset_min=config.start_offset_min,
                start_offset_max=config.start_offset_max,
                rng=ch_rng,
            )
        )
    return ChannelLineup(channels)


__all__ = [
    "Channel",
    "ChannelLineup",
    "PlayRequest",
    "BroadcastSchedule",
    "scan_episodes",
    "detect_season",
    "build_lineup",
]
