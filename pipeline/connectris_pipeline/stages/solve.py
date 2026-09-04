"""Stage 2 — solve.

An ensemble of deliberately weak models, several attempts each. What comes back is a solve
rate, which is a difficulty proxy; both ends of the band get pruned. Failures are swallowed
on purpose — a solver that errors is one fewer data point, not a dead candidate.

**Attempts differ by seed, not by temperature.** Gemini 3's guidance is to leave
temperature at its default: below 1.0 the models loop and degrade on exactly the kind of
reasoning this stage is measuring. So each attempt gets its own `seed` in the generation
config, and its own shuffle of the board. The shuffle is the better half of that anyway —
it varies the input rather than the sampler, and it means a category only counts as
recovered if it survives being presented in a different order.
"""

from __future__ import annotations

import asyncio
import logging
import random
import zlib

from ..config import Config, ModelSpec
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
    async def one(model: ModelSpec, index: int) -> Attempt | None:
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

    jobs = [one(m, i) for m in cfg.solvers for i in range(cfg.attempts_per_solver)]
    return [a for a in await asyncio.gather(*jobs) if a is not None]
