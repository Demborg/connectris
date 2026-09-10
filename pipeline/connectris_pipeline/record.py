"""The per-candidate record: everything the pipeline learned about one puzzle.

Written to disk stage by stage. Two reasons it is one flat serialisable object rather
than values passed between functions: a run that dies at the grader should not throw away
the solve data it already paid for, and the decision is a pure function over this record
(see `decide`), so thresholds can be re-tuned and old runs re-decided for free. Same
instinct as pin 10 in DESIGN.md — log everything, score it later.
"""

from __future__ import annotations

from dataclasses import MISSING, asdict, dataclass, field, fields
from types import UnionType
from typing import (
    Any,
    Literal,
    Self,
    Union,
    cast,
    get_args,
    get_origin,
    get_type_hints,
)

from pydantic import BaseModel

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
        """Rebuild a record written by a previous run, so `regrade` needs no model.

        Written to survive its own schema moving underneath it. Two runs out of nine on
        disk could not be loaded at all before this: one carried `SolveStats.min_recovery`
        from before that field was cut, the other predated `RedTeamReport.loose_labels`
        being added. Both raised, and a `regrade` that raises is a tuning loop that
        quietly stops covering its oldest and most interesting evidence.

        So every stored sub-object goes through `_rebuild`, which drops fields this
        version no longer has and fills in ones it has gained. See there for where that
        stops, because it does stop.
        """
        stats = None
        if stored := raw.get("stats"):
            stored = dict(stored)
            stored["groups"] = [_rebuild(GroupStat, g) for g in stored.get("groups", [])]
            stats = _rebuild(SolveStats, stored)
        return cls(
            id=raw["id"],
            puzzle=Puzzle.from_game_json(raw["puzzle"]),
            lures=_lures_from_json(raw),
            slot=raw.get("slot", {}),
            problems=[_rebuild(Problem, x) for x in raw.get("problems", [])],
            attempts=[_rebuild(Attempt, a) for a in raw.get("attempts", [])],
            stats=stats,
            red=_rebuild(RedTeamReport, raw["red_team"]) if raw.get("red_team") else None,
            grade=_rebuild(Grade, _retired_verdicts(raw["grade"])) if raw.get("grade") else None,
            decision=_rebuild(Decision, raw["decision"]) if raw.get("decision") else None,
            error=raw.get("error", ""),
        )


#: Grader verdicts that no longer exist, and what they mean now. `revise` came with a
#: rewritten board and a second pass; the revision loop was deleted in 6ff93df because
#: re-evaluating a rewrite costs three calls where proposing a fresh board costs one. A
#: board the old grader wanted rewritten is exactly a board a human should look at, so it
#: reads as `review` — which is what `decide` would have made of it anyway.
RETIRED_VERDICTS = {"revise": "review"}


def _retired_verdicts(grade: dict) -> dict:
    if (v := grade.get("verdict")) in RETIRED_VERDICTS:
        return grade | {"verdict": RETIRED_VERDICTS[v]}
    return grade


class StaleRecordError(Exception):
    """A stored record this version cannot honestly rebuild. Names the field and why."""


def _empty_for(annotation: object) -> object:
    """The value a field should take when the record predates it existing.

    Containers and optionals only. An absent list means "nothing was recorded", which is
    true and harmless — an old red-team report genuinely listed no loose labels, because
    nothing was looking for them.

    A missing number has no such honest answer. Filling `mean_recovery` with 0.0 would
    read as "the solver found nothing", which is the signal `decide` treats as *hard or
    broken* — so a schema change could silently move old boards toward review and the
    tuning loop would be measuring its own migration. That raises instead.
    """
    origin = get_origin(annotation) or annotation
    if origin in (list, dict, set, tuple):
        return origin()
    if origin in (Union, UnionType) and type(None) in get_args(annotation):
        return None
    raise StaleRecordError(f"no honest empty value for a missing {annotation!r}")


def _rebuild[T](cls: type[T], raw: dict) -> T:
    """One stored dict, fitted to whatever `cls` looks like now.

    Fields the record has and the class no longer does are dropped: they were removed on
    purpose and nothing reads them. Fields the class has and the record does not are
    filled from `_empty_for`, or left to their own default where they have one.

    The line is drawn at required scalars. If a new field is load-bearing and has no
    default, an old record genuinely does not contain the information and there is no way
    to invent it — `StaleRecordError` says which field, rather than a `TypeError` from three
    frames down saying only that something was unexpected.
    """
    if issubclass(cls, BaseModel):
        data = {k: v for k, v in raw.items() if k in cls.model_fields}
        for name, spec in cls.model_fields.items():
            if name not in data and spec.is_required():
                data[name] = _fill(cls, name, spec.annotation)
        return cast(T, cls.model_validate(data))

    hints = get_type_hints(cls)
    args = {}
    for spec in fields(cast(Any, cls)):
        if spec.name in raw:
            args[spec.name] = raw[spec.name]
        elif spec.default is MISSING and spec.default_factory is MISSING:
            args[spec.name] = _fill(cls, spec.name, hints[spec.name])
    return cls(**args)


def _fill(cls: type, name: str, annotation: object) -> object:
    try:
        return _empty_for(annotation)
    except StaleRecordError as exc:
        raise StaleRecordError(
            f"{cls.__name__}.{name} is required and this record predates it: {exc}. "
            f"Give the field a default, or re-run rather than regrade."
        ) from exc


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
