"""Commercial breaks between episodes.

Real television did not roll one episode straight into the next: it went to a
break first. This module owns that break, and nothing else. It knows where the
commercials live, hands them out in a sensible order, and assembles a break of
roughly the right *length*.

Length rather than count, deliberately. Adverts of the era run anywhere from 15
to 60 seconds, so "play three ads" produces a break of 45 seconds one time and
three minutes the next. Filling a target duration instead gives the steady
rhythm a real break had, and naturally works out at two or three clips.

Durations come from ffprobe, and are probed **lazily** - only for the clips
actually drawn, and cached afterwards. Probing the whole folder at start-up (as
the "broadcast" tune-in mode does for episodes) would add seconds to the boot of
a box whose entire appeal is coming on instantly.

The pool degrades quietly at every step. No folder, an empty folder, or no
ffprobe all leave the box working exactly as it did before.
"""

from __future__ import annotations

import logging
import random
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

from .channel import scan_episodes
from .playlist import ShuffleBag
from .probe import probe_duration

log = logging.getLogger(__name__)

# Assumed length of a clip we could not probe. Most adverts of this era are 30s.
DEFAULT_CLIP_SECONDS = 30.0

# Hard ceiling on clips in one break, so a folder of five-second bumpers cannot
# produce an endless break while chasing the target duration.
MAX_CLIPS_PER_BREAK = 6


class CommercialPool:
    """A folder of adverts, and the ability to assemble a break from it."""

    def __init__(
        self,
        path: Optional[Path],
        *,
        break_seconds: float = 75.0,
        break_ratio: float = 0.0,
        extensions: Sequence[str] = (".mp4", ".mkv", ".avi", ".m4v"),
        enabled: bool = True,
        recursive: bool = True,
        rng: Optional[random.Random] = None,
        probe: Callable[[Path], Optional[float]] = probe_duration,
        max_clips: int = MAX_CLIPS_PER_BREAK,
    ) -> None:
        self._break_seconds = max(0.0, float(break_seconds))
        self._break_ratio = max(0.0, float(break_ratio))
        self._probe = probe
        self._max_clips = max(1, int(max_clips))
        self._durations: Dict[Path, float] = {}
        self._clips: List[Path] = []
        self._bag: Optional[ShuffleBag[Path]] = None

        if not enabled or path is None or self._break_seconds <= 0:
            return

        root = Path(path).expanduser()
        if not root.is_dir():
            log.info("no commercials folder at %s; breaks disabled", root)
            return

        self._clips = scan_episodes(root, extensions, recursive=recursive)
        if not self._clips:
            log.info("commercials folder %s has no playable clips", root)
            return

        self._bag = ShuffleBag(self._clips, rng=rng)
        log.info("commercials: %d clips from %s", len(self._clips), root)

    @property
    def is_available(self) -> bool:
        """True when a break can actually be assembled."""
        return self._bag is not None

    def __len__(self) -> int:
        return len(self._clips)

    def _duration_of(self, clip: Path) -> float:
        """Length of ``clip`` in seconds, probed once and remembered."""
        cached = self._durations.get(clip)
        if cached is not None:
            return cached
        probed = self._probe(clip)
        seconds = probed if probed and probed > 0 else DEFAULT_CLIP_SECONDS
        self._durations[clip] = seconds
        return seconds

    def _target_for(self, episode_seconds: Optional[float]) -> float:
        """How much advertising to aim for after an episode of this length.

        With ``break_ratio`` left at zero every break is ``break_seconds``,
        which is how the box behaved before this existed. Set it, and the break
        scales with the programme: a seven-minute cartoon segment gets a short
        break, a twenty-minute episode gets the longer one a real station would
        have sold. ``break_seconds`` becomes the floor rather than the answer,
        so a very short programme is never followed by a token five seconds.
        """
        if self._break_ratio <= 0 or not episode_seconds or episode_seconds <= 0:
            return self._break_seconds
        return max(self._break_seconds, float(episode_seconds) * self._break_ratio)

    def _something_fits(self, allowance: float) -> bool:
        """Is any advert short enough for ``allowance``?

        Stops at the first one that is, so in normal use this probes a single
        clip and returns. Only a folder where nothing fits costs a probe per
        clip, and that answer is then cached for good.
        """
        return any(self._duration_of(clip) <= allowance for clip in self._clips)

    def _draw_that_fits(self, remaining: float, *, must_return: bool) -> Optional[Path]:
        """The next advert short enough for the time left, or None.

        Overshooting by up to ``break_seconds`` is fine - a thirty-second advert
        finishing a break with five seconds left is exactly what television did.
        Overshooting by more is not: it is what turns a nine-minute compilation
        into the entire break. Clips passed over go back in the bag rather than
        being counted as aired.

        ``must_return`` is set for the first clip of a break, where returning
        nothing would mean no break at all. If every advert is too long - a
        folder of nothing but compilations, or a ``break_seconds`` smaller than
        any clip - the filter steps aside entirely rather than blocking breaks.
        """
        allowance = remaining + self._break_seconds
        if not self._something_fits(allowance):
            # Every advert in the folder is longer than the break allows. Draw
            # normally rather than sifting: sifting would drain the bag and put
            # it back reordered, quietly wrecking the every-advert-before-any-
            # repeats guarantee for no benefit.
            return self._bag.next() if must_return else None
        passed_over: List[Path] = []
        seen: set = set()
        clip: Optional[Path] = None
        for _ in range(len(self._clips)):
            candidate = self._bag.next()
            if self._duration_of(candidate) <= allowance:
                clip = candidate
                break
            # The search can outlast the bag, which reshuffles and hands the
            # same over-long clip out again. Putting it back twice would breed
            # duplicates in the queue until they crowded out the usable ads.
            if candidate not in seen:
                seen.add(candidate)
                passed_over.append(candidate)
        if clip is None and must_return and passed_over:
            # Nothing fits at all. Take what the bag offered first, which is
            # exactly what it would have handed out before any of this existed,
            # so the every-advert-before-repeats order is left undisturbed.
            clip = passed_over.pop(0)
        for skipped in passed_over:
            self._bag.put_back(skipped)
        return clip

    def build_break(self, episode_seconds: Optional[float] = None) -> List[Path]:
        """Assemble a break to suit the episode that just finished.

        Draws clips until the target length is reached, capped both by the size
        of the library (so a small folder cannot repeat inside one break) and by
        ``max_clips``. Returns an empty list when no break is possible, which
        the caller should treat as "go straight to the next episode".
        """
        if self._bag is None:
            return []

        target = self._target_for(episode_seconds)
        limit = min(self._max_clips, len(self._clips))
        chosen: List[Path] = []
        total = 0.0
        while len(chosen) < limit and total < target:
            clip = self._draw_that_fits(target - total, must_return=not chosen)
            if clip is None:
                break
            chosen.append(clip)
            total += self._duration_of(clip)
        log.debug("commercial break: %d clips, %.0fs (target %.0fs)",
                  len(chosen), total, target)
        return chosen


__all__ = ["CommercialPool", "DEFAULT_CLIP_SECONDS", "MAX_CLIPS_PER_BREAK"]
