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

from .channel import scan_episodes, show_name_for
from .guide import DEFAULT_DIM, _MARGIN_X, _MARGIN_Y
from .overlay import CANVAS_H, CANVAS_W, _escape, _filled_rect, _style

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
    def cursor(self) -> int:
        return self._cursor[self._depth]

    @property
    def title(self) -> str:
        """Breadcrumb: where in the tree the list being shown sits."""
        if self._depth == 0 or not self._tree:
            return "Todo"
        chan = self._tree[self._cursor[0]][0]
        if self._depth == 1:
            return chan
        shows = self._shows()
        show = shows[self._cursor[1]][0] if shows else ""
        return f"{chan}  >  {show}"

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


def tree_from_config(config) -> List[Channel]:
    """Build the browse tree from the real lineup.

    ``<channel>/<show>/<episode>`` on disk becomes channel -> show -> episode
    here, reusing the same two helpers the shuffling side uses so the browser
    can never disagree with what actually plays: :func:`scan_episodes` applies
    each channel's own exclude rules, and :func:`show_name_for` decides which
    programme a file belongs to.

    Two judgements worth stating, because neither is forced by the data:

    * A channel with nothing on it is LEFT OUT. An empty row is useless to
      someone browsing for something to watch, where on the guide it still has
      to exist because it holds a number.
    * An episode sitting loose in a channel folder, with no show folder around
      it, is grouped under the CHANNEL's name rather than dropped - otherwise
      it would be unreachable from here while still playing on shuffle.
    """
    tree: List[Channel] = []
    for chan in config.channels:
        episodes = scan_episodes(
            chan.path,
            config.video_extensions,
            recursive=getattr(config, "scan_recursive", True),
            exclude=chan.exclude,
            exclude_seasons=chan.exclude_seasons,
        )
        if not episodes:
            continue
        grouped: dict = {}
        for ep in episodes:
            name = show_name_for(ep, chan.path) or chan.name
            # _staging, _split, _review and the like hold work in progress.
            # They are real folders of real video files, so nothing else
            # filters them out - but a half-processed episode must not be
            # offered as something to watch.
            if name.startswith("_"):
                continue
            grouped.setdefault(name, []).append(ep)
        shows: List[Show] = [
            (name, sorted(eps, key=str)) for name, eps in sorted(grouped.items())
        ]
        tree.append((chan.name, shows))
    return tree


# How many rows fit on one page. Height, not taste: the rows have to be legible
# from a sofa, and a 44px row on a 720-tall canvas is about the smallest that
# is. Kim Possible has 81 episodes, so paging is needed from the first draw
# rather than as a later addition.
ROW_H = 44
ROWS_PER_PAGE = 12
_HEADING_SIZE = 34
_ROW_SIZE = 28


def list_ass(title: str, items: Sequence, cursor: int, ui, *,
             dim: float = DEFAULT_DIM) -> str:
    """Draw ONE PAGE of a list: scrim, heading, rows, and where you are.

    A pure function of (title, items, cursor), like :func:`guide.guide_ass`, so
    it can be tested without a player or a television.

    Rows rather than tiles. The guide uses tiles because a pre-reader picks a
    channel by its picture; this is for an adult reading episode names, and a
    list of names is what reads fastest.

    The page follows the CURSOR rather than starting at the top, or selecting
    episode 70 of 81 would draw episodes 1-12 and hide the very thing that is
    selected.
    """
    labels = [x.stem if isinstance(x, Path) else str(x) for x in items]
    page = max(0, cursor) // ROWS_PER_PAGE
    first = page * ROWS_PER_PAGE
    window = labels[first:first + ROWS_PER_PAGE]

    parts = [
        # The programme keeps playing underneath rather than being covered.
        _filled_rect(x=0, y=0, w=CANVAS_W, h=CANVAS_H, fill="&H00000000",
                     alpha=round(255 * (1.0 - max(0.0, min(1.0, dim)))))
    ]
    y = _MARGIN_Y
    parts.append(
        rf"{{\an7\pos({_MARGIN_X},{y}){_style(ui, size=_HEADING_SIZE)}}}{_escape(title)}"
    )
    y += int(ROW_H * 1.6)

    if not labels:
        parts.append(
            rf"{{\an7\pos({_MARGIN_X},{y}){_style(ui, size=_ROW_SIZE, alpha=140)}}}"
            + _escape("(nothing here)")
        )
        return "\n".join(parts)

    for i, label in enumerate(window):
        selected = (first + i) == cursor
        # The cursor row is full brightness with a marker; the rest are dimmed.
        # A marker as well as brightness, because on a CRT-shaded picture
        # brightness alone is not always enough to tell which row is which.
        alpha = 0 if selected else 130
        text = ("> " if selected else "   ") + label
        parts.append(
            rf"{{\an7\pos({_MARGIN_X},{y}){_style(ui, size=_ROW_SIZE, alpha=alpha)}}}"
            + _escape(text)
        )
        y += ROW_H

    if len(labels) > ROWS_PER_PAGE:
        # Without this there is no way to tell "12 of 81" from "12 of 12".
        parts.append(
            rf"{{\an3\pos({CANVAS_W - _MARGIN_X},{CANVAS_H - _MARGIN_Y})"
            rf"{_style(ui, size=24, alpha=110)}}}{cursor + 1} / {len(labels)}"
        )
    return "\n".join(parts)
