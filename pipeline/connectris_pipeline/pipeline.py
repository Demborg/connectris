"""The orchestrator.

One candidate at a time, and stop at the first one accepted. The game ships one puzzle a
day, so a night that gets a good board out of its first proposal has nothing to do with a
second — and `propose` is two thirds of what a candidate costs, so a proposal not made is
the only saving of any size on offer.

Going sequential also fixes what parallel proposal could never do. Each board is supposed
to dedupe against the ones proposed before it, which requires them to have landed; run
concurrently they all start against the same empty snapshot, and a second, quadratic pass
had to rebuild each candidate's sibling corpus afterwards to catch what the first pass
missed. In a loop the corpus is simply correct when it is read.

Deterministic checks run between proposal and the expensive stages: there is no point
paying solver calls to discover a board has a word in it twice.
"""

from __future__ import annotations

import json
import logging
import random
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .categories import CategorySource, source_for
from .config import Config
from .corpus import load as load_corpus
from .language import get as get_language
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
    stop_on_accept: bool = True,
) -> Run:
    """Propose and evaluate one board at a time, stopping at the first that is accepted.

    `count` is a ceiling, not a quantity. The game ships one puzzle a day, so a night that
    accepts its first candidate has no use for a second — and since the whole bill is
    `propose` calls that already happened, not proposing is the only real saving there is.
    At the measured 55% acceptance a ceiling of five costs 1.78 candidates on average and
    lands a board 98% of nights, against 5.00 candidates for the same 98% in batch. The
    ceiling stopped being a cost knob and became a reliability one.

    Sequential is also what the batch version was pretending to be. It folded each
    proposal into the corpus as it landed so later boards would avoid earlier ones, then
    noted in a comment that at `concurrency >= count` every proposal starts before any has
    landed, so it prevented nothing — which is why `everything_but` had to rebuild a
    per-candidate corpus afterwards to catch the siblings it had missed. One at a time,
    the first mechanism simply works and the second is not needed.
    """
    lang = get_language(cfg.language)

    # Everything a batch shares is language-bound. The dedupe index is narrowed because a
    # word being taken in English says nothing about Swedish; the pool because a category
    # is a label in a language; the examples because a board is the standard it sets.
    if corpus is None:
        corpus = load_corpus(language=lang.code)[1]
    if examples is None:
        # Falling back to English boards when none have shipped in this language is a
        # deliberate, marked compromise, not an oversight: the examples carry the
        # construction standard, and starting with none costs more quality than starting
        # with the wrong language does. The proposer is told what they are and told not to
        # translate them (see `prompts.output_language`). Replace them with three
        # hand-written Swedish boards and this line goes away.
        examples = load_corpus(language=lang.code)[0][:2] or load_corpus()[0][:2]
    if source is None:
        source = source_for(lang)

    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    directory = None if out_dir is None else (out_dir / stamp)

    # Drawn up front so a seed reproduces a run. Nothing suspends between draws now, but
    # the guarantee is worth keeping explicit.
    rng = random.Random(seed)

    # Stage zero: top the pool up if it cannot cover the ceiling. Novelty is settled here,
    # before a single board is written, rather than by discarding boards the proposer has
    # already thought hard about.
    if len(source.known()) < count:
        try:
            banked = await invent(llm, cfg, source, count=cfg.invent_batch)
            log.info("banked %d new categories", banked)
        except Exception:
            log.exception("category invention failed; allocating from what the pool has")

    # Our own copy: `run` must not leave the caller's corpus carrying boards that were
    # proposed and then thrown away.
    against = Corpus(set(corpus.words), set(corpus.labels))

    writer = _Writer(directory)
    candidates: list[Candidate] = []

    for index in range(count):
        cid = f"gen-{stamp}-{index:02d}"

        # One slot at a time, because allocation marks a theme as recently used and a
        # ceiling of five would otherwise burn five themes to ship one board. Two
        # candidates in a night may now draw the same device; that costs nothing, because
        # they are competing drafts of the same day's board rather than a series.
        (slot,) = source.allocate(1, rng=rng)

        try:
            candidate = await propose(
                llm,
                cfg,
                candidate_id=cid,
                slot=slot,
                examples=examples,
                corpus=Corpus(set(against.words), set(against.labels)),
                lang=lang,
            )
        except Exception:
            log.exception("proposal %s failed", cid)
            candidate = Candidate(
                id=cid,
                puzzle=Puzzle(id=cid, name="(failed)", groups=[], language=lang.code),
                error=_last_error(),
            )

        if not candidate.error:
            try:
                # `against` holds everything shipped plus every sibling proposed tonight,
                # and never this candidate: it is folded in below, after it is judged.
                candidate = await evaluate(llm, cfg, candidate, against)
            except Exception:
                log.exception("%s failed during evaluation", candidate.id)
                candidate.error = _last_error()

        if candidate.decision is None:
            candidate.decision = decide(candidate, cfg.thresholds)

        # Written as it lands, so a run that is killed part-way keeps what it paid for.
        writer.append(candidate)
        candidates.append(candidate)

        if not candidate.error:
            against.extend(candidate.puzzle)

        if stop_on_accept and candidate.decision.verdict == "accept":
            log.info("accepted %s on candidate %d of at most %d", cid, index + 1, count)
            break

    result = Run(candidates=candidates, ledger=llm.ledger, directory=directory)
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
