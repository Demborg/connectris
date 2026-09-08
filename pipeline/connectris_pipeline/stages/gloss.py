"""Stage 6 — gloss.

The one stage that runs *after* a board is accepted, and the only one whose output a
player reads. Everything before it decides whether the board ships; this writes the
reference note that appears under each row once it is on the table — what the category
was, and what each of its four words actually is.

It is here rather than in `propose` for a cost reason and a quality one. Cost: 45% of
proposed boards are thrown away, and glossing them would be paying to explain puzzles
nobody will ever see. Quality: the proposer is arguing for its board while it writes it,
and notes written in that frame come out as advocacy — "a classic misdirection" — where
what is wanted is "Adolphe Sax, the Belgian instrument maker".

Notes are written for every row or for none. A board where three of five bars open reads
as two that are broken, so `attach` refuses a set that does not line up rather than
writing the part of it that does.
"""

from __future__ import annotations

from dataclasses import replace

from ..config import Config
from ..language import of as language_of
from ..llm import LLM
from ..prompts import gloss as gloss_prompt
from ..schema import GlossedCategory, PuzzleGloss
from ..spec import Group, Notes, Puzzle, WordNote, label_key, normalise_word


class GlossError(RuntimeError):
    """The notes do not describe this board, so none of them are kept.

    Raised rather than logged-and-swallowed because the callers want the choice: the
    nightly job publishes the board without notes, and the backfill command moves on to
    the next board.
    """


async def gloss(llm: LLM, cfg: Config, puzzle: Puzzle) -> Puzzle:
    """The board, with a note on every category and every word. Same board otherwise."""
    system, prompt = gloss_prompt(puzzle, language_of(puzzle.language))
    out = await llm.generate(
        stage="gloss",
        model=cfg.glosser,
        system=system,
        prompt=prompt,
        schema=PuzzleGloss,
    )
    return attach(puzzle, out)


def attach(puzzle: Puzzle, out: PuzzleGloss) -> Puzzle:
    """Pair the model's notes with the board, or raise.

    Deterministic and free, so it is a separate function: what the model got wrong about
    this is caught by matching rather than by trusting, and the matching is worth being
    able to test without a model.
    """
    matched = _by_label(puzzle, out) or _by_position(puzzle, out)
    if matched is None:
        labels = ", ".join(repr(c.label) for c in out.categories)
        raise GlossError(f"{puzzle.id}: notes name {labels}, which is not this board")

    return replace(
        puzzle,
        groups=[
            # `replace`, not a fresh Group: this rebuilds every board that ships, so a
            # field spelled out here is a field that silently vanishes the day someone
            # adds another one. `concept` was lost exactly that way.
            replace(g, notes=_notes_for(g, matched[g.id]))
            for g in puzzle.groups
        ],
    )


def _by_label(puzzle: Puzzle, out: PuzzleGloss) -> dict[str, GlossedCategory] | None:
    """Matched on the label the model echoed back, loosely — the reliable way round.

    `label_key` is the same fold the dedupe index uses, so a note that came back with the
    capitalisation or the punctuation changed still finds its row.
    """
    found: dict[str, GlossedCategory] = {}
    for c in out.categories:
        key = label_key(c.label)
        for g in puzzle.groups:
            if label_key(g.label) == key and g.id not in found:
                found[g.id] = c
                break
    return found if len(found) == len(puzzle.groups) else None


def _by_position(puzzle: Puzzle, out: PuzzleGloss) -> dict[str, GlossedCategory] | None:
    """The fallback: the prompt asks for the categories in the order it gave them.

    Only when the count is exactly right, and only because a label rewritten past
    recognition is otherwise a whole board's notes thrown away for a formatting habit.
    Position alone would be the wrong primary rule — a reordered reply would silently
    file every note under the wrong row — which is why it is second and conditional.
    """
    if len(out.categories) != len(puzzle.groups):
        return None
    return {g.id: c for g, c in zip(puzzle.groups, out.categories, strict=True)}


def _notes_for(group: Group, category: GlossedCategory) -> Notes:
    """One row's notes, in the row's own word order, or raise.

    Every word must have a line. A note under the wrong word is read as a fact about that
    word, which is worse than no note at all, so this insists on an exact cover of the
    row rather than filling the gaps with the ones it did get.
    """
    lines = {normalise_word(w.word): w.note.strip() for w in category.words}
    missing = [w for w in group.words if not lines.get(normalise_word(w))]
    if missing:
        raise GlossError(f"group {group.id!r} has no note for {', '.join(missing)}")

    summary = category.summary.strip()
    if not summary:
        raise GlossError(f"group {group.id!r} has no summary")

    return Notes(
        summary=summary,
        words=[WordNote(word=w, note=lines[normalise_word(w)]) for w in group.words],
    )
