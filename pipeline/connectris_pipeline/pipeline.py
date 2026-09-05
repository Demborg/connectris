"""The orchestrator.

Proposal is a first pass with the corpus growing as each one lands, so the fifth puzzle
of a batch already knows what the first four used — in-batch dedupe has to happen while
there is still something to change, not at the end. Evaluation is then embarrassingly
parallel, because the candidates no longer interact.

Deterministic checks run between proposal and the expensive stages: there is no point
paying nine solver calls to discover a board has a word in it twice.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .categories import DEFAULT_POOL, CategorySource, JsonCategorySource
from .config import Config
from .corpus import load as load_corpus
from .llm import LLM, Ledger
from .record import Candidate, decide
from .scoring import score
from .spec import Corpus, Puzzle, is_fatal, validate
from .stages import grade, invent, propose, red_team, solve

log = logging.getLogger(__name__)


@dataclass
class Run:
    candidates: list[Candidate]
    ledger: Ledger
    directory: Path | None = None

    def by_verdict(self, verdict: str) -> list[Candidate]:
        return [c for c in self.candidates if c.decision and c.decision.verdict == verdict]

    def summary(self) -> str:
        counts = {v: len(self.by_verdict(v)) for v in ("accept", "review", "reject")}
        led = self.ledger.summary()
        lines = [
            f"{len(self.candidates)} candidates: {counts['accept']} accepted, "
            f"{counts['review']} to review, {counts['reject']} rejected",
            f"{led['calls']} model calls, "
            f"{led['input_tokens']:,} in / {led['output_tokens']:,} out "
            f"({led['thinking_tokens']:,} thinking)",
        ]
        for c in self.candidates:
            verdict = c.decision.verdict if c.decision else "?"
            recovery = f"{c.stats.mean_recovery:.0%}" if c.stats else "  - "
            head = f"  {verdict:<7} {c.id}  recovery {recovery:>4}  {c.puzzle.name}"
            lines.append(head)
            lines.extend(
                f"            {reason}" for reason in (c.decision.reasons if c.decision else [])[:3]
            )
        return "\n".join(lines)


async def evaluate(llm: LLM, cfg: Config, candidate: Candidate, corpus: Corpus) -> Candidate:
    """Gather the evidence, then decide. Straight line, no loop.

    There was a revision loop here: a grader verdict of `revise` came with a rewritten
    board, which went back around from validation. A real run retired it. It fired on 6
    of 20 candidates and cost 22% of the batch's calls, and the grader then rejected its
    own rewrite in 4 of those 6. It also overwrote the pre-revision record — board,
    solver attempts, red-team report and first grade all gone — so the one question
    DESIGN.md asked about it was unanswerable from the artifacts it wrote.

    Since proposing a fresh board is one call and re-evaluating a rewrite is three, a
    grader that wants a revision now just says so and the candidate goes to review.
    """
    candidate.problems = validate(candidate.puzzle, corpus)
    if not is_fatal(candidate.problems):
        candidate.attempts = await solve(llm, cfg, candidate.puzzle)
        candidate.stats = score(candidate.puzzle, candidate.attempts)
        candidate.red = await red_team(llm, cfg, candidate.puzzle, candidate.traps)
        candidate.grade = await grade(llm, cfg, candidate)

    candidate.decision = decide(candidate, cfg.thresholds)
    return candidate


async def run(
    llm: LLM,
    cfg: Config,
    *,
    count: int,
    seed: int = 0,
    out_dir: Path | None = None,
    corpus: Corpus | None = None,
    examples: list[Puzzle] | None = None,
    source: CategorySource | None = None,
) -> Run:
    if corpus is None:
        corpus = load_corpus()[1]
    if examples is None:
        examples = load_corpus()[0][:2]
    if source is None:
        source = JsonCategorySource(DEFAULT_POOL)

    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    directory = None if out_dir is None else (out_dir / stamp)
    gate = asyncio.Semaphore(cfg.concurrency)

    # Drawn up front, not inside the tasks. Drawing from the shared rng inside a task
    # makes each candidate's seed depend on scheduling order, so a "reproducible" run
    # would only be reproducible while the semaphore happened not to suspend.
    rng = random.Random(seed)

    # Stage zero: top the pool up if it cannot cover the batch, then allocate. Novelty is
    # settled here, before a single board is written, rather than by discarding boards the
    # proposer has already thought hard about.
    if len(source.known()) < count:
        try:
            banked = await invent(llm, cfg, source, count=cfg.invent_batch)
            log.info("banked %d new categories", banked)
        except Exception:
            log.exception("category invention failed; allocating from what the pool has")
    slots = source.allocate(count, rng=rng)

    # Pass one: propose, folding each board into the corpus as it lands so later prompts
    # avoid earlier boards. No lock: the blocks that touch `corpus` contain no await, and
    # asyncio only switches tasks at an await, so they are already atomic.
    #
    # This is best-effort, not the dedupe check. With concurrency >= count every proposal
    # starts before any has landed, so it prevents nothing at a default batch size; it is
    # here to save tokens when it can, and `everything_but` below is what actually decides.
    shipped = Corpus(set(corpus.words), set(corpus.labels))

    async def one(index: int) -> Candidate:
        async with gate:
            cid = f"gen-{stamp}-{index:02d}"
            try:
                candidate = await propose(
                    llm,
                    cfg,
                    candidate_id=cid,
                    slot=slots[index],
                    examples=examples,
                    corpus=Corpus(set(corpus.words), set(corpus.labels)),
                )
            except Exception:
                log.exception("proposal %s failed", cid)
                return Candidate(
                    id=cid,
                    puzzle=Puzzle(id=cid, name="(failed)", groups=[]),
                    error=_last_error(),
                )
            corpus.extend(candidate.puzzle)
            return candidate

    candidates = list(await asyncio.gather(*map(one, range(count))))

    def everything_but(candidate: Candidate) -> Corpus:
        """What this board must be new against: everything shipped, plus its siblings.

        Not the live corpus, which contains the candidate itself — that bug flagged all
        20 boards of a run as stale. Not the snapshot it was proposed against either: at
        concurrency >= count every proposal snapshots the same shipped-only corpus, so
        four of ten boards in the next run shared words with a sibling unflagged, two of
        them byte-identical rows that reached accepted.json. Rebuilding per candidate is
        O(n^2) on a batch of twenty, which is free.
        """
        against = Corpus(set(shipped.words), set(shipped.labels))
        for other in candidates:
            if other.id != candidate.id and not other.error:
                against.extend(other.puzzle)
        return against

    # Pass two: the candidates no longer interact, so evaluate them all at once. Each
    # writes itself out as it lands, so a run that is killed part-way keeps what it paid
    # for rather than discarding the batch.
    writer = _Writer(directory)

    async def check(candidate: Candidate) -> Candidate:
        if not candidate.error:
            async with gate:
                try:
                    candidate = await evaluate(llm, cfg, candidate, everything_but(candidate))
                except Exception:
                    log.exception("%s failed during evaluation", candidate.id)
                    candidate.error = _last_error()
        if candidate.decision is None:
            candidate.decision = decide(candidate, cfg.thresholds)
        writer.append(candidate)
        return candidate

    finished = list(await asyncio.gather(*(check(c) for c in candidates)))
    result = Run(candidates=finished, ledger=llm.ledger, directory=directory)
    if directory is not None:
        write(result, cfg, directory)
    return result


def _last_error() -> str:
    """The exception being handled, as one line for the record."""
    exc = sys.exception()
    return f"{type(exc).__name__}: {exc}"


class _Writer:
    """Streams candidates into candidates.jsonl as they finish.

    The first real run took 25 minutes and wrote nothing until the very end, so a
    timeout would have thrown away every token it had spent. `write` still rewrites the
    file at the end — this is the crash-only copy, not the authoritative one.
    """

    def __init__(self, directory: Path | None) -> None:
        self._path = None if directory is None else directory / "candidates.jsonl"
        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text("")

    def append(self, candidate: Candidate) -> None:
        if self._path is None:
            return
        with self._path.open("a") as fh:
            fh.write(json.dumps(candidate.to_json(), ensure_ascii=False) + "\n")


def write(result: Run, cfg: Config, directory: Path) -> Path:
    """One directory per run, everything in it, nothing that needs a model to re-read."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "config.json").write_text(json.dumps(cfg.to_json(), indent=2, default=str))
    with (directory / "candidates.jsonl").open("w") as fh:
        for c in result.candidates:
            fh.write(json.dumps(c.to_json(), ensure_ascii=False) + "\n")
    (directory / "ledger.json").write_text(json.dumps(result.ledger.to_json(), indent=2))
    for verdict in ("accept", "review"):
        puzzles = [c.puzzle.to_game_json() for c in result.by_verdict(verdict)]
        (directory / f"{verdict}ed.json").write_text(json.dumps(puzzles, indent="\t") + "\n")
    (directory / "summary.txt").write_text(result.summary() + "\n")
    return directory


def reload(directory: Path) -> list[Candidate]:
    """Read a finished run back, so thresholds can be re-applied without model calls."""
    path = directory / "candidates.jsonl"
    return [
        Candidate.from_json(json.loads(line))
        for line in path.read_text().splitlines()
        if line.strip()
    ]


def regrade(directory: Path, cfg: Config) -> Run:
    candidates = reload(directory)
    for c in candidates:
        c.decision = decide(c, cfg.thresholds)
    return Run(candidates=candidates, ledger=Ledger(), directory=directory)


__all__ = ["Run", "evaluate", "regrade", "reload", "run", "write"]
