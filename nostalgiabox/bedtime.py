"""Winding the evening down: when the ✱ button should sign the box off.

The rule is one sentence:

    Stop at the end of this programme, or after :data:`CAP`, whichever comes
    sooner - except that anything running :data:`FINISH_UNDER` or less is
    always allowed to finish.

Nothing here decides whether it is watching a film or an episode, because it
does not need to. An earlier design tried to infer that from duration and tied
itself in knots; once the box could ask how long was left, the distinction
stopped mattering. A 22-minute episode finishes because it is short, not
because it is an episode.
"""

from __future__ import annotations

from typing import Optional, Set

#: Longest you ever wait after pressing the button, for anything too long to
#: be allowed to finish. Bedtime has to be decisive.
CAP = 15 * 60

#: A programme this length or shorter always runs to its end, so a child gets
#: an ending rather than a cut. Covers the normal 20-25 minute episode.
FINISH_UNDER = 25 * 60

#: Minutes before sign-off at which to warn. A shrinking number is learnable
#: by repetition long before reading is, and it gives a grown-up something to
#: point at while saying "five more minutes" out loud.
MARKS = (15, 10, 5, 3, 2, 1)


def deadline_for(
    now: float, *, position: float, runtime: Optional[float]
) -> float:
    """When the box should sign off, given what is playing right now."""
    if runtime is None or runtime <= 0:
        # An unknowable length - the no-signal static loops forever - cannot
        # be allowed to finish, because it never would.
        return now + CAP
    remaining = max(0.0, runtime - position)
    if runtime <= FINISH_UNDER:
        return now + remaining
    return now + min(remaining, CAP)


def initial_marks(remaining: float) -> Set[int]:
    """Marks to treat as already spent, so past ones do not all fire at once.

    Pressing with eight minutes left should count 5, 3, 2, 1 - not announce a
    fifteen and a ten that have already gone. A mark reached exactly is NOT
    spent, so pressing on the quarter hour still announces it.
    """
    return {m for m in MARKS if m * 60 > remaining}


def due_mark(remaining: float, spent: Set[int]) -> Optional[int]:
    """The largest unspent mark this moment has reached, if any."""
    for mark in MARKS:
        if mark not in spent and remaining <= mark * 60:
            return mark
    return None


__all__ = [
    "CAP",
    "FINISH_UNDER",
    "MARKS",
    "deadline_for",
    "initial_marks",
    "due_mark",
]
