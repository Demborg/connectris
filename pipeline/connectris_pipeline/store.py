"""The game's own database, as the generator sees it.

Three questions and one answer. What has been published — which is both the dedupe corpus
and the schedule — whether anyone has actually played the board that is up, and here is
tomorrow's board. Nothing else: the generator is a reader of two collections and a writer
of one, and everything it *decides* is decided in `nightly.py` from what these return.

`GameStore` is the port. `FirestoreStore` is the adapter that ships and `MemoryStore` is
the one the tests use, and the second exists so the first cannot quietly become the
definition. The shapes it reads and writes are `PuzzleDoc` and `RunRecord` in
`src/lib/server/firestore.ts` and `src/lib/server/ports.ts`; that file and this one are
the two ends of the same wire and neither imports the other, so they are kept in step by
`tests/test_store.py`, which reads the declaration at the other end, and by the field
names being written out here in full rather than mapped from a shared shape.

`FirestoreCategories` is here too, and it is not part of that port. It is the generator's
own state rather than the game's — a second adapter for `CategorySource`, in the database
because a Cloud Run task's disk does not outlive the task. It lives in this file because
this is where the knowledge of Firestore is kept.

The SDK import is inside `connect` on purpose: the package must stay importable, and the
whole offline test suite must stay runnable, on a machine that has no database client and
no credentials.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from .categories import Category, Slot, draw
from .day import today
from .spec import Corpus, Puzzle

if TYPE_CHECKING:
    from google.cloud.firestore import Client

#: Collection names. The first two mirror `collections` in src/lib/server/firestore.ts;
#: the third is the generator's own state, which the game never reads.
PUZZLES = "puzzles"
RUNS = "runs"
CATEGORIES = "categories"


@dataclass(frozen=True)
class Published:
    """A board and the day it is due. Dated ahead of today means written but not playable."""

    puzzle: Puzzle
    live_on: str


class GameStore(Protocol):
    def schedule(self) -> list[Published]:
        """Every board the game holds, oldest day first, whether or not it is due yet."""
        ...

    def finished_runs(self, puzzle_id: str, *, since_ms: int) -> int:
        """Completed attempts at one board that began at or after `since_ms`.

        Completed, not started: the client posts a run from `finish()` and nowhere else,
        so a record here is a player who saw the board through to a win or a loss. The
        window is the point of the method — "has anyone ever played this" would stay true
        forever once it was true once, and a generator gated on it would keep spending
        long after the last player left.
        """
        ...

    def publish(self, puzzle: Puzzle, *, live_on: str, source: str) -> None:
        """Put a board into the game, due on `live_on`. Keyed by id, so it is idempotent."""
        ...


def corpus_of(schedule: list[Published]) -> Corpus:
    """What a new board has to be new against: every board already written, due or not.

    Boards dated ahead count. Tomorrow's board is written tonight and is as much a repeat
    to avoid as one from last year — more so, since the player would meet them two days
    apart.
    """
    corpus = Corpus()
    for entry in schedule:
        corpus.extend(entry.puzzle)
    return corpus


def connect(project: str) -> Client:
    """A client for the game's database.

    Imported here rather than at the top so the package stays importable, and the whole
    offline suite stays runnable, on a machine with no database client and no credentials.
    Not over REST, unlike the game's own client: `preferRest` there is a cold-start
    argument, and this is a batch job that runs for minutes.
    """
    from google.cloud import firestore

    return firestore.Client(project=project)


class FirestoreStore:
    """Firestore, the same database the game reads."""

    def __init__(self, client: Client) -> None:
        self._db = client

    def schedule(self) -> list[Published]:
        # The whole collection, ordered. A board a day is a few hundred documents a year,
        # against a free tier of fifty thousand reads a day, and the alternative — reading
        # a window — would silently stop deduping against anything older than the window.
        found = self._db.collection(PUZZLES).order_by("liveOn").stream()
        # `to_dict()` is typed as nullable because a snapshot can describe a document that
        # is not there; one that came out of a stream always is, and `or {}` says so
        # without a cast.
        return [
            Published(
                puzzle=Puzzle.from_game_json({"id": doc.id, **data}),
                live_on=str(data.get("liveOn", "")),
            )
            for doc in found
            if (data := doc.to_dict() or {})
        ]

    def finished_runs(self, puzzle_id: str, *, since_ms: int) -> int:
        from google.cloud.firestore_v1.base_query import FieldFilter

        # Filtered on `startedAt` alone, then narrowed in Python. Asking Firestore for
        # both conditions would want a composite index — a thing to declare, deploy and
        # forget — and the range on its own already bounds the read to however much was
        # played recently, which for this game is a handful of documents.
        recent = (
            self._db.collection(RUNS)
            .where(filter=FieldFilter("startedAt", ">=", since_ms))
            .limit(500)
            .stream()
        )
        return sum(
            1
            for doc in recent
            if (run := doc.to_dict() or {}).get("puzzle") == puzzle_id
            and run.get("outcome") in {"won", "lost"}
        )

    def publish(self, puzzle: Puzzle, *, live_on: str, source: str) -> None:
        # Written field by field rather than from `to_game_json`, because the document is
        # not the game's JSON: the id lives in the path and the schedule lives here. This
        # is `puzzleDoc` in src/lib/server/firestore.ts, and the two have to agree.
        self._db.collection(PUZZLES).document(puzzle.id).set(
            {
                "name": puzzle.name,
                "language": puzzle.language,
                "groups": [
                    {"id": g.id, "label": g.label, "words": list(g.words)} for g in puzzle.groups
                ],
                "liveOn": live_on,
                "source": source,
            }
        )


@dataclass
class MemoryStore:
    """The port's second adapter, so the port is a port. Also what the tests run against."""

    #: Boards already in the game, in any order. `schedule` sorts them.
    boards: list[Published]
    #: (puzzle id, startedAt in ms) for every completed attempt on record.
    runs: list[tuple[str, int]]

    def __init__(
        self,
        boards: list[Published] | None = None,
        runs: list[tuple[str, int]] | None = None,
    ) -> None:
        self.boards = list(boards or [])
        self.runs = list(runs or [])

    def schedule(self) -> list[Published]:
        return sorted(self.boards, key=lambda b: b.live_on)

    def finished_runs(self, puzzle_id: str, *, since_ms: int) -> int:
        return sum(1 for pid, at in self.runs if pid == puzzle_id and at >= since_ms)

    def publish(self, puzzle: Puzzle, *, live_on: str, source: str) -> None:
        self.boards = [b for b in self.boards if b.puzzle.id != puzzle.id]
        self.boards.append(Published(puzzle=puzzle, live_on=live_on))


class FirestoreCategories:
    """The category pool, in the database, because the generator has no disk that lasts.

    `JsonCategorySource` is the adapter for a laptop: a file next to the code, diffable in
    review. A Cloud Run task's filesystem dies with the task, so a file-backed pool there
    would be re-invented from nothing every night — forty categories bought again each
    time, and a cooldown that never holds anything back because nothing is ever old.

    Which is exactly what `categories.py` predicted: "the pool is exactly the kind of thing
    that wants a real database the moment there is more than one machine". The allocation
    rule itself is not repeated here — `draw` is shared, so the pool rotates the same way
    wherever it is kept.
    """

    def __init__(self, client: Client, cooldown: int = 60) -> None:
        self._db = client
        self._cooldown = cooldown

    def _collection(self):  # noqa: ANN202 — a Firestore collection reference
        return self._db.collection(CATEGORIES)

    def known(self) -> list[Category]:
        return [
            Category(
                label=str(data.get("label", "")),
                reads_as=str(data.get("reads_as", "")),
                used=str(data.get("used", "")),
            )
            for doc in self._collection().stream()
            if (data := doc.to_dict() or {})
        ]

    def bank(self, categories: list[Category]) -> int:
        have = self.known()
        seen = {c.key for c in have}
        fresh = []
        for c in categories:
            if c.key and c.key not in seen:
                seen.add(c.key)
                fresh.append(c)

        # Keyed by the folded label, so banking the same idea twice is one document rather
        # than two — the same guard `bank` applies in memory, made durable.
        batch = self._db.batch()
        for c in fresh:
            batch.set(self._collection().document(_doc_id(c.key)), _category_doc(c))
        if fresh:
            batch.commit()
        return len(fresh)

    def allocate(self, count: int, *, rng: random.Random) -> list[Slot]:
        pool = self.known()
        slots, spent = draw(pool, count, rng=rng, cooldown=self._cooldown, day=today())
        # Only what was handed out. The file adapter rewrites the whole pool because
        # rewriting a small file is simpler than diffing it; here a write is a write.
        for c in spent:
            self._collection().document(_doc_id(c.key)).set(_category_doc(c))
        return slots


def _category_doc(category: Category) -> dict:
    return {"label": category.label, "reads_as": category.reads_as, "used": category.used}


def _doc_id(key: str) -> str:
    """A folded label as a document id: no slashes, no empties, still recognisable."""
    return key.replace("/", "-")[:200] or "unnamed"


__all__ = [
    "FirestoreCategories",
    "FirestoreStore",
    "GameStore",
    "MemoryStore",
    "Published",
    "corpus_of",
]
