"""Randomized, no-boring-repeats playlist ordering.

Old TV was appointment viewing on a schedule; this box instead plays each
channel on an endless shuffle. A naive "pick a random file every time" feels
wrong: it will happily play the same episode twice in a row and can go a long
time without touching some episodes. A *shuffle bag* fixes both problems.

The bag holds one copy of every episode. It hands them out in a random order
until the bag is empty, then refills and reshuffles - guaranteeing every
episode plays once before any repeats (just like dragging a season into a music
player and hitting "shuffle"). When it refills, it also makes sure the first
episode of the new shuffle is not the same as the last one played, so you never
see the same episode back-to-back across a cycle boundary.
"""

from __future__ import annotations

import random
from typing import Callable, Dict, Generic, List, Optional, Sequence, TypeVar

T = TypeVar("T")


class ShuffleBag(Generic[T]):
    """Yields items in a random order, once each, then reshuffles."""

    def __init__(self, items: Sequence[T], rng: Optional[random.Random] = None) -> None:
        self._items: List[T] = list(items)
        self._rng = rng or random.Random()
        self._queue: List[T] = []
        self._last: Optional[T] = None
        self._refill()

    def __len__(self) -> int:
        return len(self._items)

    @property
    def is_empty(self) -> bool:
        return not self._items

    def _refill(self) -> None:
        self._queue = list(self._items)
        self._rng.shuffle(self._queue)
        # Avoid an immediate repeat across the cycle boundary: if the first
        # item of the fresh shuffle is what we just played, and there is more
        # than one item, swap it deeper into the queue.
        if (
            len(self._queue) > 1
            and self._last is not None
            and self._queue[-1] == self._last
        ):
            # _last would be the *next* item popped (we pop from the end), so
            # move it to the front of the play order instead.
            self._queue.insert(0, self._queue.pop())

    def next(self) -> T:
        """Return the next item, refilling the bag if it has been exhausted."""
        if not self._items:
            raise IndexError("cannot draw from an empty ShuffleBag")
        if not self._queue:
            self._refill()
        item = self._queue.pop()
        self._last = item
        return item

    def put_back(self, item: T) -> None:
        """Return an item drawn but not used, so its turn is not spent.

        A commercial break passes over an advert too long for the time it has
        left. Without this the clip would count as aired, and the "every advert
        before any repeats" guarantee would quietly start skipping the long
        ones for a whole cycle.
        """
        # next() pops from the END of the queue, so an item appended there
        # would be handed straight back on the very next draw - the caller
        # would see the same over-long advert forever.
        self._queue.insert(0, item)
        if self._last == item:
            self._last = None

    def peek(self) -> T:
        """The item :meth:`next` will hand out, without handing it out.

        The channel guide uses this to show which programme a channel would
        play if you tuned to it - so a tile can promise what you will actually
        get. Refills an exhausted bag exactly as :meth:`next` would, so the
        answer stays true at a cycle boundary rather than raising.
        """
        if not self._items:
            raise IndexError("cannot draw from an empty ShuffleBag")
        if not self._queue:
            self._refill()
        return self._queue[-1]

    def peek_remaining(self) -> int:
        """How many items are left before the next reshuffle (for debugging)."""
        return len(self._queue)


__all__ = ["ShuffleBag"]

class ShowOrder(Generic[T]):
    """Shuffles SHOWS; plays each show's episodes in order.

    A channel used to be one shuffle bag of every episode on it, so a child
    could get episode 7, then 2, then 19 of the same series. Fully sequential
    is not the fix either - all of one show and then all of the next is a box
    set, not a channel.

    So the bag holds shows. Drawing one hands back that show's next episode in
    order and moves its cursor on, wrapping when the show runs out. Which show
    you get stays a surprise; which episode of it does not.

    Every guarantee the plain bag gives now applies at the SHOW level: each
    show appears once before any repeats, and the same show never comes twice
    in a row while the channel has more than one.
    """

    def __init__(
        self,
        items: Sequence[T],
        *,
        key: Callable[[T], str],
        rng: Optional[random.Random] = None,
    ) -> None:
        grouped: Dict[str, List[T]] = {}
        for item in items:
            grouped.setdefault(key(item), []).append(item)
        # Sorted by name, not by the order the directory happened to list them
        # in - S01E01 has to come first however the filesystem felt about it.
        self._shows: Dict[str, List[T]] = {
            name: sorted(eps, key=str) for name, eps in grouped.items()
        }
        self._cursor: Dict[str, int] = {name: 0 for name in self._shows}
        self._count = sum(len(eps) for eps in self._shows.values())
        self._bag: ShuffleBag[str] = ShuffleBag(sorted(self._shows), rng=rng)

    def __len__(self) -> int:
        return self._count

    @property
    def is_empty(self) -> bool:
        return self._count == 0

    def next(self) -> T:
        """The next episode: a fresh show, at whatever point it had reached."""
        if self.is_empty:
            raise IndexError("cannot draw from an empty ShowOrder")
        show = self._bag.next()
        episodes = self._shows[show]
        index = self._cursor[show] % len(episodes)
        self._cursor[show] = (index + 1) % len(episodes)
        return episodes[index]

    def peek(self) -> T:
        """What :meth:`next` would hand out, without spending it.

        The guide asks every channel this so a tile can promise what you would
        actually get, and it must disturb nothing - neither the show bag nor
        any show's place in its own run.
        """
        if self.is_empty:
            raise IndexError("cannot draw from an empty ShowOrder")
        show = self._bag.peek()
        episodes = self._shows[show]
        return episodes[self._cursor[show] % len(episodes)]
