"""The category pool: what a board is allowed to be about, decided before it is written.

Dedupe used to happen at the end — generate twenty boards, then notice two of them used
the same category. That is wasteful twice over: the proposer had already spent its
thinking tokens, and the check only caught *identical* categories, never merely similar
ones. Allocating slots up front moves novelty from a filter to a constraint.

`CategorySource` is the port. `JsonCategorySource` is the adapter that exists; a Postgres
one is the reason this is a protocol rather than a class, because the pool is exactly the
kind of thing that wants a real database the moment there is more than one machine.

Two slots per board are allocated: one device (a structural kind — `___ WORD`, homophones)
and one concrete theme. The proposer invents the other three and has to make them collide
with the two it was given. Prescribing all five was the alternative and was rejected: the
interference between categories is where board quality comes from, and the pool cannot see
words, so it cannot judge interference.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from .spec import label_key

#: Lives beside the pipeline rather than in the game's data — it is production state for
#: the generator, not something the app reads.
DEFAULT_POOL = Path(__file__).resolve().parents[1] / "categories.json"

#: Structural kinds. A board gets one, and the pool avoids repeating one too soon, so a
#: week of boards differs in shape rather than only in subject.
DEVICES: list[str] = [
    "a ___ WORD compound, where all four words take the same following word",
    "a WORD ___ compound, where all four words take the same preceding word",
    "four words that each contain a smaller hidden word of the same kind",
    "four words that are homophones of something else entirely",
    "four members of an ordered set (ranks, sizes, stages)",
    "four words that all mean roughly the same thing",
    "four words that are all a specific kind of noun with an everyday second meaning",
]


@dataclass(frozen=True)
class Slot:
    """What a board is told to build. `theme` is empty when only a device was allocated."""

    device: str
    theme: str = ""


@dataclass
class Category:
    """One banked concrete category. `label` is what a player would read."""

    label: str
    #: What the category narrows *from* — the wider reading it will be mistaken for. This
    #: is the trap, and it is a property of the category, not of any word.
    reads_as: str = ""
    #: ISO date it was last handed out, so recently-used themes can be held back.
    used: str = ""

    @property
    def key(self) -> str:
        return label_key(self.label)


class CategorySource(Protocol):
    """The port. Everything the pipeline needs from a pool of categories."""

    def allocate(self, count: int, *, rng: random.Random) -> list[Slot]:
        """`count` slots, distinct within the batch and held back from recent use."""
        ...

    def bank(self, categories: list[Category]) -> int:
        """Add newly invented categories, skipping near-duplicates. Returns how many stuck."""
        ...

    def known(self) -> list[Category]:
        """Everything in the pool, for prompting an inventor about what already exists."""
        ...


@dataclass
class JsonCategorySource:
    """A file-backed pool. Small enough to read whole, and diffable in review.

    Similarity is lexical, deliberately. `label_key` already folds ordering and
    punctuation, so '___ BOARD' and 'board ___' collide; the remaining gap is synonyms,
    which an embedding would close at the cost of a network call per category. Not worth
    it until the pool is big enough that a human stops recognising duplicates on sight.
    """

    path: Path
    #: A theme is not offered again until this many boards have been drawn since.
    cooldown: int = 60

    _cache: list[Category] | None = field(default=None, init=False, repr=False)

    def _load(self) -> list[Category]:
        if self._cache is None:
            raw = json.loads(self.path.read_text()) if self.path.exists() else []
            self._cache = [Category(**c) for c in raw]
        return self._cache

    def _save(self, categories: list[Category]) -> None:
        self._cache = categories
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps([c.__dict__ for c in categories], indent="\t", ensure_ascii=False) + "\n"
        )

    def known(self) -> list[Category]:
        return list(self._load())

    def bank(self, categories: list[Category]) -> int:
        have = self._load()
        seen = {c.key for c in have}
        fresh = []
        for c in categories:
            if c.key and c.key not in seen:
                seen.add(c.key)
                fresh.append(c)
        if fresh:
            self._save(have + fresh)
        return len(fresh)

    def allocate(self, count: int, *, rng: random.Random) -> list[Slot]:
        """One device and one theme per board, both spread as widely as the pool allows.

        Devices cycle rather than being sampled, because sampling with replacement is
        what gave one batch the same domain three times. Themes prefer the least recently
        used, and fall back to an empty theme when the pool is too small — a board with
        only a device allocated is still a valid board, just a less constrained one.
        """
        devices = list(DEVICES)
        rng.shuffle(devices)

        pool = sorted(self._load(), key=lambda c: (c.used, c.key))
        available = pool[: max(count, len(pool) - self.cooldown)] if pool else []
        rng.shuffle(available)

        today = datetime.now(UTC).date().isoformat()
        slots = []
        for i in range(count):
            theme = available[i] if i < len(available) else None
            if theme is not None:
                theme.used = today
            slots.append(Slot(device=devices[i % len(devices)], theme=theme.label if theme else ""))

        if pool:
            self._save(pool)
        return slots
