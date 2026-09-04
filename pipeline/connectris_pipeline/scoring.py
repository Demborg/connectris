"""Turning solver attempts into two numbers: how hard, and how legible.

*Recovery* is the difficulty proxy — what fraction of weak-model attempts reproduced a
given four exactly. *Legibility* is the fairness proxy — when they did find it, could
they say what it was? A puzzle where solvers find the grouping but name it differently is
fine; one where nobody can articulate why is unfair, and this is the only stage that
catches it.

Legibility is lexical, not embedded. The first real run put 344 embedding calls through
`gemini-embedding-2` — more calls than the whole generation pipeline — and changed no
decision: the board-level threshold fired 0 times in 20, and this free function reproduced
19 of those 20 verdicts while being *stricter*. It is also more accurate where it matters
most: the embedder charged 0.13 cosine for a pure capitalisation change, wider than the
whole band the rescale had been calibrated to cut.

Both are proxies over cheap models, which is not human difficulty. See DESIGN.md's honest
caveat: until real runs are logged and fitted, this filters broken puzzles, not easy ones.
"""

from __future__ import annotations

import difflib
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

    Blind to synonyms — 'Card suits' vs 'Things in a deck' scores near zero — so it is a
    floor on legibility, not a measurement of it, and it errs toward the review queue
    rather than toward rejection. That is the right direction to be wrong in, and it is
    what an embedding model measurably failed to improve on.
    """
    ta, tb = _tokens(a), _tokens(b)
    jaccard = len(ta & tb) / len(ta | tb) if ta | tb else 0.0
    ratio = difflib.SequenceMatcher(None, " ".join(sorted(ta)), " ".join(sorted(tb))).ratio()
    if not ta & tb:
        # Character overlap between unrelated English phrases floors around 0.3, which is
        # close enough to the threshold to be noise. No shared content word, no credit.
        return ratio * 0.5
    return max(jaccard, ratio)


def score(puzzle: Puzzle, attempts: list[Attempt]) -> SolveStats:
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

    stats: list[GroupStat] = []
    for g in puzzle.groups:
        names = found[g.id]
        legibility = (
            sum(lexical_similarity(g.label, name) for name in names) / len(names) if names else -1.0
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
        mean_legibility=round(sum(scored) / len(scored), 3) if scored else -1.0,
        groups=stats,
        by_model={k: sum(v) / (len(v) * ROWS) for k, v in per_model.items()},
    )
