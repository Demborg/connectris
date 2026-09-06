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
from typing import Literal, Self

#: Words per row. `COLS` in engine.ts.
COLS = 4
#: Rows on a full board, i.e. categories per puzzle. `ROWS` in engine.ts.
ROWS = 5
#: Four columns on a 375px screen is ~70px a tile. Hard data constraint, not a style note.
MAX_WORD_LEN = 12

#: The letters a board may use, per language. Anything outside its language's alphabet is
#: a `charset` fatal — which is the point: the old single ASCII regex made "not English"
#: and "not a word" the same error, and `normalise_word` below silently *repaired* the
#: first one before the regex could see it.
ALPHABETS: dict[str, str] = {
    "en": "A-Z",
    #: Å Ä Ö are letters of the Swedish alphabet, not decorated A and O. Folding them is a
    #: spelling error: RÅTTA (rat) and RATTA (to steer) are different words.
    "sv": "A-ZÅÄÖ",
}

#: Uppercase, and space/hyphen/apostrophe only where an entry really needs one.
WORD_RE = re.compile(rf"[A-Z][A-Z'\- ]{{0,{MAX_WORD_LEN - 1}}}")

Severity = Literal["fatal", "warn"]


def word_re(language: str) -> re.Pattern[str]:
    """The charset gate for one language. Unknown languages get the English one."""
    letters = ALPHABETS.get(language, ALPHABETS["en"])
    return re.compile(rf"[{letters}][{letters}'\- ]{{0,{MAX_WORD_LEN - 1}}}")


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
class WordNote:
    """One word of a category, and what puts it there."""

    word: str
    note: str


@dataclass
class Notes:
    """A category written out, for the player who has already solved the row.

    Carried on the group rather than beside it, because that is what makes it safe: the
    game only ever hands a `Group` to a player whose row is on the table, so notes are
    revealed by exactly the rule the label is. See `Notes` in src/lib/game/types.ts.

    `words` carries each word rather than lining up with `Group.words` by position, so a
    note cannot end up under its neighbour.
    """

    summary: str
    words: list[WordNote]

    @classmethod
    def from_game_json(cls, raw: dict) -> Self:
        return cls(
            summary=raw.get("summary", ""),
            words=[WordNote(word=w["word"], note=w["note"]) for w in raw.get("words", [])],
        )

    def to_game_json(self) -> dict:
        return {
            "summary": self.summary,
            "words": [{"word": w.word, "note": w.note} for w in self.words],
        }


@dataclass
class Group:
    id: str
    label: str
    words: list[str]
    #: Written by the gloss stage, after a board is accepted. `None` on every board that
    #: was published before that stage existed; those rows simply do not open.
    notes: Notes | None = None


@dataclass
class Puzzle:
    id: str
    name: str
    groups: list[Group]
    language: str = "en"

    @property
    def words(self) -> list[str]:
        return [w for g in self.groups for w in g.words]

    @classmethod
    def from_game_json(cls, raw: dict) -> Self:
        """The inverse of `to_game_json`, which existed twice by hand before this."""
        return cls(
            id=raw["id"],
            name=raw["name"],
            language=raw.get("language", "en"),
            groups=[
                Group(
                    id=g["id"],
                    label=g["label"],
                    words=list(g["words"]),
                    notes=Notes.from_game_json(g["notes"]) if g.get("notes") else None,
                )
                for g in raw["groups"]
            ],
        )

    def to_game_json(self) -> dict:
        """The exact object shape `src/lib/data/puzzles.json` holds.

        `notes` is written only where there are some, so a board from before the gloss
        stage round-trips byte-identical rather than growing a row of nulls.
        """
        return {
            "id": self.id,
            "name": self.name,
            "language": self.language,
            "groups": [group_json(g) for g in self.groups],
        }


def group_json(group: Group) -> dict:
    """One group as both the game's JSON file and its Firestore document hold it.

    The two shapes were written out by hand in three places, which is how a field gets
    added to the file and forgotten in the database. `store.py` writes the document field
    by field on purpose — the document is not the file — but a *group* is the same object
    in both, so it is spelled out once here.
    """
    doc: dict = {"id": group.id, "label": group.label, "words": list(group.words)}
    if group.notes is not None:
        doc["notes"] = group.notes.to_game_json()
    return doc


#: Letters that must survive folding, as opposed to accents that may not. Å Ä Ö are the
#: last three letters of the Swedish alphabet, not decorated A and O — folding them is a
#: spelling error, and a silent one: it turned RÅTTA (rat) into RATTA (to steer) and ÖGON
#: into OGON. Because the answer key went through the same fold, the damage cancelled out
#: between board and solver and left nothing to notice. Add Æ Ø Ð here for Norwegian.
_PROTECTED = "ÅÄÖåäö"


def normalise_word(word: str) -> str:
    """Fold a model's idea of a word into the board's: uppercase, single-spaced, unaccented.

    Solvers echo the words back, and they echo them back in whatever case they feel like,
    so this is also what makes solver output comparable to the answer key.

    "Unaccented" means decoration only. CAFÉ is still folded to CAFE, because in English an
    acute is a flourish on a letter that is already there; RÅTTA is left alone, because in
    Swedish the ring is the letter. The distinction is `_PROTECTED` and it is per-alphabet
    rather than per-board on purpose — this function is called from the dedupe index and
    the scorer, neither of which has a language in hand, and a fold that varied by caller
    would make the same word compare unequal to itself.

    What this does *not* do is decide whether a letter belongs on this board. That is
    `validate`'s job now, through `word_re`, so "not in this language" is an error a run
    can see rather than a repair it cannot.
    """
    folded = "".join(
        ch
        if ch in _PROTECTED
        else unicodedata.normalize("NFKD", ch).encode("ascii", "ignore").decode()
        for ch in unicodedata.normalize("NFC", word)
    )
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
    def from_game_json(cls, puzzles: list[dict], language: str | None = None) -> Self:
        """The shipped board index, optionally narrowed to one language.

        Narrowing matters once two languages share a database. The *word* axis has to be
        per-language or it is simply wrong: BAND, PARK, HAND and KORT are ordinary words in
        both, so an English board would forbid a Swedish one from using them and vice
        versa, for no reason a player would recognise. The *category* axis is the opposite
        — 'stone fruit' and 'stenfrukt' are the same board idea in two costumes, and
        shipping both a week apart is the repetition this index exists to prevent — but
        `label_key` is lexical, so it cannot see that, and scoping labels by language is
        the conservative call rather than the correct one. Cross-language category dedupe
        needs an embedding or a concept id on the pool entry; see the report.
        """
        words: set[str] = set()
        labels: set[str] = set()
        for p in puzzles:
            if language is not None and p.get("language", "en") != language:
                continue
            for g in p.get("groups", []):
                labels.add(label_key(g.get("label", "")))
                words.update(normalise_word(w) for w in g.get("words", []))
        return cls(words=words, labels=labels)

    def extend(self, puzzle: Puzzle) -> None:
        """Fold an accepted candidate in, so the rest of a batch dedupes against it too."""
        self.words.update(normalise_word(w) for w in puzzle.words)
        self.labels.update(label_key(g.label) for g in puzzle.groups)


#: Letters that survive the loose comparisons below. Not per-language: two languages share
#: one dedupe index, so the folding has to be the union or a Swedish label would compare as
#: its own consonant skeleton ("STJÄRNOR" -> "stjrnor").
_LETTERS = "a-zåäöéèüà"


def label_key(label: str) -> str:
    """Category labels compare loosely: '___ BOARD' and 'board ___' are the same idea."""
    return " ".join(sorted(re.sub(rf"[^{_LETTERS} ]+", " ", label.lower()).split()))


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

    charset = word_re(puzzle.language)
    for w in words:
        if len(w) > MAX_WORD_LEN:
            problems.append(Problem("too-long", f"{w!r} is {len(w)} chars, cap is {MAX_WORD_LEN}"))
        elif not charset.fullmatch(w):
            problems.append(Problem("charset", f"{w!r} is not plain uppercase {puzzle.language!r}"))

    ids = [g.id for g in puzzle.groups]
    if len(set(ids)) != len(ids):
        problems.append(Problem("duplicate-group-id", f"group ids are not unique: {ids}"))

    # A word written into a label points straight at a row — at that row if the word is
    # filed elsewhere, at the answer if it is the label's own.
    for g in puzzle.groups:
        label_words = set(re.sub(rf"[^{_LETTERS}]+", " ", g.label.lower()).split())
        problems.extend(
            Problem(
                "label-gives-it-away",
                f"{w!r} (in {other.id!r}) is written into the label of {g.id!r}: {g.label!r}",
                "warn",
            )
            for other in puzzle.groups
            for w in other.words
            if normalise_word(w).lower() in label_words
        )

    # Notes are written by a model after the board is accepted, so this is the one thing
    # in the file that no earlier stage has already checked. A note under the wrong word
    # is worse than a missing one: the player reads it as fact about a word it is not
    # about. Warn rather than fatal — the board itself is fine, and `attach` in the gloss
    # stage is what refuses to write a set that does not line up.
    for g in puzzle.groups:
        if g.notes is None:
            continue
        if not g.notes.summary.strip():
            problems.append(Problem("no-summary", f"group {g.id!r} has empty notes", "warn"))
        noted = {normalise_word(w.word) for w in g.notes.words}
        if noted != {normalise_word(w) for w in g.words}:
            problems.append(
                Problem("notes-mismatch", f"group {g.id!r} has notes for {sorted(noted)}", "warn")
            )

    explained = sum(1 for g in puzzle.groups if g.notes is not None)
    if explained not in (0, len(puzzle.groups)):
        # Five bars where three open reads as three that are broken.
        problems.append(
            Problem(
                "part-explained",
                f"{explained} of {len(puzzle.groups)} rows have notes",
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
        problems.extend(
            Problem("stale-category", f"category {g.label!r} has shipped before", "warn")
            for g in puzzle.groups
            if label_key(g.label) in corpus.labels
        )

    return problems


def is_fatal(problems: list[Problem]) -> bool:
    return any(p.severity == "fatal" for p in problems)
