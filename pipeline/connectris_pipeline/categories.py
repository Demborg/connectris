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
from datetime import date
from pathlib import Path
from typing import Protocol

from .day import today
from .language import EN_DEVICES, Language
from .spec import label_key

#: Lives beside the pipeline rather than in the game's data — it is production state for
#: the generator, not something the app reads.
DEFAULT_POOL = Path(__file__).resolve().parents[1] / "categories.json"


def pool_for(language: str, base: Path = DEFAULT_POOL) -> Path:
    """One pool file per language: `categories.json`, `categories.sv.json`.

    Not one file with a language column. A category in the pool is a *label in a language*
    — 'Stone fruit' is not a slot a Swedish board can fill — so the two pools never share a
    row, and the only thing a shared file would buy is a filter on every read. Keeping
    English at the unsuffixed name also means the existing file and every path that names
    it keep working untouched.
    """
    return base if language == "en" else base.with_name(f"{base.stem}.{language}{base.suffix}")


#: Structural kinds. A board gets one, and `draw` walks the list from the date's own
#: ordinal — so seven of them is exactly a week of boards that differ in shape and not only
#: in subject. Adding an eighth is fine and breaks the weekly alignment, which is arguably
#: an improvement; removing one below seven means a repeat inside the same week.
#:
#: The list itself is per-language and lives in `language.py`, because the two compound
#: devices are English grammar rather than puzzle design — see the note there. Swedish has
#: eight, so its week rotates rather than aligning, which is the harmless half of the note
#: above. Re-exported under the old name so nothing that only builds English boards has to
#: know, and it is `draw`'s default for the same reason.
DEVICES: list[str] = EN_DEVICES


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


def draw(
    pool: list[Category],
    count: int,
    *,
    rng: random.Random,
    cooldown: int,
    day: str,
    devices: list[str] | None = None,
) -> tuple[list[Slot], list[Category]]:
    """Pick `count` slots out of `pool`, and say which categories were spent doing it.

    The one place the allocation rule is written down, because there are two adapters and
    a pool that rotates differently depending on where it is stored is a pool that has two
    rules. `pool` is mutated in place — the categories handed back are the same objects,
    already stamped, so an adapter only has to decide how to persist them.

    Devices cycle rather than being sampled, and the cycle is walked from a position fixed
    by the date rather than from a shuffle. Sampling with replacement is what gave one
    batch the same domain three times; sampling *without* it still wasted the list once
    boards stopped coming twenty at a time, because a night that proposes one or two takes
    only the front of a fresh shuffle and lands on about four distinct shapes a week.
    Walking from today's ordinal gives all seven, every week, for nothing.

    Themes prefer the least recently used, and fall back to an empty theme when the pool
    is too small — a board with only a device allocated is still a valid board, just a
    less constrained one.

    `devices` defaults to the English list. It is a parameter rather than a lookup because
    the rule above is about *rotation* and has nothing to say about which language's
    devices are rotating; a Swedish batch walks its own eight the same way.
    """
    devices = devices or DEVICES
    start = date.fromisoformat(day).toordinal()

    pool.sort(key=lambda c: (c.used, c.key))
    available = pool[: max(count, len(pool) - cooldown)] if pool else []
    rng.shuffle(available)

    slots: list[Slot] = []
    spent: list[Category] = []
    for i in range(count):
        theme = available[i] if i < len(available) else None
        if theme is not None:
            theme.used = day
            spent.append(theme)
        slots.append(
            Slot(device=devices[(start + i) % len(devices)], theme=theme.label if theme else "")
        )
    return slots, spent


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
    #: Whose devices to cycle. The pool holds themes; the device list is the language's.
    devices: list[str] = field(default_factory=lambda: list(EN_DEVICES))

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
        pool = self._load()
        slots, _ = draw(
            pool, count, rng=rng, cooldown=self.cooldown, day=today(), devices=self.devices
        )
        if pool:
            self._save(pool)
        return slots


def source_for(language: Language, base: Path = DEFAULT_POOL) -> JsonCategorySource:
    """The pool and the device list that go with one language."""
    return JsonCategorySource(pool_for(language.code, base), devices=list(language.devices))
