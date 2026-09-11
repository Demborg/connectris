"""Loading records written by older versions of this pipeline.

`regrade` re-deciding a stored run for nothing is the whole tuning loop, and it is only
free if the records still load. Two of nine runs on disk had stopped loading before these
existed — silently, because nobody regrades an old run until the day they need to.
"""

from __future__ import annotations

import pytest

from connectris_pipeline.config import Thresholds
from connectris_pipeline.record import Candidate, StaleRecordError, decide

PUZZLE = {
    "id": "p",
    "name": "Legacy",
    "language": "en",
    "groups": [
        {"id": "a", "label": "A", "words": ["ONE", "TWO", "THREE", "FOUR"]},
        {"id": "b", "label": "B", "words": ["FIVE", "SIX", "SEVEN", "EIGHT"]},
    ],
}


def record(**extra) -> dict:
    return {"id": "legacy", "puzzle": PUZZLE} | extra


def test_a_field_this_version_dropped_is_ignored():
    """`SolveStats.min_recovery` was cut; one run on disk still carries it in 20 records."""
    raw = record(
        stats={
            "attempts": 3,
            "well_formed": 3,
            "full_solve_rate": 0.0,
            "mean_recovery": 0.4,
            "mean_legibility": 0.8,
            "min_recovery": 0.1,  # gone from the dataclass
            "by_model": {},
            "groups": [
                {"id": "a", "label": "A", "recovery": 0.4, "legibility": 0.8, "names": ["A"]}
            ],
        }
    )
    c = Candidate.from_json(raw)
    assert c.stats is not None
    assert c.stats.mean_recovery == 0.4
    assert not hasattr(c.stats, "min_recovery")


def test_a_field_this_version_gained_comes_back_empty():
    """`RedTeamReport.loose_labels` was added later. An old report listed none, truthfully."""
    raw = record(red_team={"ambiguous_words": [], "alternatives": [], "verdict": "clean"})
    c = Candidate.from_json(raw)
    assert c.red is not None
    assert c.red.loose_labels == []
    assert c.red.verdict == "clean"


def test_a_retired_verdict_becomes_the_one_that_replaced_it():
    """`revise` went when the revision loop did. Such a board is one a human should see."""
    raw = record(grade={"verdict": "revise", "fairness": 4, "elegance": 3, "reasons": "rewrite it"})
    c = Candidate.from_json(raw)
    assert c.grade is not None
    assert c.grade.verdict == "review"
    assert decide(c, Thresholds()).verdict == "review"


def test_a_missing_number_refuses_to_be_invented():
    """The line this stops at, and why it stops there.

    Defaulting `mean_recovery` to 0.0 would read as 'the solver found nothing', which is
    the signal `decide` treats as hard-or-broken — so a schema change would quietly push
    old boards toward review and the tuning loop would measure its own migration.
    """
    raw = record(
        stats={
            "attempts": 3,
            "well_formed": 3,
            "full_solve_rate": 0.0,
            "mean_legibility": 0.8,
            "by_model": {},
            "groups": [],
        }
    )
    with pytest.raises(StaleRecordError, match="mean_recovery"):
        Candidate.from_json(raw)


def test_a_record_with_nothing_but_a_board_still_decides():
    """Every stage absent is a candidate that reviews, never one that raises."""
    c = Candidate.from_json(record())
    d = decide(c, Thresholds())
    assert d.verdict == "review"
    assert any("no grade" in r for r in d.reasons)
