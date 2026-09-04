"""The shape of a legal puzzle.

Mirrors `src/lib/game/engine.ts` (`COLS`, `ROWS`) and the `puzzle data` block in
`engine.spec.ts`. Anything the vitest suite would reject must be rejected here first —
a generated puzzle that fails CI is a puzzle the pipeline should never have emitted.

Everything in this module is deterministic and free. It runs before a single solver
token is spent, because most of what a model gets wrong about this format (five words in
a row, a repeated word, a 15-character word) is catchable by counting.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Literal

#: Words per row. `COLS` in engine.ts.
COLS = 4
#: Rows on a full board, i.e. categories per puzzle. `ROWS` in engine.ts.
ROWS = 5
#: Four columns on a 375px screen is ~70px a tile. Hard data constraint, not a style note.
MAX_WORD_LEN = 12

#: Uppercase, and space/hyphen/apostrophe only where an English entry really needs one.
WORD_RE = re.compile(rf"[A-Z][A-Z'\- ]{{0,{MAX_WORD_LEN - 1}}}")

Severity = Literal["fatal", "warn"]


@dataclass(frozen=True)
class Problem:
    """One thing wrong with a candidate.

    `fatal` means the puzzle is unshippable as written; `warn` means it is legal but
    smells, and the grader is told about it.
    """

    code: str
    message: str
    severity: Severity = "fatal"

    def __str__(self) -> str:
        return f"[{self.severity}] {self.code}: {self.message}"


@dataclass
class Group:
    id: str
    label: str
    words: list[str]


@dataclass
class Puzzle:
    id: str
    name: str
    groups: list[Group]
    language: str = "en"

    @property
    def words(self) -> list[str]:
        return [w for g in self.groups for w in g.words]

    def to_game_json(self) -> dict:
        """The exact object shape `src/lib/data/puzzles.json` holds."""
        return {
            "id": self.id,
            "name": self.name,
            "language": self.language,
            "groups": [{"id": g.id, "label": g.label, "words": list(g.words)} for g in self.groups],
        }


def normalise_word(word: str) -> str:
    """Fold a model's idea of a word into the board's: uppercase, single-spaced, unaccented.

    Solvers echo the words back, and they echo them back in whatever case they feel like,
    so this is also what makes solver output comparable to the answer key.
    """
    folded = unicodedata.normalize("NFKD", word).encode("ascii", "ignore").decode()
    return " ".join(folded.upper().split())


def slugify(text: str) -> str:
    """Group ids in the game data are short lowercase slugs; keep that."""
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")
    return slug or "group"


@dataclass
class Corpus:
    """What has already shipped, for the dedupe stage.

    Words are the cheap axis and category concepts the expensive one; a repeated word is
    a shrug, a repeated category is the same puzzle again.
    """

    words: set[str] = field(default_factory=set)
    labels: set[str] = field(default_factory=set)

    @classmethod
    def from_game_json(cls, puzzles: list[dict]) -> Corpus:
        words: set[str] = set()
        labels: set[str] = set()
        for p in puzzles:
            for g in p.get("groups", []):
                labels.add(label_key(g.get("label", "")))
                words.update(normalise_word(w) for w in g.get("words", []))
        return cls(words=words, labels=labels)

    def extend(self, puzzle: Puzzle) -> None:
        """Fold an accepted candidate in, so the rest of a batch dedupes against it too."""
        self.words.update(normalise_word(w) for w in puzzle.words)
        self.labels.update(label_key(g.label) for g in puzzle.groups)


def label_key(label: str) -> str:
    """Category labels compare loosely: '___ BOARD' and 'board ___' are the same idea."""
    return " ".join(sorted(re.sub(r"[^a-z ]+", " ", label.lower()).split()))


def validate(
    puzzle: Puzzle, corpus: Corpus | None = None, *, max_reused_words: int = 4
) -> list[Problem]:
    """Every deterministic reason to throw a candidate away, cheapest first."""
    problems: list[Problem] = []

    if len(puzzle.groups) != ROWS:
        problems.append(Problem("row-count", f"{len(puzzle.groups)} groups, need {ROWS}"))
    for g in puzzle.groups:
        if len(g.words) != COLS:
            problems.append(
                Problem("col-count", f"group {g.id!r} has {len(g.words)} words, need {COLS}")
            )
        if not g.label.strip():
            problems.append(Problem("no-label", f"group {g.id!r} has no label"))

    words = [normalise_word(w) for w in puzzle.words]

    seen: set[str] = set()
    for w in words:
        if w in seen:
            problems.append(Problem("duplicate-word", f"{w!r} appears twice on the board"))
        seen.add(w)

    for w in words:
        if len(w) > MAX_WORD_LEN:
            problems.append(Problem("too-long", f"{w!r} is {len(w)} chars, cap is {MAX_WORD_LEN}"))
        elif not WORD_RE.fullmatch(w):
            problems.append(Problem("charset", f"{w!r} is not plain uppercase English"))

    ids = [g.id for g in puzzle.groups]
    if len(set(ids)) != len(ids):
        problems.append(Problem("duplicate-group-id", f"group ids are not unique: {ids}"))

    # A word written into a label points straight at a row — at that row if the word is
    # filed elsewhere, at the answer if it is the label's own.
    for g in puzzle.groups:
        label_words = set(re.sub(r"[^a-z]+", " ", g.label.lower()).split())
        for other in puzzle.groups:
            for w in other.words:
                if normalise_word(w).lower() in label_words:
                    problems.append(
                        Problem(
                            "label-gives-it-away",
                            f"{w!r} (in {other.id!r}) is written into "
                            f"the label of {g.id!r}: {g.label!r}",
                            "warn",
                        )
                    )

    if corpus is not None:
        reused = sorted(set(words) & corpus.words)
        if len(reused) > max_reused_words:
            shown = ", ".join(reused[:8]) + (", ..." if len(reused) > 8 else "")
            problems.append(
                Problem("stale-words", f"{len(reused)} words already shipped: {shown}", "warn")
            )
        for g in puzzle.groups:
            if label_key(g.label) in corpus.labels:
                problems.append(
                    Problem("stale-category", f"category {g.label!r} has shipped before", "warn")
                )

    return problems


def is_fatal(problems: list[Problem]) -> bool:
    return any(p.severity == "fatal" for p in problems)
