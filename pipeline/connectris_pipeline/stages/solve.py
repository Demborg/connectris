"""Stage 2 — solve.

One deliberately weak model, three attempts. What comes back is a recovery rate, which is
a difficulty proxy. Failure is swallowed on purpose — a solver that errors leaves one
fewer data point, not a dead candidate.

Three, not one, because one attempt quantises recovery to multiples of 0.2 and the gate
that reads it stops being a band (see `Config.attempts`). Three, not nine, because three
models at three attempts each reproduced the same verdict on 20 boards out of 20.

Each attempt gets its own seed and its own shuffle of the board. The shuffle is not for
variety — it is so the solver is never handed the words in solution order, which would
measure the proposer's formatting rather than the puzzle.
"""

from __future__ import annotations

import asyncio
import logging
import random
import zlib

from ..config import Config
from ..llm import LLM
from ..prompts import solve as solve_prompt
from ..schema import SolveAttempt
from ..scoring import Attempt
from ..spec import Puzzle, normalise_word

log = logging.getLogger(__name__)


def attempt_seed(puzzle_id: str, model_key: str, index: int) -> int:
    """Distinct per attempt, identical between runs. crc32 because `hash` is salted."""
    return zlib.crc32(f"{puzzle_id}/{model_key}/{index}".encode()) & 0x7FFFFFFF


def board_order(puzzle: Puzzle, seed: int) -> list[str]:
    """Shuffled, and shuffled the same way for the same seed.

    Never hand a solver the words in solution order — it would score the proposer's
    formatting rather than the puzzle.
    """
    words = [normalise_word(w) for w in puzzle.words]
    random.Random(seed).shuffle(words)
    return words


async def solve(llm: LLM, cfg: Config, puzzle: Puzzle) -> list[Attempt]:
    model = cfg.solver

    async def one(index: int) -> Attempt | None:
        seed = attempt_seed(puzzle.id, model.key, index)
        system, prompt = solve_prompt(board_order(puzzle, seed))
        try:
            out = await llm.generate(
                stage="solve",
                model=model,
                system=system,
                prompt=prompt,
                schema=SolveAttempt,
                seed=seed,
            )
        except Exception as exc:
            log.warning("solver %s gave up on %s: %s", model.key, puzzle.id, exc)
            return None
        return Attempt.of(model.key, seed, out)

    attempts = await asyncio.gather(*(one(i) for i in range(cfg.attempts)))
    return [a for a in attempts if a is not None]
