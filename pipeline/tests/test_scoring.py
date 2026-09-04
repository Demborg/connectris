"""Recovery and legibility, the two numbers the whole decision rests on."""

from __future__ import annotations

from connectris_pipeline.config import Thresholds
from connectris_pipeline.schema import SolveAttempt, SolvedGroup
from connectris_pipeline.scoring import Attempt, lexical_similarity, rescale, score
from connectris_pipeline.spec import Group, Puzzle

PUZZLE = Puzzle(
    id="t",
    name="Test",
    groups=[
        Group("tools", "Hand tools", ["HAMMER", "CHISEL", "PLANE", "WRENCH"]),
        Group("weather", "Bad weather", ["FROST", "GALE", "HAZE", "SLEET"]),
        Group("rocks", "Rocks", ["SHALE", "BASALT", "CHALK", "SLATE"]),
        Group("fish", "Fish", ["PERCH", "SOLE", "BASS", "SKATE"]),
        Group("trees", "Trees", ["BIRCH", "ALDER", "ROWAN", "ASPEN"]),
    ],
)


def attempt(*groups: tuple[str, list[str]]) -> Attempt:
    return Attempt.of(
        "fake/low", 1, SolveAttempt(groups=[SolvedGroup(category=c, words=w) for c, w in groups])
    )


def perfect() -> Attempt:
    return attempt(*[(g.label, list(g.words)) for g in PUZZLE.groups])


async def test_a_perfect_attempt_recovers_everything():
    stats = await score(PUZZLE, [perfect()])
    assert stats.full_solve_rate == 1.0
    assert stats.mean_recovery == 1.0
    assert stats.well_formed == 1
    assert stats.mean_legibility == 1.0


async def test_recovery_is_per_category_and_order_free():
    """Word order inside a row is irrelevant to the game, so it must be here too."""
    half = attempt(
        ("Tools", ["WRENCH", "PLANE", "CHISEL", "HAMMER"]),
        ("Weather", ["FROST", "GALE", "HAZE", "SLEET"]),
        ("no idea", ["SHALE", "BASALT", "CHALK", "PERCH"]),
        ("no idea", ["SLATE", "SOLE", "BASS", "SKATE"]),
        ("Trees", ["BIRCH", "ALDER", "ROWAN", "ASPEN"]),
    )
    stats = await score(PUZZLE, [perfect(), half])
    assert stats.full_solve_rate == 0.5
    by_id = {g.id: g for g in stats.groups}
    assert by_id["tools"].recovery == 1.0
    assert by_id["rocks"].recovery == 0.5
    assert stats.min_recovery == 0.5


async def test_a_category_nobody_found_scores_legibility_minus_one():
    """'Never found' and 'found but unnameable' are different failures, so different numbers."""
    missed = attempt(*[("junk", list(g.words)) for g in PUZZLE.groups[:4]])
    stats = await score(PUZZLE, [missed])
    trees = next(g for g in stats.groups if g.id == "trees")
    assert trees.recovery == 0.0
    assert trees.legibility == -1.0


async def test_found_but_named_differently_scores_low_legibility():
    vague = attempt(*[("things that go together", list(g.words)) for g in PUZZLE.groups])
    stats = await score(PUZZLE, [vague])
    assert stats.mean_recovery == 1.0
    assert 0 <= stats.mean_legibility < 0.45


async def test_malformed_attempts_still_count_against_recovery():
    """A solver too confused to partition the board also failed to find the groups."""
    junk = attempt(("?", ["HAMMER", "HAMMER", "HAMMER", "HAMMER"]))
    stats = await score(PUZZLE, [perfect(), junk])
    assert stats.well_formed == 1
    assert stats.attempts == 2
    assert stats.mean_recovery == 0.5


async def test_embeddings_are_used_when_available_and_fall_back_when_not():
    async def embed(texts):
        return [[1.0, 0.0] if "Fish" in t else [0.0, 1.0] for t in texts]

    stats = await score(PUZZLE, [perfect()], embed=embed)
    assert stats.mean_legibility == 1.0

    async def broken(texts):
        return []

    assert (await score(PUZZLE, [perfect()], embed=broken)).mean_legibility == 1.0


def test_lexical_similarity_is_a_floor_not_a_measurement():
    assert lexical_similarity("Card suits", "Card suits") == 1.0
    assert lexical_similarity("Card suits", "Suits in a deck") > 0.3
    assert lexical_similarity("Card suits", "Espresso drinks") < 0.3
    assert lexical_similarity("Fish", "Things you find in the sea") < 0.45


def test_the_embedding_rescale_separates_the_measured_bands():
    """Anchored on real `gemini-embedding-2` output — see the note in scoring.py.

    The point of the rescale is that `min_legibility` lands in the gap between a genuine
    paraphrase and everything else, so these bands must stay on opposite sides of it.
    """
    paraphrase = [0.780, 0.800, 0.827, 0.883, 0.910]
    unrelated = [0.615, 0.636, 0.642]
    vague = [0.454, 0.507, 0.594]

    assert min(rescale(c) for c in paraphrase) > Thresholds().min_legibility
    assert max(rescale(c) for c in unrelated + vague) < Thresholds().min_legibility
    assert rescale(1.0) == 1.0
