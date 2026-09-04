"""The decision is a pure function over the record. These are its edges."""

from __future__ import annotations

from connectris_pipeline.config import Thresholds
from connectris_pipeline.record import Candidate, decide
from connectris_pipeline.schema import (
    AlternativePartition,
    AmbiguousWord,
    Grade,
    RedTeamReport,
    SolvedGroup,
)
from connectris_pipeline.scoring import GroupStat, SolveStats
from connectris_pipeline.spec import Group, Problem, Puzzle

T = Thresholds()


def stats(recovery: float = 0.4, legibility: float = 0.9, full: float = 0.1) -> SolveStats:
    """`legibility` no longer gates anything — it reaches the grader as prose instead."""
    groups = [GroupStat(f"g{i}", f"G{i}", recovery, legibility) for i in range(5)]
    return SolveStats(
        attempts=9,
        well_formed=8,
        full_solve_rate=full,
        mean_recovery=recovery,
        min_recovery=recovery,
        mean_legibility=legibility,
        groups=groups,
        by_model={"fake@1.0": recovery},
    )


def candidate(**kwargs) -> Candidate:
    base = dict(
        id="c",
        puzzle=Puzzle("c", "C", [Group("g", "G", ["A", "B", "C", "D"])]),
        stats=stats(),
        red=RedTeamReport(ambiguous_words=[], alternatives=[], verdict="clean"),
        grade=Grade(verdict="accept", fairness=5, elegance=4, reasons=""),
    )
    return Candidate(**{**base, **kwargs})


def test_clean_through_every_stage_is_accepted():
    assert decide(candidate(), T).verdict == "accept"


def test_an_alternative_partition_is_fatal():
    red = RedTeamReport(
        ambiguous_words=[],
        alternatives=[AlternativePartition(groups=[SolvedGroup(category="x", words=[])], why="")],
        verdict="broken",
    )
    assert decide(candidate(red=red), T).verdict == "reject"


def test_one_ambiguous_word_blocks_auto_accept_without_killing_the_puzzle():
    red = RedTeamReport(
        ambiguous_words=[
            AmbiguousWord(word="SOLE", intended_label="Fish", also_fits="Shoes", why="")
        ],
        alternatives=[],
        verdict="soft",
    )
    decision = decide(candidate(red=red), T)
    assert decision.verdict == "review"
    assert any("SOLE" in r for r in decision.reasons)


def test_too_easy_is_rejected():
    assert decide(candidate(stats=stats(recovery=0.95, full=0.8)), T).verdict == "reject"


def test_nothing_landing_goes_to_review_because_hard_and_broken_look_alike():
    """The whole reason the review queue exists rather than a second threshold."""
    assert decide(candidate(stats=stats(recovery=0.0)), T).verdict == "review"


def test_a_fatal_spec_problem_short_circuits_everything():
    c = candidate(problems=[Problem("duplicate-word", "twice")])
    decision = decide(c, T)
    assert decision.verdict == "reject"
    assert decision.reasons == ["[fatal] duplicate-word: twice"]


def test_a_stage_error_can_never_be_accepted():
    assert decide(candidate(error="429 forever"), T).verdict == "reject"


def test_missing_evidence_is_a_review_not_an_accept():
    assert decide(candidate(stats=None, red=None, grade=None), T).verdict == "review"


def test_thresholds_are_the_only_thing_that_changed_between_these_two():
    c = candidate(stats=stats(recovery=0.4))
    assert decide(c, Thresholds()).verdict == "accept"
    assert decide(c, Thresholds(min_mean_recovery=0.5)).verdict == "review"
