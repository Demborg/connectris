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


class ProposedGroup(BaseModel):
    label: str = Field(
        description="The category, as the player sees it once the row clears. Short. "
        "Use '___ WORD' or 'WORD ___' for word-joining categories."
    )
    words: list[str] = Field(
        description="Exactly 4 words, uppercase, at most 12 characters each, no spaces "
        "unless the entry genuinely has one."
    )
    trap: str = Field(
        description="Which word in this group is the decoy, and which other category on "
        "this board it is baiting. Say 'none' only if this group has no decoy at all."
    )


class ProposedPuzzle(BaseModel):
    name: str = Field(description="A two or three word title for the puzzle.")
    groups: list[ProposedGroup] = Field(description="Exactly 5 groups of 4 words.")
    hardest_group: str = Field(
        description="The label of the group you expect to be found last, and one line on why."
    )


class SolvedGroup(BaseModel):
    category: str = Field(description="What you think these four words have in common.")
    words: list[str] = Field(description="Exactly 4 of the words from the board, copied exactly.")


class SolveAttempt(BaseModel):
    groups: list[SolvedGroup] = Field(
        description="Exactly 5 groups of 4, using all 20 words, each word exactly once."
    )


class AmbiguousWord(BaseModel):
    """A word whose second reading survives the full-partition rule.

    Not merely a word that looks like it belongs elsewhere — every category is built to
    contain one of those. This is one the finished board fails to resolve.
    """

    word: str = Field(description="The word whose second placement the whole board allows.")
    intended_label: str = Field(description="The category it is filed under in the answer key.")
    also_fits: str = Field(description="The other category on this board it fits just as well.")
    completion: str = Field(
        description="The four words the row it left would have instead, proving the rest of "
        "the board still completes. Without this the finding is just a decoy doing its job."
    )
    why: str = Field(description="One sentence for why the second reading is legitimate.")


class AlternativePartition(BaseModel):
    """A second consistent way to cut the board into five fours.

    Finding one of these is fatal to a puzzle: the player is right and the game says no.
    """

    groups: list[SolvedGroup] = Field(description="A full alternative solution: 5 groups of 4.")
    why: str = Field(description="Why this partition holds together as well as the intended one.")


class RedTeamReport(BaseModel):
    ambiguous_words: list[AmbiguousWord] = Field(
        description="Words that legitimately fit two categories on this board. Empty if none."
    )
    alternatives: list[AlternativePartition] = Field(
        description="Full alternative solutions you found. Empty if none. Do not force one."
    )
    verdict: Literal["clean", "soft", "broken"] = Field(
        description="'clean' = one solution only. 'soft' = a defensible second reading of one "
        "word. 'broken' = a whole alternative partition holds."
    )


class Grade(BaseModel):
    verdict: Literal["accept", "revise", "reject"] = Field(
        description="'accept' ships it. 'reject' kills it. 'revise' means the board is "
        "sound but one word is doing damage — say which in `reasons`; a human will look."
    )
    fairness: int = Field(
        description="1-5. Can a careful player get here from the words alone, with no "
        "outside knowledge they could not reasonably have?"
    )
    elegance: int = Field(description="1-5. Does the click of getting it feel earned?")
    reasons: str = Field(description="Two or three sentences. What is wrong, or what is good.")
