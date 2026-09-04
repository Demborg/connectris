"""Prompts, and the seed vocabulary that keeps a batch from converging.

Kept as code rather than template files because they are the thing under active tuning
and they are meaningless apart from the schemas in schema.py.

Note what the solver prompt does *not* contain: the game's name, the rules, the trap
design, or any hint that the words were constructed. The solver's job is to be an
ordinary confused player, and every extra sentence makes it a better one than the
players we are calibrating against.
"""

from __future__ import annotations

import random

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
- Plain uppercase English. No punctuation, no digits, no phrases.
- No word may appear inside another category's label.

What makes one good:
- Every category needs a decoy: a word that plainly belongs to a different category on \
this board until you find the row that needs it more. That collision is the puzzle.
- Prefer categories a player can *name*. If someone groups the four correctly but cannot \
say why, the puzzle is unfair even though it is solvable.
- Vary the kind of category: things-that-are-X, ___ WORD and WORD ___ compounds, \
homophones, members of a set, words hiding another word. Do not use five of the same kind.
- Vary difficulty deliberately. One category should be gettable at a glance, one should be \
the last thing anyone sees.
- No proper nouns that need specific regional or generational knowledge.
"""

#: Rotated through so a night's batch does not come back as five puzzles about cooking.
DOMAINS = [
    "kitchen and cooking",
    "geology and weather",
    "sailing and the sea",
    "music theory",
    "cards and gambling",
    "the body",
    "printing and typography",
    "gardening",
    "cinema and theatre",
    "birds and animals",
    "tools and hardware",
    "clothing",
    "money and finance",
    "mathematics",
    "chess and board games",
    "trains and roads",
    "medicine",
    "law and courtrooms",
    "cosmetics",
    "sleep and dreams",
    "insects",
    "textiles and sewing",
    "astronomy",
    "coffee and tea",
    "castles and armour",
    "photography",
    "plumbing",
    "the circus",
]

#: At least one category per puzzle must be built with the drawn device.
DEVICES = [
    "a ___ WORD compound, where all four words take the same following word",
    "a WORD ___ compound, where all four words take the same preceding word",
    "four words that each contain a smaller hidden word of the same kind",
    "four words that are homophones of something else entirely",
    "four members of an ordered set (ranks, sizes, stages)",
    "four words that all mean roughly the same thing",
    "four words that are all a specific kind of noun with an everyday second meaning",
]


def draw_seed(rng: random.Random) -> dict[str, str]:
    """A per-candidate seed. Diversity comes from the input, not from asking for variety."""
    domains = rng.sample(DOMAINS, 2)
    return {"domains": ", ".join(domains), "device": rng.choice(DEVICES)}


def _puzzle_as_example(p: Puzzle) -> str:
    rows = "\n".join(f"  {g.label}: {', '.join(g.words)}" for g in p.groups)
    return f"{p.name}\n{rows}"


def propose(
    *, seed: dict[str, str], examples: list[Puzzle], avoid_words: list[str], avoid_labels: list[str]
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

Draw at least two categories from: {seed["domains"]}.
Build at least one category as {seed["device"]}.

Already shipped, so do not reuse — words: {words}
Already shipped, so do not repeat the idea — categories: {labels}

For each category, state its trap: which of its words looks like it belongs to a \
different row on this board, and which row. If a category has no such word, say so — but \
a board where three categories say "none" is a board you should rewrite before answering.
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

    The ask is narrower than it looks, and the narrowing is the point. The first real run
    produced 37 ambiguous-word findings and *every one of them was a trap the proposer
    had declared in its own prompt* — handed the trap list, the model handed it back.
    That made the stage a mirror, and since the construction rules require every category
    to have a decoy, it taxed exactly the boards that followed the brief.

    A decoy is not a defect. What makes it one is surviving the full-partition rule: the
    player commits all twenty words at once, so a word that looks like it belongs
    elsewhere is resolved the moment the other row fills up without it. The only real
    ambiguity is one that still stands when the whole board is laid out — which is the
    same thing as a second complete partition.
    """
    system = (
        "You are a hostile solver. You are given a word puzzle *and its intended answer*. "
        "Your only job is to find a way for a reasonable player to be correct and be told "
        "they are wrong.\n\n"
        + GAME_BRIEF
        + "\nThis board is built so that every category contains a word that looks like it "
        "belongs to a different row. That is the intended difficulty, not a fault, and "
        "reporting it as one gets a good puzzle thrown away. The full-partition rule "
        "resolves an ordinary decoy by itself: the player places all twenty words at "
        "once, so a word that looks like it belongs elsewhere is settled as soon as the "
        "other row is full without it.\n"
        "Report a word only when that resolution *fails* — when moving it leaves both "
        "rows fillable with four words each, so the board still works with the word in "
        "the other place. That is a genuine second answer. Everything else is the puzzle "
        "doing its job."
    )
    rows = "\n".join(
        f"{g.label}: {', '.join(g.words)}   [intended trap: {traps.get(g.id, 'none stated')}]"
        for g in puzzle.groups
    )
    prompt = f"""\
Board (all 20 words): {", ".join(puzzle.words)}

Intended answer:
{rows}

The traps are listed so you can rule them out, not so you can repeat them. A trap that \
the full board resolves is a working trap.

Two questions, in this order:
1. Is there a *different* way to cut these 20 words into 5 groups of 4 where every group \
holds together? If yes, give it in full. This is fatal to the puzzle, so look hard.
2. Is there a word you could move to another row and still complete the whole board — \
every row four words, every row holding together? Name it, and say which four words the \
row it left would then have. If completing the board forces the word back, it is resolved \
and you should not report it.
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
        "You are the editor. You decide whether a puzzle ships, gets one revision, or is "
        "killed, using evidence gathered by other models.\n\n"
        + GAME_BRIEF
        + "\n"
        + CONSTRUCTION_RULES
        + "\nHow to read the solver evidence: the solvers are deliberately weak models. "
        "A low recovery rate means hard OR broken, and it is your job to say which — the "
        "red-team report is the tiebreaker. A category the solvers found but could not "
        "name is the specific shape of unfair that nothing else in this pipeline catches.\n"
        "Use 'revise' when the board is sound and one word is doing the damage — name "
        "that word in your reasons; a human decides what to do about it. Use 'reject' "
        "when fixing it would need two categories rewritten."
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
    lines = []
    for a in red.ambiguous_words:
        lines.append(
            f"- {a.word}: filed under {a.intended_label!r}, also fits {a.also_fits!r} — {a.why}"
        )
    for alt in red.alternatives:
        groups = "; ".join(f"{g.category}: {', '.join(g.words)}" for g in alt.groups)
        lines.append(f"- ALTERNATIVE PARTITION — {alt.why}\n  {groups}")
    return "\n".join(lines) or "- nothing found"
