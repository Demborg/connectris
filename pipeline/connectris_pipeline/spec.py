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
#: How many checks a player gets. `CHECKS` in engine.ts, and mirrored here for the same
#: reason `ROWS` is: it is the whole difficulty budget a board is designed against, and the
#: prompt said six while the game gave four for as long as both existed separately.
CHECKS = 4

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
    #: What this category *is*, written in English whatever the board's language, so that
    #: 'Bleckblåsinstrument' and 'Orchestral brass instruments' can be seen to be the same
    #: idea. Generator metadata: the app never reads it. Empty on boards that predate it.
    concept: str = ""


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
                    concept=g.get("concept", ""),
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
    # Written only where there is one, so a board from before the concept index existed
    # round-trips byte-identical rather than growing a row of empty strings.
    if group.concept:
        doc["concept"] = group.concept
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
    #: Concept keys, pooled across *every* language. See `from_game_json`.
    concepts: set[frozenset[str]] = field(default_factory=set)

    def copy(self) -> Corpus:
        """A detached snapshot. A method rather than `Corpus(c.words, c.labels)` at the
        call site, because that positional form silently dropped whichever axis was added
        last — which is exactly how a new index arrives already broken."""
        return Corpus(set(self.words), set(self.labels), set(self.concepts))

    def matches_concept(self, concept: str) -> bool:
        """Whether this idea has shipped, in any language.

        Containment in either direction, not equality: a category is a repeat both when
        it says more than one already shipped ('orchestral brass instruments' against
        'brass instruments') and when it says less.
        """
        key = concept_key(concept)
        return bool(key) and any(key <= seen or seen <= key for seen in self.concepts)

    @classmethod
    def from_game_json(cls, puzzles: list[dict], language: str | None = None) -> Self:
        """The shipped board index, optionally narrowed to one language.

        Narrowing matters once two languages share a database. The *word* axis has to be
        per-language or it is simply wrong: BAND, PARK, HAND and KORT are ordinary words in
        both, so an English board would forbid a Swedish one from using them and vice
        versa, for no reason a player would recognise. The *category* axis is the opposite
        — 'stone fruit' and 'stenfrukt' are the same board idea in two costumes, and
        shipping both a week apart is the repetition this index exists to prevent — but
        `label_key` is lexical, so it cannot see that. The `concepts` axis is what does:
        it is built from every puzzle regardless of language, and it is deliberately the
        one index this parameter does not narrow.
        """
        words: set[str] = set()
        labels: set[str] = set()
        concepts: set[frozenset[str]] = set()
        for p in puzzles:
            # Concepts are pooled first and unconditionally: a Swedish batch has to be
            # told what shipped in English, which is the whole point of the axis.
            for g in p.get("groups", []):
                if key := concept_key(g.get("concept", "")):
                    concepts.add(key)
            if language is not None and p.get("language", "en") != language:
                continue
            for g in p.get("groups", []):
                labels.add(label_key(g.get("label", "")))
                words.update(normalise_word(w) for w in g.get("words", []))
        return cls(words=words, labels=labels, concepts=concepts)

    def extend(self, puzzle: Puzzle) -> None:
        """Fold an accepted candidate in, so the rest of a batch dedupes against it too."""
        self.words.update(normalise_word(w) for w in puzzle.words)
        self.labels.update(label_key(g.label) for g in puzzle.groups)
        self.concepts.update(k for g in puzzle.groups if (k := concept_key(g.concept)))


#: Letters that survive the loose comparisons below. Not per-language: two languages share
#: one dedupe index, so the folding has to be the union or a Swedish label would compare as
#: its own consonant skeleton ("STJÄRNOR" -> "stjrnor").
_LETTERS = "a-zåäöéèüà"


def label_key(label: str) -> str:
    """Category labels compare loosely: '___ BOARD' and 'board ___' are the same idea."""
    return " ".join(sorted(re.sub(rf"[^{_LETTERS} ]+", " ", label.lower()).split()))


#: Dropped before concepts are compared, so 'styles of drinking glasses' and 'drinking
#: glass styles' reduce to the same thing. English only, and that is not an oversight:
#: a concept is always written in English (see `Group.concept`).
_CONCEPT_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "by",
        "for",
        "from",
        "in",
        "kind",
        "kinds",
        "of",
        "on",
        "or",
        "sort",
        "sorts",
        "style",
        "styles",
        "that",
        "the",
        "their",
        "thing",
        "things",
        "to",
        "type",
        "types",
        "with",
        "word",
        "words",
    }
)


def concept_key(concept: str) -> frozenset[str]:
    """The content words of a concept, as a set, for comparison *across* languages.

    `label_key` cannot do this job and no amount of tuning will make it: it is lexical,
    so 'Bleckblåsinstrument' and 'Orchestral brass instruments' share not one character
    and compare as maximally different when they are in fact the same board idea. The
    first Swedish run re-invented three shipped English categories in translation and
    every one of them passed the label check clean.

    A set rather than a sorted string because the useful test is *containment*, not
    equality — 'brass instruments' and 'orchestral brass instruments' are the same
    category with one word of extra precision, and an equality test misses that. See
    `Corpus.matches_concept`.
    """
    return frozenset(re.sub(r"[^a-z ]+", " ", concept.lower()).split()) - _CONCEPT_STOPWORDS


def validate(
    puzzle: Puzzle, corpus: Corpus | None = None, *, max_reused_words: int = 3
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
        # Three, not four, and the gate stays `>`. A row is exactly `COLS` words, so a cap
        # of four let an entire duplicated row through unflagged — and it did: two boards
        # of one run shipped FÄNRIK, LÖJTNANT, KAPTEN, MAJOR identically, warned about by
        # nothing. Four shared words is not a coincidence, it is a copied category.
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
        # The same test again, one level up, and the only one that can see across a
        # language boundary. A board that scores clean on `stale-category` and fails here
        # is a translation of something already shipped.
        problems.extend(
            Problem(
                "stale-concept",
                f"category {g.label!r} is {g.concept!r}, which has shipped in another "
                f"language or under another name",
                "warn",
            )
            for g in puzzle.groups
            if label_key(g.label) not in corpus.labels and corpus.matches_concept(g.concept)
        )

    return problems


def is_fatal(problems: list[Problem]) -> bool:
    return any(p.severity == "fatal" for p in problems)
