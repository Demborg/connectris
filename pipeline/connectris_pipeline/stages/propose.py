"""Stage 1 — propose.

One puzzle per call, not a batch of ten. A single call asked for ten boards spends its
attention on the first two and then reuses their vocabulary; independent calls also mean
an independent retry, cheap parallelism, and a per-candidate diversity seed. The cost of
twenty calls a night rounds to nothing (DESIGN.md, phase 2).
"""

from __future__ import annotations

import random

from ..config import Config
from ..llm import LLM
from ..prompts import draw_seed
from ..prompts import propose as propose_prompt
from ..record import Candidate
from ..schema import ProposedGroup, ProposedPuzzle
from ..spec import Corpus, Group, Puzzle, normalise_word, slugify


def to_puzzle(
    proposed: ProposedPuzzle | list[ProposedGroup], puzzle_id: str, name: str = ""
) -> tuple[Puzzle, dict[str, str]]:
    """Model output -> board, plus the trap notes keyed by the ids we just assigned.

    Ids are ours, not the model's: they end up in the shipped JSON and in the play log,
    and a model asked for one will eventually produce a duplicate.
    """
    groups_in = proposed.groups if isinstance(proposed, ProposedPuzzle) else proposed
    title = name or (proposed.name if isinstance(proposed, ProposedPuzzle) else puzzle_id)

    groups: list[Group] = []
    traps: dict[str, str] = {}
    used: set[str] = set()
    for g in groups_in:
        gid = slugify(g.label)
        while gid in used:
            gid += "-b"
        used.add(gid)
        groups.append(
            Group(id=gid, label=g.label.strip(), words=[normalise_word(w) for w in g.words])
        )
        traps[gid] = g.trap.strip()

    return Puzzle(id=puzzle_id, name=title.strip(), groups=groups), traps


async def propose(
    llm: LLM,
    cfg: Config,
    *,
    candidate_id: str,
    rng: random.Random,
    examples: list[Puzzle],
    corpus: Corpus,
) -> Candidate:
    seed = draw_seed(rng)
    system, prompt = propose_prompt(
        seed=seed,
        examples=examples,
        avoid_words=sorted(corpus.words),
        avoid_labels=sorted(corpus.labels),
    )
    out = await llm.generate(
        stage="propose", model=cfg.proposer, system=system, prompt=prompt, schema=ProposedPuzzle
    )
    puzzle, traps = to_puzzle(out, candidate_id)
    return Candidate(id=candidate_id, puzzle=puzzle, traps=traps, seed=seed)
