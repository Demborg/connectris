"""The wire between the generator and the game.

Python writes these documents and TypeScript reads them, and nothing type-checks across
that seam — so the field names are asserted here against the file at the other end, and
the query shapes are asserted against a double. The Firestore adapters on the game's side
are held to their own contract by the emulator in CI; this is the half that CI cannot see.
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path

from conftest import BOARDS

from connectris_pipeline.categories import Category, JsonCategorySource
from connectris_pipeline.spec import Group, Notes, Puzzle, WordNote
from connectris_pipeline.store import (
    CATEGORIES,
    PUZZLES,
    RUNS,
    FirestoreCategories,
    FirestoreStore,
    GameStore,
    MemoryStore,
    Published,
    corpus_of,
)

#: pipeline/tests -> repo root
GAME_FIRESTORE = Path(__file__).resolve().parents[2] / "src" / "lib" / "server" / "firestore.ts"


def board(pid: str, rows: list[tuple[str, list[str]]] | None = None) -> Puzzle:
    rows = rows if rows is not None else BOARDS[0]
    return Puzzle(
        id=pid,
        name=f"Board {pid}",
        groups=[Group(id=label.lower(), label=label, words=list(ws)) for label, ws in rows],
    )


# --- a Firestore stand-in -------------------------------------------------------------


class FakeSnapshot:
    def __init__(self, doc_id: str, data: dict) -> None:
        self.id = doc_id
        self._data = data

    def to_dict(self) -> dict:
        return dict(self._data)


class FakeQuery:
    """Records what was asked, and answers it in memory.

    Deliberately not a Firestore simulator: it applies the one filter and the one ordering
    this module uses and nothing else, so a query that grows a clause fails here rather
    than passing against a re-implementation of a database.
    """

    def __init__(self, docs: dict[str, dict]) -> None:
        self.docs = docs
        self.ordered_by: str | None = None
        self.filters: list[tuple[str, str, object]] = []
        self.limited: int | None = None

    def order_by(self, field: str) -> FakeQuery:
        self.ordered_by = field
        return self

    # `filter` shadows the builtin because that is the keyword Firestore takes.
    def where(self, *, filter: object) -> FakeQuery:
        self.filters.append((filter.field_path, filter.op_string, filter.value))  # ty: ignore
        return self

    def limit(self, n: int) -> FakeQuery:
        self.limited = n
        return self

    def stream(self):
        rows = list(self.docs.items())
        for field, op, value in self.filters:
            assert op == ">=", f"the double only knows >=, not {op}"
            rows = [(k, v) for k, v in rows if v.get(field, 0) >= value]
        if self.ordered_by:
            rows.sort(key=lambda kv: kv[1].get(self.ordered_by, ""))
        if self.limited is not None:
            rows = rows[: self.limited]
        return (FakeSnapshot(k, v) for k, v in rows)


class FakeDocument:
    def __init__(self, collection: FakeCollection, doc_id: str) -> None:
        self._collection = collection
        self._id = doc_id

    def set(self, data: dict) -> None:
        self._collection.docs[self._id] = data

    def update(self, data: dict) -> None:
        """A merge, and only of the fields named. The distinction is the point of
        `annotate`: a board already in front of players keeps its date."""
        self._collection.docs[self._id] = {**self._collection.docs[self._id], **data}


class FakeCollection(FakeQuery):
    def document(self, doc_id: str) -> FakeDocument:
        return FakeDocument(self, doc_id)


class FakeBatch:
    def __init__(self) -> None:
        self.writes: list[tuple[FakeDocument, dict]] = []

    def set(self, doc: FakeDocument, data: dict) -> None:
        self.writes.append((doc, data))

    def commit(self) -> None:
        for doc, data in self.writes:
            doc.set(data)
        self.writes = []


class FakeClient:
    def __init__(self, **collections: dict[str, dict]) -> None:
        self.collections = {name: FakeCollection(docs) for name, docs in collections.items()}
        self.asked: list[FakeCollection] = []

    def collection(self, name: str) -> FakeCollection:
        found = self.collections.setdefault(name, FakeCollection({}))
        # A fresh view each time, so one call's filters do not leak into the next.
        view = FakeCollection(found.docs)
        self.asked.append(view)
        return view

    def batch(self) -> FakeBatch:
        return FakeBatch()


def store(**collections: dict[str, dict]) -> tuple[FirestoreStore, FakeClient]:
    client = FakeClient(**collections)
    return FirestoreStore(client), client  # ty: ignore


# --- what gets written ----------------------------------------------------------------


def test_a_published_board_is_exactly_the_document_the_game_reads():
    written, client = store()
    written.publish(board("gen-01"), live_on="2026-09-07", source="pipeline/20260906-220000")

    (doc,) = client.collections[PUZZLES].docs.items()
    doc_id, data = doc
    assert doc_id == "gen-01", "the id belongs in the path, not in the document"
    assert set(data) == {"name", "language", "groups", "liveOn", "source"}
    assert data["liveOn"] == "2026-09-07"
    assert data["groups"][0] == {
        "id": "hand tools",
        "label": "Hand tools",
        "words": ["HAMMER", "CHISEL", "PLANE", "WRENCH"],
    }


def test_notes_ride_on_the_group_they_explain():
    """The one field added to a board after it is written, and the shape both ends read.

    `Notes` in src/lib/game/types.ts is the other half of this: it hangs off `Group`, so
    the game reveals a note by exactly the rule it reveals a label — a row that is on the
    table has one and a row still in play does not.
    """
    explained = board("gen-01")
    explained.groups[0].notes = Notes(
        summary="Tools you swing or turn by hand.",
        words=[WordNote(word=w, note=f"About {w}.") for w in explained.groups[0].words],
    )
    written, client = store()
    written.publish(explained, live_on="2026-09-07", source="pipeline")

    (data,) = client.collections[PUZZLES].docs.values()
    assert data["groups"][0]["notes"] == {
        "summary": "Tools you swing or turn by hand.",
        "words": [{"word": w, "note": f"About {w}."} for w in explained.groups[0].words],
    }
    # A board from before notes existed does not grow an empty field for them.
    assert "notes" not in data["groups"][1]


def test_annotating_a_published_board_leaves_its_schedule_alone():
    """The backfill's one write. `publish` would work and would also rewrite `liveOn` and
    `source` — a job that is only adding prose must not move a board's date."""
    written, client = store(
        puzzles={"gen-01": {**board("gen-01").to_game_json(), "liveOn": "2026-09-05"}}
    )

    explained = board("gen-01")
    for g in explained.groups:
        g.notes = Notes(
            summary=f"What {g.label} is.",
            words=[WordNote(word=w, note=f"About {w}.") for w in g.words],
        )
    written.annotate(explained)

    data = client.collections[PUZZLES].docs["gen-01"]
    assert data["liveOn"] == "2026-09-05"
    assert [g["notes"]["summary"] for g in data["groups"]] == [
        f"What {g.label} is." for g in explained.groups
    ]


def test_the_document_agrees_with_the_type_the_game_declares():
    """`PuzzleDoc` in src/lib/server/firestore.ts is the other end of this wire.

    Nothing checks across the two languages, so a field renamed on one side would be a
    board that loads without a name, or one that never becomes live, discovered in
    production. Reading the declaration is cheap; the alternative is a comment asking
    someone to remember.
    """
    declared = GAME_FIRESTORE.read_text()
    body = re.search(r"export function puzzleDoc\([^)]*\): PuzzleDoc \{(.*?)\n\}", declared, re.S)
    assert body, "puzzleDoc has moved; this test is the only thing watching that seam"
    fields = set(re.findall(r"^\t\t(\w+)", body.group(1), re.M))

    written, client = store()
    written.publish(board("gen-01"), live_on="2026-09-07", source="pipeline")
    assert set(next(iter(client.collections[PUZZLES].docs.values()))) == fields


# --- what gets read -------------------------------------------------------------------


def test_the_schedule_comes_back_oldest_first_with_its_dates():
    written, _ = store(
        puzzles={
            "b": {**board("b").to_game_json(), "liveOn": "2026-09-07"},
            "a": {**board("a").to_game_json(), "liveOn": "2026-09-05"},
        }
    )
    got = written.schedule()
    assert [(p.puzzle.id, p.live_on) for p in got] == [("a", "2026-09-05"), ("b", "2026-09-07")]
    assert got[0].puzzle.groups[0].words == ["HAMMER", "CHISEL", "PLANE", "WRENCH"]


def test_the_schedule_is_ordered_by_the_field_the_game_indexes():
    written, client = store(puzzles={})
    written.schedule()
    assert client.asked[-1].ordered_by == "liveOn"


def test_only_recent_finished_attempts_at_this_board_are_counted():
    runs = {
        "r1": {"puzzle": "today", "outcome": "won", "startedAt": 5_000},
        "r2": {"puzzle": "today", "outcome": "lost", "startedAt": 6_000},
        "r3": {"puzzle": "today", "outcome": "won", "startedAt": 1_000},
        "r4": {"puzzle": "yesterday", "outcome": "won", "startedAt": 7_000},
        "r5": {"puzzle": "today", "outcome": "abandoned", "startedAt": 8_000},
    }
    written, client = store(runs=runs)
    assert written.finished_runs("today", since_ms=4_000) == 2

    # One range filter and no ordering, which is what Firestore indexes without being
    # asked. Narrowing by puzzle as well would want a composite index to declare, deploy
    # and eventually forget; the range alone already bounds the read to recent play.
    asked = client.asked[-1]
    assert asked.filters == [("startedAt", ">=", 4_000)]
    assert asked.ordered_by is None


def test_the_runs_collection_is_the_one_the_game_writes():
    assert (PUZZLES, RUNS) == ("puzzles", "runs")
    declared = GAME_FIRESTORE.read_text()
    assert f"puzzles: '{PUZZLES}'" in declared
    assert f"runs: '{RUNS}'" in declared


# --- the port -------------------------------------------------------------------------


def test_both_adapters_satisfy_the_port():
    """A protocol nobody checks is a comment. Two adapters is what makes it a seam."""
    written, _ = store()
    checked: list[GameStore] = [written, MemoryStore()]
    assert len(checked) == 2


def test_the_corpus_holds_every_board_the_game_has_including_one_dated_ahead():
    corpus = corpus_of(
        [
            Published(puzzle=board("old", BOARDS[0]), live_on="2025-01-01"),
            Published(puzzle=board("ahead", BOARDS[1]), live_on="2099-01-01"),
        ]
    )
    assert {"HAMMER", "KETCH"} <= corpus.words
    # `label_key` sorts the words in a label, so this is "Sailing boats" folded.
    assert {"hand tools", "boats sailing"} <= corpus.labels


# --- the category pool ----------------------------------------------------------------

POOL = ["Stone fruit", "Chess tactics", "Bed linen", "Knots", "Volcanoes", "Tea"]


def test_banking_the_same_idea_twice_leaves_one_category():
    """The pool's own dedupe, made durable. `label_key` folds ordering and punctuation, so
    it is the key — two documents for one idea would hand the same theme out twice."""
    client = FakeClient()
    pool = FirestoreCategories(client)  # ty: ignore

    assert pool.bank([Category(label="___ STONE"), Category(label="Knots")]) == 2
    assert pool.bank([Category(label="stone ___"), Category(label="Knots")]) == 0
    assert len(client.collections[CATEGORIES].docs) == 2
    assert {c.label for c in pool.known()} == {"___ STONE", "Knots"}


def test_allocation_only_writes_back_the_themes_it_spent():
    client = FakeClient()
    pool = FirestoreCategories(client)  # ty: ignore
    pool.bank([Category(label=x) for x in POOL])

    pool.allocate(2, rng=random.Random(1))
    stamped = [c for c in pool.known() if c.used]
    assert len(stamped) == 2, "a night of two boards spent more than two themes"


def test_both_pools_hand_out_the_same_slots(tmp_path):
    """One rule, two places to keep it.

    The file-backed pool is what a laptop uses and the database-backed one is what the job
    uses, and a generator whose variety depends on where its state lives would be
    impossible to reason about from a local run. `draw` is shared; this is what says so.
    """
    on_disk = tmp_path / "categories.json"
    on_disk.write_text(json.dumps([{"label": x, "reads_as": "", "used": ""} for x in POOL]))

    client = FakeClient()
    in_db = FirestoreCategories(client)  # ty: ignore
    in_db.bank([Category(label=x) for x in POOL])

    from_disk = JsonCategorySource(on_disk).allocate(3, rng=random.Random(4))
    from_db = in_db.allocate(3, rng=random.Random(4))
    assert from_disk == from_db
