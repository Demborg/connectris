"""Structured-output schemas.

Every model call in the pipeline returns one of these. The field descriptions are not
documentation — they are shipped to the model as part of the JSON schema and are the
cheapest prompt surface there is, so they carry real instruction.

Deliberately plain: no unions, no optionals, no dicts. Vertex's structured output is a
JSON-schema subset, and "empty list" survives that subset where "null" does not.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class InventedCategory(BaseModel):
    """A category for the pool, judged before any board is built from it."""

    label: str = Field(
        description="The category as a player would read it once the row clears. Short. "
        "Prefer one that narrows: 'Stone fruit' rather than 'Fruit'."
    )
    reads_as: str = Field(
        description="The wider category a player will mistake this for, and the word that "
        "mistake would pull in. 'Reads as fruit, so it pulls APPLE.' This is the trap, and "
        "it belongs to the category rather than to any word."
    )
    concept: str = Field(
        description="The same category as a short English noun phrase, ALWAYS in English "
        "however the label is written: 'stone fruit', 'orchestral brass instruments'. It "
        "is not a translation for the player to read — it is an identifier, used to notice "
        "that a category already exists in another language. Two labels that mean the same "
        "thing must get the same concept."
    )


class InventedCategories(BaseModel):
    categories: list[InventedCategory] = Field(description="Distinct from each other.")


class ProposedGroup(BaseModel):
    label: str = Field(
        description="The category, as the player sees it once the row clears. Short. "
        "For word-joining categories use the notation the board's own language writes: "
        "English writes its compounds open, so '___ WORD' or 'WORD ___'; a language that "
        "writes compounds closed takes no gap, so '___WORD' or 'WORD___'."
    )
    concept: str = Field(
        description="This category as a short English noun phrase, ALWAYS in English "
        "however the label is written: 'stone fruit', 'orchestral brass instruments'. An "
        "identifier rather than a translation, used to notice that the same category has "
        "already shipped in another language."
    )
    words: list[str] = Field(
        description="Exactly 4 entries, uppercase, at most 20 characters each including "
        "spaces, and no single word within an entry longer than 12 characters. Two-word "
        "entries are fine and are often what a good board needs."
    )


class Lure(BaseModel):
    """A set of words a player could defensibly group, and where those words really live.

    This replaced a per-category `trap` field that asked which *one* word a row baited and
    which *other row* it baited. That shape could only describe a decoy running between
    two rows, so that is the only kind of decoy the proposer ever built — the data model
    was generating the monoculture. Every trap this game has is really one shape: a
    tempting set, plus the true home of each member. A narrowing category is a lure of 5
    whose members sit 4-and-1; a phantom is a lure of 5 or more spread across 3 or 4 rows.
    The difference is data, so there is no `kind` field here and a new device needs no
    schema change.
    """

    name: str = Field(
        description="What a player would call this set on sight: 'fruit', 'AC', "
        "'things in space'. If you cannot name it in three words a player will not see "
        "it, and it is not doing any work."
    )
    words: list[str] = Field(
        description="Every entry on this board a player could defensibly put in this set. "
        "Must be 3 or fewer, or 5 or more. EXACTLY 4 is fatal: 4 words that cohere are a "
        "second correct answer to this board, and a player who submits them is right and "
        "will be told they are wrong. If your set has exactly 4, either find a fifth "
        "member on the board or change a word until it has 3."
    )
    where_each_lives: list[str] = Field(
        description="For each word above in the same order, the label of the row it is "
        "really filed under. When these are all the same label the lure is that row's own "
        "narrowing; when they span three or more rows it is a phantom, which is the "
        "stronger device."
    )


class ProposedPuzzle(BaseModel):
    name: str = Field(description="A two or three word title for the puzzle.")
    groups: list[ProposedGroup] = Field(description="Exactly 5 groups of 4 words.")
    lures: list[Lure] = Field(
        description="The false groupings this board is built to suggest. At least two, "
        "and at least one of them spanning three or more rows. A board with no lure is a "
        "board of five unrelated lists and is not worth playing."
    )


class SolvedGroup(BaseModel):
    category: str = Field(description="What you think these four words have in common.")
    words: list[str] = Field(description="Exactly 4 of the words from the board, copied exactly.")


class SolveAttempt(BaseModel):
    groups: list[SolvedGroup] = Field(
        description="Exactly 5 groups of 4, using all 20 words, each word exactly once."
    )


class AmbiguousWord(BaseModel):
    """A word that genuinely satisfies two of the board's five labels.

    Not a word that a category merely *tempts* — categories are built to read wider than
    they are, and that temptation is the puzzle. This is a word both labels actually
    admit, which makes the board unsolvable rather than hard.
    """

    word: str = Field(description="The word that two labels both genuinely admit.")
    intended_label: str = Field(description="The category it is filed under in the answer key.")
    also_fits: str = Field(description="The other label on this board that also admits it.")
    why: str = Field(
        description="Why the second reading is defensible on the label's own terms. Do not "
        "argue from how many words a row has left — that is not a resolution."
    )


class LooseLabel(BaseModel):
    """A label written wider than the row it names, which is how the defect above starts."""

    label: str = Field(description="The label as written.")
    invites: str = Field(description="The word it invites but does not mean.")
    tighten_to: str = Field(description="A precise rewording that excludes that word.")


class AlternativePartition(BaseModel):
    """A second consistent way to cut the board into five fours.

    Finding one of these is fatal to a puzzle: the player is right and the game says no.
    """

    groups: list[SolvedGroup] = Field(description="A full alternative solution: 5 groups of 4.")
    why: str = Field(description="Why this partition holds together as well as the intended one.")


class RedTeamReport(BaseModel):
    ambiguous_words: list[AmbiguousWord] = Field(
        description="Words two labels both genuinely admit. Empty if none — and empty is "
        "the expected answer for a well-built board."
    )
    loose_labels: list[LooseLabel] = Field(
        description="Labels written wider than the row they name. Empty if none."
    )
    alternatives: list[AlternativePartition] = Field(
        description="Full alternative solutions you found. Empty if none. Do not force one."
    )
    verdict: Literal["clean", "soft", "broken"] = Field(
        description="'clean' = one solution only. 'soft' = a defensible second reading of one "
        "word. 'broken' = a whole alternative partition holds."
    )


class GlossedWord(BaseModel):
    word: str = Field(description="The word, copied from the board exactly as given.")
    note: str = Field(
        description="One sentence. What this thing is, in the terms the category needs — "
        "the fact a player would have gone and looked up. Name the person, the place or "
        "the meaning: 'Charles Boycott, the Irish land agent whose tenants shunned him in "
        "1880.' Do not restate the category, and do not say 'this belongs because'."
    )


class GlossedCategory(BaseModel):
    label: str = Field(description="The category's label, copied exactly as given.")
    summary: str = Field(
        description="One sentence on what the category is, for a player who has just "
        "solved it and wants to know what it was. Say the thing that makes the four a "
        "set — 'Everyday words that began as the surname of a real person' — and where "
        "the label is a narrowing, say what it excludes. No praise, no second sentence."
    )
    words: list[GlossedWord] = Field(
        description="One entry per word in this category, in the order they were given."
    )


class PuzzleGloss(BaseModel):
    """The board explained, once it has been accepted. Never shown to a player mid-run."""

    categories: list[GlossedCategory] = Field(
        description="One per category on the board, in the order they were given."
    )


class Grade(BaseModel):
    verdict: Literal["accept", "review", "reject"] = Field(
        description="'accept' ships it as it stands. 'reject' kills it. 'review' means "
        "the board is sound but something specific is wrong with it — say what in "
        "`reasons`, and a human will decide what to do."
    )
    fairness: int = Field(
        description="1-5. Can a careful player get here from the words alone, with no "
        "outside knowledge they could not reasonably have?"
    )
    elegance: int = Field(description="1-5. Does the click of getting it feel earned?")
    reasons: str = Field(description="Two or three sentences. What is wrong, or what is good.")
