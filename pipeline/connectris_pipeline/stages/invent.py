"""Stage 0 — invent categories.

One cheap call per batch that proposes many categories at once, before any board exists.
The pool rejects near-duplicates and banks the rest, so novelty is settled for the price
of a single call rather than by throwing away boards the proposer has already thought hard
about.

Categories are invented in bulk here even though *boards* are proposed one at a time, and
the reason is the opposite of the reason boards are not batched: a board is a design with
five interacting parts and degrades when the model is asked for ten at once, whereas a
category is a one-line idea and asking for forty is just asking for a list.
"""

from __future__ import annotations

from ..categories import Category, CategorySource
from ..config import Config
from ..llm import LLM
from ..prompts import invent as invent_prompt
from ..schema import InventedCategories


async def invent(llm: LLM, cfg: Config, source: CategorySource, *, count: int) -> int:
    """Top the pool up. Returns how many categories were new."""
    system, prompt = invent_prompt(count=count, known=[c.label for c in source.known()])
    out = await llm.generate(
        stage="invent", model=cfg.proposer, system=system, prompt=prompt, schema=InventedCategories
    )
    return source.bank(
        [Category(label=c.label.strip(), reads_as=c.reads_as.strip()) for c in out.categories]
    )
