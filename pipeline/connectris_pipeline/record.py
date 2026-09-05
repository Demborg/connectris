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
    #: group id -> the decoy the proposer says it planted. Shown to the red team and grader.
    traps: dict[str, str] = field(default_factory=dict)
    seed: dict[str, str] = field(default_factory=dict)
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
            "seed": self.seed,
            "puzzle": self.puzzle.to_game_json(),
            "traps": self.traps,
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
            traps=raw.get("traps", {}),
            seed=raw.get("seed", {}),
            problems=[Problem(**x) for x in raw.get("problems", [])],
            attempts=[Attempt(**a) for a in raw.get("attempts", [])],
            stats=stats,
            red=RedTeamReport.model_validate(raw["red_team"]) if raw.get("red_team") else None,
            grade=Grade.model_validate(raw["grade"]) if raw.get("grade") else None,
            decision=decision,
            error=raw.get("error", ""),
        )


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
