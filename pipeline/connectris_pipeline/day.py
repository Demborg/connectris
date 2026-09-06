"""Days, as the schedule counts them.

The Python half of `src/lib/server/day.ts`, and it has to agree with it: the generator
writes `liveOn` and the game reads it, so a disagreement about what today is called is a
day with two boards or none.

UTC, and deliberately not anyone's local time. A board is served by being the most recent
one dated on or before today, so the timezone decides what hour the board changes, not
whether there is one. UTC keeps that hour the same for every player, the same as the one
Cloud Scheduler fires in, and free of anything that happens twice a year.

A day is a `YYYY-MM-DD` string rather than a `date` because it crosses a wire as a string,
sorts as one, and is compared as one by the Firestore index the game reads it through.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


def today() -> str:
    """The day now falls on."""
    return datetime.now(UTC).date().isoformat()


def shift(day: str, days: int) -> str:
    """`days` after `day` — negative to go back."""
    return (datetime.fromisoformat(day).date() + timedelta(days=days)).isoformat()
