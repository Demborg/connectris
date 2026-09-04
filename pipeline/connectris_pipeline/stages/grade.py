"""Stage 5 — grade.

The only stage that sees everything at once: the board, the intended traps, what the weak
ensemble did with it, and what the red team found. It rates, and where one word is doing
the damage it rewrites — a revision goes back around from validation, once.
"""

from __future__ import annotations

from ..config import Config
from ..llm import LLM
from ..prompts import grade as grade_prompt
from ..record import Candidate
from ..schema import Grade


async def grade(llm: LLM, cfg: Config, candidate: Candidate) -> Grade:
    system, prompt = grade_prompt(
        puzzle=candidate.puzzle,
        traps=candidate.traps,
        solver_digest=candidate.stats.digest() if candidate.stats else "no solver data",
        red=candidate.red,
        warnings=candidate.warnings,
    )
    return await llm.generate(
        stage="grade", model=cfg.grader, system=system, prompt=prompt, schema=Grade
    )
