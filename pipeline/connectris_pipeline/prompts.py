"""Prompts, and the seed vocabulary that keeps a batch from converging.

Kept as code rather than template files because they are the thing under active tuning
and they are meaningless apart from the schemas in schema.py.

Note what the solver prompt does *not* contain: the game's name, the rules, the trap
design, or any hint that the words were constructed. The solver's job is to be an
ordinary confused player, and every extra sentence makes it a better one than the
players we are calibrating against.
"""

from __future__ import annotations

from .categories import Slot
from .schema import RedTeamReport
from .spec import COLS, MAX_WORD_LEN, ROWS, Puzzle

GAME_BRIEF = f"""\
Connectris is a word-grouping puzzle. The board is {ROWS * COLS} words in {ROWS} rows of \
{COLS}. Each row is one category. The player rearranges the whole board and commits to a \
full arrangement, and only the leading run of correct rows from the top clears — so the \
player must also rank their rows by confidence. They get six checks.

This means a puzzle is judged on two things at once:
- Each category must have exactly one defensible membership, or a player who is right is \
told they are wrong.
- The categories must differ in how obvious they are. A board of five equally-easy \
categories gives the player nothing to rank, and the ranking is the game.
"""

CONSTRUCTION_RULES = f"""\
Hard constraints — a puzzle breaking any of these is thrown away unread:
- Exactly {ROWS} categories of exactly {COLS} words. {ROWS * COLS} distinct words, no repeats.
- Every word at most {MAX_WORD_LEN} characters. The board is four columns on a phone. \
Shorter is better; most words should be under 8.
- Plain uppercase English. No punctuation, no digits. Two words are fine if the
entry really is two words and it fits the tile.
- No word may appear inside another category's label.

What makes one good — and this is the distinction the whole thing turns on:

- **The misdirection belongs in the category, not in the word.** Write a category whose
obvious reading is wider than its real one, so a word looks like it belongs until you read
the category precisely and see that it does not. APPLE, PEACH, PLUM, MANGO and OLIVE on a
board: the row is not "fruit", it is "stone fruit" — PEACH, PLUM, MANGO and OLIVE are all
drupes and APPLE is not, so APPLE is freed for the tech companies. The player is not
counting seats; they are noticing that the category is narrower than they read it.
- **Never write a word that genuinely belongs to two categories on the board.** If the only
thing separating them is that the other row is already full, the puzzle resolves by
arithmetic instead of by insight, and a player who reads it the other way is right and is
told they are wrong. A word must have exactly one home under a precise reading of the
labels.
- Prefer categories a player can *name*. If someone groups the four correctly but cannot \
say why, the puzzle is unfair even though it is solvable.
- Vary the kind of category: things-that-are-X, ___ WORD and WORD ___ compounds, \
homophones, members of a set, words hiding another word. Do not use five of the same kind.
- A category that quietly narrows is the best device you have: "stone fruit" read as
"fruit", "circus performers" read as "circus things", "birds that cannot fly" read as
"birds". Reach for one of those before you reach for a collision.
- Vary difficulty deliberately. One category should be gettable at a glance, one should be \
the last thing anyone sees.
- No proper nouns that need specific regional or generational knowledge.
"""


def _puzzle_as_example(p: Puzzle) -> str:
    rows = "\n".join(f"  {g.label}: {', '.join(g.words)}" for g in p.groups)
    return f"{p.name}\n{rows}"


def propose(
    *, slot: Slot, examples: list[Puzzle], avoid_words: list[str], avoid_labels: list[str]
) -> tuple[str, str]:
    shown = "\n\n".join(_puzzle_as_example(p) for p in examples)
    words = ", ".join(sorted(avoid_words)[:200]) or "(nothing yet)"
    labels = "; ".join(sorted(avoid_labels)[:80]) or "(nothing yet)"
    system = (
        "You are a puzzle constructor. You write one board at a time and you care more "
        "about whether it has exactly one answer than about whether it is clever.\n\n"
        + GAME_BRIEF
        + "\n"
        + CONSTRUCTION_RULES
    )
    prompt = f"""\
Hand-written boards that set the standard:

{shown}

Write one new board.

Two of your five categories are assigned. Build the other three yourself, and choose them
so their words collide with these two.

  Assigned device: {slot.device}
  Assigned theme: {slot.theme or "(none — the pool was empty, so choose all five)"}

Already shipped, so do not reuse — words: {words}
Already shipped, so do not repeat the idea — categories: {labels}

For each category, state its trap: which word on this board its *obvious* reading would \
pull in, and what in its precise reading keeps that word out. "Stone fruit — reads as \
fruit, so it pulls APPLE, but an apple is a pome not a drupe." If a category has no such \
pull, say so; a board where three categories say "none" is one you should rewrite before \
answering. And check, before you answer, that no word genuinely satisfies two of your \
five labels — that is the one defect that makes the board unsolvable rather than hard.
"""
    return system, prompt


def solve(words: list[str]) -> tuple[str, str]:
    """Deliberately bare. See the module docstring."""
    system = (
        "You group words. Given 20 words, split them into 5 groups of 4 that each share "
        "something. Use every word exactly once. Name each group. Answer even if you are "
        "unsure — a guess is more useful than a refusal."
    )
    prompt = "\n".join(words)
    return system, prompt


def red_team(puzzle: Puzzle, traps: dict[str, str]) -> tuple[str, str]:
    """The critical stage, and not the same job as solving.

    A solver that happens to find the intended answer proves nothing about whether a
    second answer exists — so this model is shown the key and paid to break it.

    This ask has been rewritten twice. First it reported every decoy, which made it a
    mirror of the proposer's own trap list. Then it was asked whether a decoy survived
    the full-partition rule, which is a question about seat-counting. Both were wrong in
    the same way: they treated a word belonging to two categories as difficulty to be
    measured, when the construction rules now say it is a defect to be found. The
    misdirection is supposed to live in a category that reads wider than it is, and a
    word that genuinely satisfies two labels is simply a broken board.

    So the question is now flat: does any word satisfy two of these five labels under a
    precise reading? No completion proof, no partition arithmetic.
    """
    system = (
        "You are a hostile solver. You are given a word puzzle *and its intended answer*. "
        "Your only job is to find a way for a reasonable player to be correct and be told "
        "they are wrong.\n\n"
        + GAME_BRIEF
        + "\nThis board is built so that some categories read wider than they are: a "
        "category like 'stone fruit' looks like 'fruit' and tempts APPLE, but an apple is "
        "not a drupe, so the temptation resolves the moment you read the label precisely. "
        "That is the intended difficulty and it is not a fault.\n"
        "A fault is a word that genuinely satisfies two of the five labels under a precise "
        "reading — where a player could file it either way and defend it. Judge the labels "
        "as written, on their own terms, and ignore how many words each row already has: "
        "'the other row is full' is not a resolution, it is the bug."
    )
    rows = "\n".join(
        f"{g.label}: {', '.join(g.words)}   [intended pull: {traps.get(g.id, 'none stated')}]"
        for g in puzzle.groups
    )
    prompt = f"""\
Board (all 20 words): {", ".join(puzzle.words)}

Intended answer:
{rows}

Three questions, in this order:
1. Does any word genuinely satisfy two of these five labels? For each, name both labels \
and say why the second reading is defensible. Do not report a word that a precise reading \
of the label excludes — that is the puzzle working.
2. Is there a *different* way to cut these 20 words into 5 groups of 4 where every group \
holds together? If yes, give it in full. This is fatal, so look hard.
3. Is any label written so loosely that it invites a word it does not mean? Say which \
tightening would fix it.
"""
    return system, prompt


def grade(
    *,
    puzzle: Puzzle,
    traps: dict[str, str],
    solver_digest: str,
    red: RedTeamReport | None,
    warnings: list[str],
) -> tuple[str, str]:
    system = (
        "You are the editor. You decide whether a puzzle ships as it stands, goes to a "
        "human, or is killed, using evidence gathered by other models. Nothing rewrites "
        "the board after you — there is no revision step, so do not ask for one.\n\n"
        + GAME_BRIEF
        + "\n"
        + CONSTRUCTION_RULES
        + "\nHow to read the red-team report: this board is *meant* to contain categories "
        "that read wider than they are, so a word being tempted by another row is the "
        "puzzle working. What the red team reports is different — a word two labels both "
        "genuinely admit — and that is a defect, not difficulty.\n"
        "How to read the solver evidence: the solvers are deliberately weak models. "
        "A low recovery rate means hard OR broken, and it is your job to say which — the "
        "red-team report is the tiebreaker. A category the solvers found but could not "
        "name is the specific shape of unfair that nothing else in this pipeline catches.\n"
        "Use 'review' when the board is sound but something specific is wrong — name it "
        "in your reasons, precisely enough that a human can check the claim in seconds. "
        "Use 'reject' when the board is not worth a human's time."
    )
    rows = "\n".join(
        f"{g.label}: {', '.join(g.words)}   [intended trap: {traps.get(g.id, 'none stated')}]"
        for g in puzzle.groups
    )
    flags = "\n".join(f"- {w}" for w in warnings) or "- none"
    prompt = f"""\
Puzzle: {puzzle.name}
{rows}

Automatic checks flagged:
{flags}

Weak-solver ensemble:
{solver_digest}

Red team ({red.verdict if red else "did not run"}):
{_red_summary(red)}

Decide.
"""
    return system, prompt


def _red_summary(red: RedTeamReport | None) -> str:
    """A stage that fell over must read as absent, never as a clean bill of health."""
    if red is None:
        return "- the red team did not run; treat this board as unchecked for a second answer"
    lines = [
        f"- {a.word}: filed under {a.intended_label!r}, but {a.also_fits!r} admits it too — {a.why}"
        for a in red.ambiguous_words
    ]
    lines += [
        f"- label {loose.label!r} is wider than its row: it invites {loose.invites}. "
        f"Tighter: {loose.tighten_to}"
        for loose in red.loose_labels
    ]
    for alt in red.alternatives:
        groups = "; ".join(f"{g.category}: {', '.join(g.words)}" for g in alt.groups)
        lines.append(f"- ALTERNATIVE PARTITION — {alt.why}\n  {groups}")
    return "\n".join(lines) or "- nothing found"


def invent(*, count: int, known: list[str]) -> tuple[str, str]:
    """Stage 0. Cheap, bulk, and run before any board exists.

    Asking for forty categories in one call is fine where asking for ten boards is not: a
    board is a design with five interacting parts and degrades when batched, a category is
    a one-line idea.
    """
    system = (
        "You invent categories for a word puzzle. Not boards — just categories, one line "
        "each, to be drawn on later.\n\n" + GAME_BRIEF + "\n"
        "The best category reads wider than it is. 'Stone fruit' looks like 'fruit' and "
        "tempts APPLE, but an apple is a pome, so the temptation resolves the moment the "
        "label is read precisely. 'Circus performers' looks like 'circus things' and "
        "excludes TRAPEZE. That narrowing is what you are being asked for.\n"
        "Avoid categories that need regional or generational knowledge, and avoid ones "
        "whose members are longer than 12 characters."
    )
    have = ", ".join(sorted(known)[:300]) or "(the pool is empty)"
    prompt = f"""\
Invent {count} categories.

For each, give the label as a player would read it, and the wider reading it will be
mistaken for along with the word that mistake pulls in.

Already in the pool, so do not repeat the idea: {have}
"""
    return system, prompt
