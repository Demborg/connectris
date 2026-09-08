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
from dataclasses import dataclass, field

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
