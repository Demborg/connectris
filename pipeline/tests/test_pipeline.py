"""Orchestration, on a scripted model. No network, no credentials.

These test the wiring — that candidates come out decided, that artifacts round-trip, that
a stage falling over degrades rather than lies. They deliberately do not test whether the
pipeline produces *good puzzles*: a scripted model cannot answer that, and pretending
otherwise is what the mock used to do.
"""

from __future__ import annotations

import json

import pytest
from conftest import BOARDS, CONFIG, MemoryCategorySource, ScriptedLLM

from connectris_pipeline import pipeline
from connectris_pipeline.config import Config, Thresholds
from connectris_pipeline.corpus import append, load
from connectris_pipeline.record import Candidate
from connectris_pipeline.schema import Grade
from connectris_pipeline.spec import Corpus, is_fatal, validate


def verdicts(candidates: list[Candidate]) -> list[str]:
    return [c.decision.verdict for c in candidates if c.decision]


async def run(
    count: int = 3,
    cfg: Config = CONFIG,
    llm: ScriptedLLM | None = None,
    corpus: Corpus | None = None,
    *,
    stop_on_accept: bool = False,
    **kwargs,
) -> pipeline.Run:
    """A whole batch by default.

    Production stops at the first accepted board, but most of what is tested below is a
    property of *every* candidate, and a helper that stops after one would quietly reduce
    those to a sample of one. The early-exit tests ask for it explicitly.
    """
    return await pipeline.run(
        llm or ScriptedLLM(),
        cfg,
        count=count,
        seed=7,
        corpus=Corpus() if corpus is None else corpus,
        examples=[],
        source=MemoryCategorySource(["Stone fruit", "Chess tactics", "Bed linen"]),
        stop_on_accept=stop_on_accept,
        **kwargs,
    )


async def test_every_candidate_comes_out_decided():
    result = await run()
    assert len(result.candidates) == 3
    assert len(verdicts(result.candidates)) == 3


async def test_every_candidate_comes_out_shippable():
    for c in (await run()).candidates:
        assert not is_fatal(validate(c.puzzle)), c.puzzle.to_game_json()


async def test_every_candidate_carries_the_solver_evidence_it_was_judged_on():
    for c in (await run()).candidates:
        assert c.stats is not None
        assert c.stats.attempts == CONFIG.attempts


async def test_a_candidate_is_never_deduped_against_itself():
    """The bug that made the accept rate structurally zero.

    Proposals fold into the shared corpus as they land, so by pass two the corpus contains
    the candidate under test. Validating against the live corpus reported every board as
    20 stale words and 5 stale categories, and the grader was shown those as evidence.
    One candidate against an empty corpus: the only collision available is with itself.
    """
    result = await run(count=1)
    (candidate,) = result.candidates
    assert candidate.warnings == [], "a lone candidate was deduped against itself"


async def test_a_genuine_collision_is_still_caught():
    """The fix must not have turned the dedupe stage off.

    Two halves, because they fail differently: against the shipped corpus, and between two
    candidates of one batch — the in-batch half is the point of folding boards in as they
    land, and it is the half a snapshot could plausibly have broken.
    """
    shipped = Corpus(words={w for _, ws in BOARDS[0] for w in ws}, labels=set())
    against_shipped = await run(count=1, corpus=shipped)
    assert "stale-words" in [p.code for c in against_shipped.candidates for p in c.problems]

    # The scripted model cycles three boards, so the fourth repeats the first.
    in_batch = await run(count=4)
    assert "stale-words" in [p.code for c in in_batch.candidates for p in c.problems]


async def test_a_run_writes_everything_needed_to_re_decide_it(tmp_path):
    result = await run(out_dir=tmp_path)
    directory = result.directory
    assert directory is not None
    for name in ("config.json", "candidates.jsonl", "ledger.json", "accepted.json"):
        assert (directory / name).exists(), name

    reloaded = pipeline.reload(directory)
    assert [c.id for c in reloaded] == [c.id for c in result.candidates]
    assert verdicts(reloaded) == verdicts(result.candidates)


async def test_regrade_changes_verdicts_without_spending_anything(tmp_path):
    result = await run(out_dir=tmp_path)
    assert result.by_verdict("accept"), "scripted grader accepts, so there is something to lose"

    assert result.directory is not None
    strict = Config(thresholds=Thresholds(min_fairness=5, min_elegance=5))
    again = pipeline.regrade(result.directory, strict)
    assert again.ledger.summary()["calls"] == 0
    assert not again.by_verdict("accept")


async def test_a_proposal_that_dies_never_reaches_the_review_queue(tmp_path):
    class Broken(ScriptedLLM):
        async def generate(self, **kwargs) -> object:
            if kwargs["stage"] == "propose":
                raise RuntimeError("no quota")
            return await super().generate(**kwargs)

    result = await run(count=2, llm=Broken(), out_dir=tmp_path)
    assert verdicts(result.candidates) == ["reject", "reject"]
    assert all("no quota" in " ".join(c.decision.reasons) for c in result.candidates if c.decision)


async def test_a_solver_outage_degrades_to_review_rather_than_a_bad_accept():
    class NoSolvers(ScriptedLLM):
        async def generate(self, **kwargs) -> object:
            if kwargs["stage"] == "solve":
                raise RuntimeError("solver down")
            return await super().generate(**kwargs)

    result = await run(count=2, llm=NoSolvers())
    assert all(c.stats is not None and c.stats.attempts == 0 for c in result.candidates)
    assert verdicts(result.candidates) == ["review", "review"]


async def test_a_grader_rejection_is_final():
    rejects = Grade(verdict="reject", fairness=2, elegance=1, reasons="scripted")
    result = await run(count=2, llm=ScriptedLLM(grade=rejects))
    assert verdicts(result.candidates) == ["reject", "reject"]


async def test_export_round_trips_into_the_games_own_json(tmp_path):
    """The exported shape has to be exactly what puzzles.json holds."""
    result = await run(count=3)
    accepted = result.by_verdict("accept") or result.by_verdict("review")
    assert accepted

    shipped, _ = load()
    target = tmp_path / "puzzles.json"
    target.write_text(json.dumps([p.to_game_json() for p in shipped], indent="\t"))

    assert append([c.puzzle for c in accepted], target) == len(accepted)
    assert append([c.puzzle for c in accepted], target) == 0, "ids should not double up"

    reloaded, _ = load(target)
    assert len(reloaded) == len(shipped) + len(accepted)
    assert all(not is_fatal(validate(p)) for p in reloaded)


async def test_a_run_killed_part_way_keeps_what_it_paid_for(tmp_path):
    """The first real batch took 25 minutes and wrote nothing until the very end.

    A timeout would have discarded every token it had spent, in a pipeline whose stated
    principle is that a run which dies should not throw away work it already bought.
    """
    seen: list[str] = []

    class Killed(BaseException):
        """Not an Exception, so it passes straight through the per-candidate handler —
        which is what a timeout or a Ctrl-C actually does."""

    class DiesHalfway(ScriptedLLM):
        async def generate(self, **kwargs) -> object:
            if kwargs["stage"] == "grade":
                seen.append("graded")
                if len(seen) > 1:
                    raise Killed("killed")
            return await super().generate(**kwargs)

    with pytest.raises(Killed):
        await run(count=3, llm=DiesHalfway(), out_dir=tmp_path)

    (partial,) = tmp_path.glob("*/candidates.jsonl")
    survived = [json.loads(line) for line in partial.read_text().splitlines() if line.strip()]
    assert survived, "a killed run left nothing behind"
    assert survived[0]["decision"] is not None


async def test_of_two_candidates_sharing_a_row_the_second_is_the_duplicate():
    """In-batch dedupe, and the asymmetry sequential proposal buys.

    Two boards shipped byte-identical rows to accepted.json once, because at the old
    concurrency every proposal was checked against a corpus none of its siblings had
    landed in yet. Both being flagged was the fix for that, and it threw away a good board
    to punish its twin: neither could be accepted, though one of them was fine.

    In a loop there is an order, so there is an original and a copy. The first board is
    judged against a corpus that does not contain it and passes; the second is judged
    against one that now holds the first, and is caught.
    """
    twins = [BOARDS[0], BOARDS[0]]
    first, second = (await run(count=2, llm=ScriptedLLM(boards=twins))).candidates
    assert first.warnings == [], "the original was penalised for its copy"
    assert "stale-words" in [p.code for p in second.problems], second.warnings


async def test_a_night_stops_at_the_first_accepted_board():
    """The whole point of the ceiling. `propose` is two thirds of a candidate's cost, so
    a proposal not made is the only saving of any size the pipeline has."""
    result = await run(count=5, stop_on_accept=True)
    assert verdicts(result.candidates) == ["accept"]
    proposals = [c for c in result.ledger.calls if c.stage == "propose"]
    assert len(proposals) == 1, "a second board was written after one had been accepted"


async def test_a_night_keeps_going_until_something_lands():
    """A rejection is not the end of the night, or a bad first draft would take the day
    down with it. The first two candidates fail, the third is accepted, and nothing is
    proposed after that."""
    rejects = Grade(verdict="reject", fairness=2, elegance=1, reasons="scripted")

    class RejectsTwice(ScriptedLLM):
        def __init__(self) -> None:
            super().__init__()
            self.graded = 0

        async def generate(self, **kwargs) -> object:
            if kwargs["stage"] == "grade":
                self.graded += 1
                if self.graded <= 2:
                    return rejects
            return await super().generate(**kwargs)

    result = await run(count=5, llm=RejectsTwice(), stop_on_accept=True)
    assert verdicts(result.candidates) == ["reject", "reject", "accept"]


async def test_the_ceiling_is_a_ceiling_and_a_night_may_land_nothing():
    """A night where every draft fails costs the ceiling and ships no board. The gate on
    publishing is what keeps that from reaching a player, not this."""
    rejects = Grade(verdict="reject", fairness=2, elegance=1, reasons="scripted")
    result = await run(count=3, llm=ScriptedLLM(grade=rejects), stop_on_accept=True)
    assert verdicts(result.candidates) == ["reject", "reject", "reject"]
    assert not result.by_verdict("accept")


async def test_a_run_leaves_the_callers_corpus_alone():
    """Boards proposed and then thrown away must not narrow what tomorrow may write.

    The batch version folded every proposal into the corpus it was handed, so a caller
    holding that corpus across runs accumulated the vocabulary of boards no player will
    ever see.
    """
    corpus = Corpus()
    await run(count=2, corpus=corpus)
    assert corpus.words == set()
    assert corpus.labels == set()
