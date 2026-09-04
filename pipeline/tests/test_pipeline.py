"""End to end on the mock provider: no network, no credentials, real orchestration."""

from __future__ import annotations

import json

from connectris_pipeline import pipeline
from connectris_pipeline.config import Config, ModelSpec, Thresholds
from connectris_pipeline.corpus import append, load
from connectris_pipeline.mock import BANK, MockLLM
from connectris_pipeline.spec import Corpus, is_fatal, validate

CFG = Config(
    solvers=(
        ModelSpec("mock-lite", thinking_level="low"),
        ModelSpec("mock-flash", thinking_level="high"),
    ),
    attempts_per_solver=3,
    concurrency=4,
)


async def run(count: int = 6, cfg: Config = CFG, **kwargs):
    llm = MockLLM(seed=7)
    return await pipeline.run(llm, cfg, count=count, seed=7, corpus=Corpus(), examples=[], **kwargs)


async def test_every_candidate_comes_out_decided_and_well_formed():
    result = await run()
    assert len(result.candidates) == 6
    for c in result.candidates:
        assert c.decision is not None
        assert not is_fatal(validate(c.puzzle)), c.puzzle.to_game_json()
        assert c.stats is not None and c.stats.attempts == 6


async def test_a_run_produces_all_three_verdicts_worth_of_machinery():
    result = await run(count=10)
    verdicts = {c.decision.verdict for c in result.candidates}
    assert verdicts <= {"accept", "review", "reject"}
    assert result.ledger.summary()["calls"] > 0


async def test_in_batch_dedupe_stops_the_same_board_twice():
    """Proposals fold into the corpus as they land, so later ones see earlier ones."""
    result = await run(count=8)
    seen: set[frozenset[str]] = set()
    for c in result.candidates:
        key = frozenset(c.puzzle.words)
        assert key not in seen, f"{c.id} repeated a whole board"
        seen.add(key)


async def test_the_grader_revision_loop_actually_replaces_the_board():
    """The mock plants an ambiguity in a share of boards and swaps the offending word."""
    result = await run(count=10)
    revised = [c for c in result.candidates if c.revision > 0]
    assert revised, "mock should have forced at least one revision"
    for c in revised:
        assert c.grade is not None


async def test_a_run_writes_everything_needed_to_re_decide_it(tmp_path):
    result = await run(count=4, out_dir=tmp_path)
    directory = result.directory
    assert directory is not None
    for name in (
        "config.json",
        "candidates.jsonl",
        "ledger.json",
        "accepted.json",
        "reviewed.json",
    ):
        assert (directory / name).exists(), name

    reloaded = pipeline.reload(directory)
    assert [c.id for c in reloaded] == [c.id for c in result.candidates]
    assert [c.decision.verdict for c in reloaded] == [c.decision.verdict for c in result.candidates]


async def test_regrade_changes_verdicts_without_spending_anything(tmp_path):
    result = await run(count=6, out_dir=tmp_path)
    strict = Config(thresholds=Thresholds(min_mean_recovery=0.99))
    again = pipeline.regrade(result.directory, strict)
    assert again.ledger.summary()["calls"] == 0
    assert not again.by_verdict("accept")


async def test_a_proposal_that_dies_never_reaches_the_review_queue(tmp_path):
    class Broken(MockLLM):
        async def generate(self, **kwargs):
            if kwargs["stage"] == "propose":
                raise RuntimeError("no quota")
            return await super().generate(**kwargs)

    result = await pipeline.run(
        Broken(seed=1), CFG, count=2, corpus=Corpus(), examples=[], out_dir=tmp_path
    )
    assert all(c.decision.verdict == "reject" for c in result.candidates)
    assert all("no quota" in " ".join(c.decision.reasons) for c in result.candidates)


async def test_a_solver_outage_degrades_to_review_rather_than_a_bad_accept():
    class NoSolvers(MockLLM):
        async def generate(self, **kwargs):
            if kwargs["stage"] == "solve":
                raise RuntimeError("solver down")
            return await super().generate(**kwargs)

    result = await pipeline.run(NoSolvers(seed=2), CFG, count=2, corpus=Corpus(), examples=[])
    for c in result.candidates:
        assert c.stats.attempts == 0
        assert c.decision.verdict == "review"


async def test_export_round_trips_into_the_games_own_json(tmp_path):
    """The exported shape has to be exactly what puzzles.json holds."""
    result = await run(count=6)
    accepted = result.by_verdict("accept") or result.by_verdict("review")
    assert accepted

    shipped, _ = load()
    target = tmp_path / "puzzles.json"
    target.write_text(json.dumps([p.to_game_json() for p in shipped], indent="\t"))

    added = append([c.puzzle for c in accepted], target)
    assert added == len(accepted)
    assert append([c.puzzle for c in accepted], target) == 0, "ids should not double up"

    reloaded, _ = load(target)
    assert len(reloaded) == len(shipped) + len(accepted)
    for p in reloaded:
        assert not is_fatal(validate(p))


async def test_a_candidate_is_never_deduped_against_itself():
    """The bug that made the accept rate structurally zero.

    Proposals fold into the shared corpus as they land, so by the time pass two runs the
    corpus contains the candidate under test. Validating against the live corpus reported
    every board as 20 stale words and 5 stale categories, and the grader was shown those
    as evidence. Each candidate is checked against what existed when it was proposed.
    """
    # One candidate against an empty corpus: the only collision available is with itself.
    result = await run(count=1)
    (candidate,) = result.candidates
    assert candidate.warnings == [], "a lone candidate was deduped against itself"


async def test_a_genuine_collision_is_still_caught():
    """The fix must not have turned the dedupe stage off.

    Two checks, because they fail differently: against a shipped corpus, and between two
    candidates in the same batch — the in-batch half is the whole point of folding each
    board into the corpus as it lands.
    """
    shipped = Corpus(words={w for _, ws, _ in BANK for w in ws}, labels=set())
    against_shipped = await pipeline.run(
        MockLLM(seed=7), CFG, count=1, seed=7, corpus=shipped, examples=[]
    )
    assert "stale-words" in [p.code for c in against_shipped.candidates for p in c.problems]

    # The mock draws 5 categories from a bank of 15, so 6 boards must collide with a
    # sibling somewhere.
    in_batch = await run(count=6)
    assert "stale-category" in [p.code for c in in_batch.candidates for p in c.problems]
