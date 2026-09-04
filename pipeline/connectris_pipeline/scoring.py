"""Turning solver attempts into two numbers: how hard, and how legible.

*Recovery* is the difficulty proxy — what fraction of weak-model attempts reproduced a
given four exactly. *Legibility* is the fairness proxy — when they did find it, could
they say what it was? A puzzle where solvers find the grouping but name it differently is
fine; one where nobody can articulate why is unfair, and this is the only stage that
catches it.

Both are proxies over cheap models, which is not human difficulty. See DESIGN.md's honest
caveat: until real runs are logged and fitted, this filters broken puzzles, not easy ones.
"""

from __future__ import annotations

import difflib
import math
import re
from dataclasses import asdict, dataclass, field

from .schema import SolveAttempt
from .spec import COLS, ROWS, Puzzle, normalise_word

_STOPWORDS = {
    "the",
    "a",
    "an",
    "of",
    "and",
    "or",
    "in",
    "on",
    "to",
    "for",
    "kinds",
    "types",
    "things",
    "words",
}


@dataclass
class Attempt:
    """One solver run, kept whole for the run artifacts.

    `model` is a `ModelSpec.key` — name plus thinking setting — because two configurations
    of one model are two different solvers. `seed` is what made this attempt differ from
    its siblings; see stages/solve.py.
    """

    model: str
    seed: int
    groups: list[tuple[str, list[str]]]

    @classmethod
    def of(cls, model: str, seed: int, raw: SolveAttempt) -> Attempt:
        return cls(
            model=model,
            seed=seed,
            groups=[(g.category, [normalise_word(w) for w in g.words]) for g in raw.groups],
        )

    @property
    def sets(self) -> list[frozenset[str]]:
        return [frozenset(words) for _, words in self.groups]

    def is_well_formed(self, board: set[str]) -> bool:
        """Did it actually partition the board, or just say words?"""
        flat = [w for _, words in self.groups for w in words]
        return (
            len(self.groups) == ROWS
            and all(len(words) == COLS for _, words in self.groups)
            and len(set(flat)) == len(flat) == len(board)
            and set(flat) == board
        )

    def to_json(self) -> dict:
        return asdict(self)


@dataclass
class GroupStat:
    id: str
    label: str
    #: Fraction of attempts that produced this exact four as one of their groups.
    recovery: float
    #: Mean similarity of the names given to it, over the attempts that found it.
    #: -1 when nobody found it, which is a different thing from "named it badly".
    legibility: float
    names: list[str] = field(default_factory=list)


@dataclass
class SolveStats:
    attempts: int
    well_formed: int
    full_solve_rate: float
    mean_recovery: float
    min_recovery: float
    mean_legibility: float
    groups: list[GroupStat]
    by_model: dict[str, float]

    def digest(self) -> str:
        """The human- and grader-readable version. Fed straight into the grader prompt."""
        lines = [
            f"{self.attempts} attempts, {self.well_formed} of them a legal partition. "
            f"Solved outright: {self.full_solve_rate:.0%}.",
            "Per category — recovery, then how the solvers named it:",
        ]
        for g in self.groups:
            named = "; ".join(dict.fromkeys(g.names)) or "never found it"
            legible = "n/a" if g.legibility < 0 else f"{g.legibility:.2f}"
            lines.append(f"  {g.label!r}: {g.recovery:.0%} found, name match {legible} — {named}")
        by_model = ", ".join(f"{k} {v:.0%}" for k, v in self.by_model.items())
        lines.append(f"By solver: {by_model}")
        return "\n".join(lines)

    def to_json(self) -> dict:
        return asdict(self)


def _tokens(label: str) -> set[str]:
    words = re.sub(r"[^a-z ]+", " ", label.lower()).split()
    return {w for w in words if w not in _STOPWORDS} or set(words)


def lexical_similarity(a: str, b: str) -> float:
    """Token overlap or string ratio, whichever is kinder.

    The fallback when there is no embeddings endpoint. It is blind to synonyms — 'Card
    suits' vs 'Things in a deck' scores near zero — so it is a floor on legibility, not a
    measurement of it, and it will send fair puzzles to the review queue rather than
    reject them.
    """
    ta, tb = _tokens(a), _tokens(b)
    jaccard = len(ta & tb) / len(ta | tb) if ta | tb else 0.0
    ratio = difflib.SequenceMatcher(None, " ".join(sorted(ta)), " ".join(sorted(tb))).ratio()
    if not ta & tb:
        # Character overlap between unrelated English phrases floors around 0.3, which is
        # close enough to the threshold to be noise. No shared content word, no credit.
        return ratio * 0.5
    return max(jaccard, ratio)


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


async def score(puzzle: Puzzle, attempts: list[Attempt], embed=None) -> SolveStats:
    """`embed` is an async `list[str] -> list[list[float]]`; falsy result means lexical."""
    board = {normalise_word(w) for w in puzzle.words}
    intended = {g.id: frozenset(normalise_word(w) for w in g.words) for g in puzzle.groups}
    n = max(len(attempts), 1)

    found: dict[str, list[str]] = {g.id: [] for g in puzzle.groups}
    full = 0
    per_model: dict[str, list[int]] = {}

    for att in attempts:
        hits = 0
        sets = att.sets
        for g in puzzle.groups:
            for (category, _words), s in zip(att.groups, sets, strict=True):
                if s == intended[g.id]:
                    found[g.id].append(category.strip())
                    hits += 1
                    break
        if hits == ROWS:
            full += 1
        per_model.setdefault(att.model, []).append(hits)

    similarity = await _similarity_fn(puzzle, found, embed)

    stats: list[GroupStat] = []
    for g in puzzle.groups:
        names = found[g.id]
        legibility = (
            sum(similarity(g.label, name) for name in names) / len(names) if names else -1.0
        )
        stats.append(
            GroupStat(
                id=g.id,
                label=g.label,
                recovery=len(names) / n,
                legibility=round(legibility, 3),
                names=list(dict.fromkeys(names))[:6],
            )
        )

    scored = [s.legibility for s in stats if s.legibility >= 0]
    return SolveStats(
        attempts=len(attempts),
        well_formed=sum(1 for a in attempts if a.is_well_formed(board)),
        full_solve_rate=full / n,
        mean_recovery=sum(s.recovery for s in stats) / len(stats),
        min_recovery=min((s.recovery for s in stats), default=0.0),
        mean_legibility=round(sum(scored) / len(scored), 3) if scored else -1.0,
        groups=stats,
        by_model={k: sum(v) / (len(v) * ROWS) for k, v in per_model.items()},
    )


async def _similarity_fn(puzzle: Puzzle, found: dict[str, list[str]], embed):
    """One embedding call for every label and every name, or lexical if that fails."""
    if embed is None:
        return lexical_similarity

    texts = [g.label for g in puzzle.groups] + [n for names in found.values() for n in names]
    texts = list(dict.fromkeys(t for t in texts if t.strip()))
    if not texts:
        return lexical_similarity

    vectors = await embed(texts)
    if not vectors or len(vectors) != len(texts):
        return lexical_similarity

    table = dict(zip(texts, vectors, strict=True))

    def similar(a: str, b: str) -> float:
        va, vb = table.get(a), table.get(b)
        if va is None or vb is None:
            return lexical_similarity(a, b)
        return rescale(cosine(va, vb))

    return similar


#: Raw cosine has no useful zero, so it is rescaled onto 0..1 before meeting a threshold.
#: These two numbers are measured, not guessed — 13 label pairs through
#: `gemini-embedding-2`, which sorted into three clean bands:
#:
#:     genuine paraphrase   0.78 - 0.91   ("Card suits" ~ "Suits in a deck")
#:     unrelated category   0.61 - 0.64   ("Fish" ~ "Typography")
#:     vague non-answer     0.45 - 0.59   ("Card suits" ~ "words that go together")
#:
#: Note the middle band: two real but different categories score *higher* than a solver
#: shrugging. Both are legibility failures, so the floor sits under both, and the gap
#: between 0.64 and 0.78 is what `min_legibility` is really cutting.
#:
#: This is model-specific. Change `embedding_model` and these have to be re-measured.
EMBEDDING_FLOOR = 0.60
EMBEDDING_SPAN = 0.35


def rescale(cos: float) -> float:
    """Raw cosine onto 0..1, with 'unrelated' pinned near zero."""
    return min(1.0, max(0.0, (cos - EMBEDDING_FLOOR) / EMBEDDING_SPAN))
