"""Stage 4 — red team.

The critical stage, and not the same as solving: a solver that happens to find the
intended answer says nothing about whether a second answer exists. Ambiguity is the
failure mode that makes players furious, so this model is shown the key and paid to break
it (DESIGN.md, phase 2 sketch).
"""

from __future__ import annotations

from ..config import Config
from ..llm import LLM
from ..prompts import red_team as red_team_prompt
from ..schema import RedTeamReport
from ..spec import Puzzle


async def red_team(llm: LLM, cfg: Config, puzzle: Puzzle, traps: dict[str, str]) -> RedTeamReport:
    system, prompt = red_team_prompt(puzzle, traps)
    return await llm.generate(
        stage="red_team", model=cfg.red_team, system=system, prompt=prompt, schema=RedTeamReport
    )
