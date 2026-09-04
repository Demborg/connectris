"""Orchestration, on a scripted model. No network, no credentials.

These test the wiring — that candidates come out decided, that artifacts round-trip, that
a stage falling over degrades rather than lies. They deliberately do not test whether the
pipeline produces *good puzzles*: a scripted model cannot answer that, and pretending
otherwise is what the mock used to do.
"""

from __future__ import annotations

import json

import pytest
from conftest import BOARDS, CONFIG, ScriptedLLM

from connectris_pipeline import pipeline
from connectris_pipeline.config import Config, Thresholds
from connectris_pipeline.corpus import append, load
from connectris_pipeline.schema import Grade
from connectris_pipeline.spec import Corpus, is_fatal, validate


async def run(
    count: int = 3,
    cfg: Config = CONFIG,
    llm: ScriptedLLM | None = None,
    corpus: Corpus | None = None,
    **kwargs,
):
    return await pipeline.run(
        llm or ScriptedLLM(),
        cfg,
        count=count,
        seed=7,
        corpus=Corpus() if corpus is None else corpus,
        examples=[],
        **kwargs,
    )


async def test_every_candidate_comes_out_decided():
    result = await run()
    assert len(result.candidates) == 3
    assert all(c.decision is not None for c in result.candidates)


async def test_every_candidate_comes_out_shippable():
    for c in (await run()).candidates:
        assert not is_fatal(validate(c.puzzle)), c.puzzle.to_game_json()


async def test_every_candidate_carries_the_solver_evidence_it_was_judged_on():
    for c in (await run()).candidates:
        assert c.stats is not None
        assert c.stats.attempts == 1


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
    assert [c.decision.verdict for c in reloaded] == [c.decision.verdict for c in result.candidates]


async def test_regrade_changes_verdicts_without_spending_anything(tmp_path):
    result = await run(out_dir=tmp_path)
    assert result.by_verdict("accept"), "scripted grader accepts, so there is something to lose"

    strict = Config(thresholds=Thresholds(min_fairness=5, min_elegance=5))
    again = pipeline.regrade(result.directory, strict)
    assert again.ledger.summary()["calls"] == 0
    assert not again.by_verdict("accept")


async def test_a_proposal_that_dies_never_reaches_the_review_queue(tmp_path):
    class Broken(ScriptedLLM):
        async def generate(self, **kwargs):
            if kwargs["stage"] == "propose":
                raise RuntimeError("no quota")
            return await super().generate(**kwargs)

    result = await run(count=2, llm=Broken(), out_dir=tmp_path)
    assert all(c.decision.verdict == "reject" for c in result.candidates)
    assert all("no quota" in " ".join(c.decision.reasons) for c in result.candidates)


async def test_a_solver_outage_degrades_to_review_rather_than_a_bad_accept():
    class NoSolvers(ScriptedLLM):
        async def generate(self, **kwargs):
            if kwargs["stage"] == "solve":
                raise RuntimeError("solver down")
            return await super().generate(**kwargs)

    for c in (await run(count=2, llm=NoSolvers())).candidates:
        assert c.stats.attempts == 0
        assert c.decision.verdict == "review"


async def test_a_grader_rejection_is_final():
    rejects = Grade(verdict="reject", fairness=2, elegance=1, reasons="scripted")
    result = await run(count=2, llm=ScriptedLLM(grade=rejects))
    assert all(c.decision.verdict == "reject" for c in result.candidates)


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
        async def generate(self, **kwargs):
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
