"""The per-candidate record: everything the pipeline learned about one puzzle.

Written to disk stage by stage. Two reasons it is one flat serialisable object rather
than values passed between functions: a run that dies at the grader should not throw away
the solve data it already paid for, and the decision is a pure function over this record
(see `decide`), so thresholds can be re-tuned and old runs re-decided for free. Same
instinct as pin 10 in DESIGN.md — log everything, score it later.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal, Self

from .config import Thresholds
from .schema import Grade, RedTeamReport
from .scoring import Attempt, GroupStat, SolveStats
from .spec import Problem, Puzzle, is_fatal

Verdict = Literal["accept", "review", "reject"]


@dataclass
class Decision:
    verdict: Verdict
    reasons: list[str]


@dataclass
class Candidate:
    id: str
    puzzle: Puzzle
    #: The false groupings the proposer says it built in — each a name, the words in it,
    #: and the row each of those words really belongs to. Shown to the red team and the
    #: grader. Plain dicts rather than the `Lure` model so that a stored run rebuilds
    #: without it; see `from_json`.
    lures: list[dict] = field(default_factory=list)
    #: The device and theme this board was allocated before it was written.
    slot: dict[str, str] = field(default_factory=dict)
    problems: list[Problem] = field(default_factory=list)
    attempts: list[Attempt] = field(default_factory=list)
    stats: SolveStats | None = None
    red: RedTeamReport | None = None
    grade: Grade | None = None
    decision: Decision | None = None
    #: Set when a stage raised. A candidate that errored is never accepted.
    error: str = ""

    @property
    def warnings(self) -> list[str]:
        return [str(p) for p in self.problems]

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "slot": self.slot,
            "puzzle": self.puzzle.to_game_json(),
            "lures": self.lures,
            "problems": [asdict(p) for p in self.problems],
            "attempts": [a.to_json() for a in self.attempts],
            "stats": self.stats.to_json() if self.stats else None,
            "red_team": self.red.model_dump() if self.red else None,
            "grade": self.grade.model_dump() if self.grade else None,
            "decision": asdict(self.decision) if self.decision else None,
            "error": self.error,
        }

    @classmethod
    def from_json(cls, raw: dict) -> Self:
        """Rebuild a record written by a previous run, so `regrade` needs no model."""
        puzzle = Puzzle.from_game_json(raw["puzzle"])
        stats = None
        if raw.get("stats"):
            fields = dict(raw["stats"])
            fields["groups"] = [GroupStat(**g) for g in fields["groups"]]
            stats = SolveStats(**fields)
        decision = Decision(**raw["decision"]) if raw.get("decision") else None
        return cls(
            id=raw["id"],
            puzzle=puzzle,
            lures=_lures_from_json(raw),
            slot=raw.get("slot", {}),
            problems=[Problem(**x) for x in raw.get("problems", [])],
            attempts=[Attempt(**a) for a in raw.get("attempts", [])],
            stats=stats,
            red=RedTeamReport.model_validate(raw["red_team"]) if raw.get("red_team") else None,
            grade=Grade.model_validate(raw["grade"]) if raw.get("grade") else None,
            decision=decision,
            error=raw.get("error", ""),
        )


def _lures_from_json(raw: dict) -> list[dict]:
    """Read `lures`, falling back to the `traps` dict that preceded it.

    Runs on disk predate this field, and `regrade` re-deciding an old run for free is the
    whole tuning loop — so an old record has to load rather than raise. A trap was one
    sentence about one row, which carries no word list, so it comes back as a named lure
    with no members: enough for the grader to read, not enough to pretend it was measured.
    """
    if (lures := raw.get("lures")) is not None:
        return list(lures)
    return [
        {"name": note, "words": [], "where_each_lives": [gid]}
        for gid, note in (raw.get("traps") or {}).items()
        if note and note.lower() != "none"
    ]


def decide(candidate: Candidate, t: Thresholds) -> Decision:
    """Accept, review, or reject — from the record alone, no model call.

    The bar for *reject* is evidence the puzzle is wrong; the bar for *accept* is evidence
    it is right. Everything in between is a human's problem, which is the point of having
    a queue rather than a threshold.
    """
    reasons: list[str] = []
    reject = False

    if candidate.error:
        return Decision("reject", [f"pipeline error: {candidate.error}"])

    if is_fatal(candidate.problems):
        return Decision("reject", [str(p) for p in candidate.problems if p.severity == "fatal"])

    review = [str(p) for p in candidate.problems]

    red = candidate.red
    if red is not None:
        if red.verdict == "broken" or red.alternatives:
            reject = True
            reasons.append(f"red team found {len(red.alternatives)} alternative partition(s)")
        if red.ambiguous_words:
            # A word two labels both admit is a construction defect, not difficulty, so
            # one finding is one too many. It reviews rather than rejects because a model
            # can still be wrong about a definition, and a human can check in seconds.
            words = ", ".join(a.word for a in red.ambiguous_words)
            review.append(f"red team says two labels both admit: {words}")
        if red.loose_labels:
            labels = ", ".join(repr(x.label) for x in red.loose_labels)
            review.append(f"red team says these labels read wider than their row: {labels}")
    else:
        review.append("no red-team report")

    s = candidate.stats
    if s is None:
        review.append("no solver evidence")
    else:
        if s.well_formed == 0:
            review.append("no solver produced a legal partition — ensemble may be misconfigured")
        if s.mean_recovery > t.max_mean_recovery:
            reject = True
            reasons.append(
                f"too easy: the weak solver recovered {s.mean_recovery:.0%} of categories"
            )
        if s.mean_recovery == 0:
            # Hard and broken look identical from here, so this never rejects on its own —
            # the grader, which can see the board, is the one that tells them apart.
            review.append("nothing landed: the solver recovered no categories at all")

    g = candidate.grade
    if g is None:
        review.append("no grade")
    else:
        if g.verdict == "reject":
            reject = True
            reasons.append(f"grader rejected: {g.reasons}")
        elif g.verdict == "review":
            review.append(f"grader sent it to review: {g.reasons}")
        if g.fairness < t.min_fairness:
            review.append(f"grader scored fairness {g.fairness}/5")
        if g.elegance < t.min_elegance:
            review.append(f"grader scored elegance {g.elegance}/5")

    if reject:
        return Decision("reject", reasons + review)
    if review:
        return Decision("review", review)
    return Decision("accept", ["clean through every stage"])
