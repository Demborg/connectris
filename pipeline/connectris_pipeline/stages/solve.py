"""Stage 2 — solve.

One deliberately weak model, one attempt. What comes back is a solve rate, which is a
difficulty proxy; both ends of the band get pruned. Failure is swallowed on purpose — a
solver that errors leaves no evidence, not a dead candidate.

This was an ensemble of three models at three attempts each until a real run showed the
three correlated 0.71 to 0.85 and that three attempts reproduced nine on every verdict.
See `Config.solver`.

The board is still shuffled before it is shown, and the shuffle still carries a seed. That
is not for variety any more — it is so the solver is never handed the words in solution
order, which would measure the proposer's formatting rather than the puzzle.
"""

from __future__ import annotations

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
    seed = attempt_seed(puzzle.id, model.key, 0)
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
        return []
    return [Attempt.of(model.key, seed, out)]
