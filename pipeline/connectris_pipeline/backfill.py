"""Adding notes to boards that shipped before there were any.

The gloss stage runs on the night a board is written, which leaves every board written
before it existed with rows that do not open. This is the one-off that fixes them, and it
is a separate module from `nightly.py` for the same reason `nightly.py` is separate from
`pipeline.py`: it decides what to spend, and that decision is worth reading on its own.

It is deliberately not a nightly job. Backfilling is finished the moment it has run, and
a scheduled task that re-reads every board every night to find nothing to do is a bill
with no upside. Run it by hand, once, and again if a board ever lands without notes.

Where the boards come from and where they go back to is the caller's business — the game's
database on Cloud Run, `puzzles.json` on a laptop — so this takes a list and a writer and
knows about neither.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field, replace

from .config import Config
from .llm import LLM
from .spec import Puzzle
from .stages import gloss

log = logging.getLogger(__name__)


@dataclass
class Backfill:
    """What it did, per board, so the summary is not a number to be trusted."""

    glossed: list[str] = field(default_factory=list)
    #: Board id -> why its notes were not written. A failure here costs one board.
    failed: dict[str, str] = field(default_factory=dict)
    #: Boards that already had notes, or that the limit stopped it reaching.
    skipped: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"{len(self.glossed)} board(s) explained, "
            f"{len(self.failed)} failed, {len(self.skipped)} skipped"
        ]
        lines.extend(f"  ok      {pid}" for pid in self.glossed)
        lines.extend(f"  failed  {pid}: {why}" for pid, why in self.failed.items())
        return "\n".join(lines)


def wants_notes(puzzle: Puzzle) -> bool:
    """Any row without notes. Not `all` — a half-explained board is the case to fix."""
    return any(g.notes is None for g in puzzle.groups)


async def backfill(
    llm: LLM,
    cfg: Config,
    boards: list[Puzzle],
    write: Callable[[Puzzle], None],
    *,
    force: bool = False,
    limit: int | None = None,
) -> Backfill:
    """Explain every board that has no notes yet, writing each one as it lands.

    One board at a time, and written the moment it is finished rather than at the end. A
    backfill over a year of boards is minutes of model calls, and a run that is killed
    part-way has to keep what it paid for — the same rule the pipeline's own writer
    follows, for the same reason.

    A board whose notes do not line up is logged and skipped, never partially written:
    the board is already published and playable, and the worst outcome here is a note
    filed under the wrong word.
    """
    done = Backfill()

    for puzzle in boards:
        if not force and not wants_notes(puzzle):
            done.skipped.append(puzzle.id)
            continue
        if limit is not None and len(done.glossed) + len(done.failed) >= limit:
            done.skipped.append(puzzle.id)
            continue

        try:
            explained = await gloss(llm, cfg, puzzle)
        except Exception as exc:
            log.warning("could not explain %s: %s", puzzle.id, exc)
            done.failed[puzzle.id] = f"{type(exc).__name__}: {exc}"
            continue

        write(explained)
        done.glossed.append(puzzle.id)
        log.info("explained %s", puzzle.id)

    return done


__all__ = ["Backfill", "backfill", "wants_notes"]


@dataclass
class Concepts:
    """What a concept backfill did. Same shape as `Backfill`, and for the same reason."""

    named: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return f"{len(self.named)} board(s) given concepts, {len(self.skipped)} skipped"


def concepts_for(puzzle: Puzzle, known: dict[str, str]) -> Puzzle | None:
    """Fill in the concepts a board is missing, or None if it needs none.

    No model, and it does not need one for an English board: the label already *is* an
    English noun phrase, which is what a concept is. `known` overrides it wherever a
    hand-written concept exists for that exact label, because "Styles of drinking glasses"
    is better recorded as the idea — drinking vessels — than as its own wording.

    A board in another language is skipped rather than guessed at. Its label is not English
    and there is nothing here that could make it so; boards written from now on carry a
    concept from the proposer, and the handful that predate that are a job for a person.
    """
    if puzzle.language != "en" or all(g.concept for g in puzzle.groups):
        return None
    return replace(
        puzzle,
        groups=[
            g if g.concept else replace(g, concept=known.get(g.label) or g.label.lower())
            for g in puzzle.groups
        ],
    )


def name_concepts(
    boards: list[Puzzle], write: Callable[[Puzzle], None], known: dict[str, str]
) -> Concepts:
    """Give every published board a concept, so the cross-language index has something to
    compare against.

    Without this the index is present and inert: the boards that shipped before the field
    existed carry none, so a Swedish batch is told nothing has shipped and re-invents the
    English catalogue in translation — which is exactly what it did, banking
    *Bleckblåsinstrument* against a live English board called "Orchestral brass
    instruments".
    """
    done = Concepts()
    for board in boards:
        named = concepts_for(board, known)
        if named is None:
            done.skipped.append(board.id)
            continue
        write(named)
        done.named.append(board.id)
    return done
