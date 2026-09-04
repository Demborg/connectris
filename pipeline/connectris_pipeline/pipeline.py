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
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .config import Config
from .corpus import load as load_corpus
from .llm import LLM, Ledger
from .record import Candidate, decide
from .scoring import score
from .spec import Corpus, Puzzle, is_fatal, validate
from .stages import grade, propose, red_team, solve, to_puzzle

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
            for reason in (c.decision.reasons if c.decision else [])[:3]:
                lines.append(f"            {reason}")
        return "\n".join(lines)


async def evaluate(llm: LLM, cfg: Config, candidate: Candidate, corpus: Corpus) -> Candidate:
    """Solve, red-team, grade, and take the grader's revision once if it offers one."""
    for attempt in range(cfg.max_revisions + 1):
        candidate.problems = validate(candidate.puzzle, corpus)
        if is_fatal(candidate.problems):
            break

        attempts = await solve(llm, cfg, candidate.puzzle)
        candidate.attempts = attempts
        candidate.stats = score(candidate.puzzle, attempts)

        candidate.red = await red_team(llm, cfg, candidate.puzzle, candidate.traps)
        candidate.grade = await grade(llm, cfg, candidate)

        revised = candidate.grade.revised_groups
        if candidate.grade.verdict != "revise" or not revised:
            break
        if attempt == cfg.max_revisions:
            # Out of revisions with the grader still asking for one. Keep this record
            # rather than an unevaluated rewrite; `decide` reads the standing 'revise'
            # off the grade and sends it to review.
            break

        puzzle, traps = to_puzzle(revised, candidate.puzzle.id, candidate.puzzle.name)
        log.info("%s: taking the grader's revision", candidate.id)
        candidate = Candidate(
            id=candidate.id,
            puzzle=puzzle,
            traps=traps,
            seed=candidate.seed,
            revision=candidate.revision + 1,
        )

    # If it fell out of the loop still asking for another revision, `decide` reads that
    # off the grade and sends it to review rather than shipping it.
    candidate.problems = validate(candidate.puzzle, corpus)
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
) -> Run:
    if corpus is None or examples is None:
        shipped, shipped_corpus = load_corpus()
        examples = examples if examples is not None else shipped[:2]
        corpus = corpus if corpus is not None else shipped_corpus

    ledger = llm.ledger
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    rng = random.Random(seed)
    gate = asyncio.Semaphore(cfg.concurrency)

    # Pass one: propose, folding each board into the corpus as it lands.
    lock = asyncio.Lock()
    candidates: list[Candidate] = []
    #: What the corpus looked like when each candidate was proposed — which is exactly
    #: what its prompt was told to avoid. Pass two validates against this and not against
    #: the live corpus, because the live corpus contains the candidate itself by then.
    proposed_against: dict[str, Corpus] = {}

    async def one(index: int) -> None:
        async with gate:
            local = random.Random(rng.randrange(1 << 30))
            cid = f"gen-{stamp}-{index:02d}"
            try:
                async with lock:
                    snapshot = Corpus(set(corpus.words), set(corpus.labels))
                proposed_against[cid] = snapshot
                candidate = await propose(
                    llm, cfg, candidate_id=cid, rng=local, examples=examples, corpus=snapshot
                )
            except Exception as exc:
                log.error("proposal %s failed: %s", cid, exc)
                candidates.append(
                    Candidate(
                        id=cid, puzzle=Puzzle(id=cid, name="(failed)", groups=[]), error=str(exc)
                    )
                )
                return
            async with lock:
                corpus.extend(candidate.puzzle)
                candidates.append(candidate)

    await asyncio.gather(*(one(i) for i in range(count)))
    candidates.sort(key=lambda c: c.id)

    # Pass two: the candidates no longer interact, so evaluate them all at once.
    async def check(candidate: Candidate) -> Candidate:
        if candidate.error:
            candidate.decision = decide(candidate, cfg.thresholds)
            return candidate
        async with gate:
            try:
                return await evaluate(llm, cfg, candidate, proposed_against[candidate.id])
            except Exception as exc:
                log.error("%s failed during evaluation: %s", candidate.id, exc)
                candidate.error = str(exc)
                candidate.decision = decide(candidate, cfg.thresholds)
                return candidate

    finished = list(await asyncio.gather(*(check(c) for c in candidates)))
    result = Run(candidates=finished, ledger=ledger)

    if out_dir is not None:
        result.directory = write(result, cfg, out_dir / stamp)
    return result


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


__all__ = ["Run", "run", "evaluate", "write", "reload", "regrade"]
