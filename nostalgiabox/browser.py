"""Adult mode: browse channel -> show -> episode and pick one to watch.

The box is built to be operated by someone who cannot read: one button, a
random episode, no decisions. This is the opposite - it is for the adult who
wants a particular episode of a particular show, with no commercial break.

Pure state, exactly like :class:`~nostalgiabox.guide.Guide` - no player, no
clock, no drawing - so every movement rule is testable with no television
attached, and the thing that draws it can be replaced without touching this.

One rule differs from the Guide deliberately. The Guide works hard to ensure
every move from every position lands on a real channel, because a cursor parked
on nothing reads as a broken television to a 2-year-old. Here the user can
read, so a list simply STOPS at its ends rather than wrapping - looping a list
silently is more confusing to someone who is trying to reach the bottom of it.

What must hold instead: you can always get back out, from any depth.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Sequence, Tuple, Union

# channel name -> shows -> episode paths
Show = Tuple[str, Sequence[Path]]
Channel = Tuple[str, Sequence[Show]]

_LEVELS = ("channel", "show", "episode")


class Browser:
    """Where the cursor is in the channel -> show -> episode tree."""

    def __init__(self, tree: Sequence[Channel]) -> None:
        self._tree: List[Channel] = list(tree)
        self._depth = 0
        # One cursor per level, kept when descending so that coming back up
        # returns you to where you were rather than to the top of the list.
        self._cursor = [0, 0, 0]

    # -- where are we -------------------------------------------------------

    @property
    def level(self) -> str:
        return _LEVELS[self._depth]

    @property
    def items(self) -> list:
        """The list being shown at the current depth."""
        if self._depth == 0:
            return [name for name, _ in self._tree]
        shows = self._shows()
        if self._depth == 1:
            return [name for name, _ in shows]
        return list(self._episodes())

    @property
    def current_label(self) -> Optional[str]:
        items = self.items
        if not items:
            return None
        item = items[min(self._cursor[self._depth], len(items) - 1)]
        return item.stem if isinstance(item, Path) else item

    def _shows(self) -> Sequence[Show]:
        if not self._tree:
            return []
        return self._tree[self._cursor[0]][1]

    def _episodes(self) -> Sequence[Path]:
        shows = self._shows()
        if not shows:
            return []
        return shows[self._cursor[1]][1]

    # -- moving -------------------------------------------------------------

    def up(self) -> None:
        self._cursor[self._depth] = max(0, self._cursor[self._depth] - 1)

    def down(self) -> None:
        last = max(0, len(self.items) - 1)
        self._cursor[self._depth] = min(last, self._cursor[self._depth] + 1)

    def enter(self) -> Union[Path, None]:
        """Descend a level, or return the chosen episode.

        Returns the episode's path when one is picked, and None otherwise -
        including when there is nothing to descend into, which leaves the
        cursor exactly where it was rather than dropping into an empty list.
        """
        if self._depth == 2:
            episodes = self._episodes()
            if not episodes:
                return None
            return episodes[min(self._cursor[2], len(episodes) - 1)]
        deeper = self._shows() if self._depth == 0 else self._episodes()
        if not deeper:
            return None
        self._depth += 1
        self._cursor[self._depth] = 0
        return None

    def back(self) -> bool:
        """Go up a level. False when already at the top, meaning 'close me'."""
        if self._depth == 0:
            return False
        self._depth -= 1
        return True

    # -- what plays next ----------------------------------------------------

    def next_episode(self) -> Optional[Path]:
        """The episode after the one selected, or None at the end of a show.

        Adult mode plays a show in order rather than shuffling, so this is what
        the app asks for when one finishes.
        """
        episodes = self._episodes()
        nxt = self._cursor[2] + 1
        return episodes[nxt] if 0 <= nxt < len(episodes) else None

    def advance(self) -> Optional[Path]:
        """Move to the next episode and return it, for continuous play."""
        nxt = self.next_episode()
        if nxt is not None:
            self._cursor[2] += 1
        return nxt
