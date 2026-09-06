"""What changes when the board is not in English.

A language is not a flag on the prompt. Three things vary together and there is no useful
way to vary one without the others:

- the **alphabet**, which is a validation question (`spec.ALPHABETS`);
- the **devices**, which is the interesting one. `___ WORD` is an English device. Swedish
  writes its compounds closed — SOL + SKEN is SOLSKEN, one word, no gap to point at — so
  the same idea has to be posed as "four stems that take the same second element", and the
  tile then shows a bound morpheme rather than a word. That is a different puzzle with
  different failure modes, not a translation;
- the **register**, meaning what counts as a fair category. "No knowledge that needs a
  particular region" means something else when the language itself picks the region.

So a `Language` is a small record and the prompts take one, rather than taking a code and
branching. Adding Norwegian is adding an entry here.

The prompts stay in English on purpose, with the output language stated explicitly. That
is one variable rather than two: if the Swedish boards come out weak, an English prompt
asking for Swedish output has one obvious next thing to try, whereas a Swedish prompt that
produced weak boards leaves "was it the prompt or the language" unanswerable. Whether
prompting in Swedish is better is an open question and it is cheap to test later.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Structural kinds, English. A board gets one, and the pool avoids repeating one too soon,
#: so a week of boards differs in shape rather than only in subject.
EN_DEVICES: list[str] = [
    "a ___ WORD compound, where all four words take the same following word",
    "a WORD ___ compound, where all four words take the same preceding word",
    "four words that each contain a smaller hidden word of the same kind",
    "four words that are homophones of something else entirely",
    "four members of an ordered set (ranks, sizes, stages)",
    "four words that all mean roughly the same thing",
    "four words that are all a specific kind of noun with an everyday second meaning",
]

#: Swedish. Four of the seven English devices survive translation unchanged (hidden words,
#: ordered sets, synonyms, second meanings) and are kept. The two compound devices are
#: rewritten around closed compounds, and are the ones most likely to break the tile:
#: SOLSKEN is one word but the *tile* only shows SOL, and whether a player reads a bare
#: förled as an invitation to compound is exactly what a playtest has to answer.
#: Two devices are added that only exist here: the å/ä/ö minimal pair, which is free
#: wordplay in a language with three extra vowels, and the fixed expression, which is where
#: Swedish idiom actually lives.
SV_DEVICES: list[str] = [
    "fyra förled — four stems that each form a real, everyday closed compound with the "
    "same second element (SOL, MÅN, STJÄRN + LJUS). Put only the stem on the tile. Every "
    "one of the four compounds must be a word people actually say",
    "fyra efterled — four second elements that each form a real closed compound with the "
    "same stem. Put only the second element on the tile",
    "four words that each contain a smaller hidden word of the same kind",
    "four words that differ from a common word only in Å, Ä or Ö — a minimal pair on the "
    "vowel (RÅTTA/RATTA, HÖNA/HANA). The board word is the real one",
    "four members of an ordered set (ranks, sizes, stages)",
    "four words that all mean roughly the same thing",
    "four words that are each the load-bearing noun of a fixed Swedish expression",
    "four words that are all a specific kind of noun with an everyday second meaning",
]

#: Extra construction rules, appended to the shared ones. Empty for English, because the
#: shared rules were written for English and already say what they need to.
SV_RULES = """\
Writing in Swedish, specifically:
- Swedish spelling, including Å, Ä and Ö where the word has them. Never write A for Å or O \
for Ö — RÅTTA and RATTA are different words and the board is wrong if you confuse them.
- The 12-character cap is the binding constraint in Swedish, not a formality. Swedish \
compounds are written closed and run long: SOMMARSTUGA is 11, KAFFEBRYGGARE is 14 and does \
not fit. Prefer simplex words and short compounds. If a category's natural members are all \
long compounds, that category is wrong for this board — pick a different one rather than \
abbreviating, and never invent a clipped form nobody writes.
- Definite and indefinite are different words on a tile. Pick one form per row and keep it: \
a row reading HUND, KATTEN, HÄST, RÄVEN looks like a mistake and reads as one.
- No en/ett or singular/plural mixture inside a row either, for the same reason.
- Idiom must be idiom, not translated English. "Kick the bucket" is not a Swedish \
expression. If a category only works because it is a calque of an English one, it is not a \
Swedish category and you should throw it away.
- Avoid words that are only current in Sweden versus Finland, and avoid slang that dates a \
board to one decade.
"""


@dataclass(frozen=True)
class Language:
    """One target language: what to validate, what to build with, what to say."""

    code: str
    #: As written in a prompt. The model is told this by name, not by ISO code.
    name: str
    devices: list[str]
    #: A one-line menu of category kinds, for the "do not use five of the same kind" rule.
    #: Shorter and vaguer than `devices` on purpose: `devices` assigns one slot precisely,
    #: this only asks for variety in the other four.
    kinds: str = ""
    #: Appended to CONSTRUCTION_RULES. Empty when the shared rules already suffice.
    rules: str = ""

    @property
    def is_default(self) -> bool:
        return self.code == "en"


ENGLISH = Language(
    code="en",
    name="English",
    devices=EN_DEVICES,
    kinds="things-that-are-X, ___ WORD and WORD ___ compounds, homophones, members of a "
    "set, words hiding another word",
)
SWEDISH = Language(
    code="sv",
    name="Swedish",
    devices=SV_DEVICES,
    kinds="things-that-are-X, förled or efterled of a shared closed compound, minimal "
    "pairs on Å/Ä/Ö, nouns from fixed expressions, members of a set, words hiding another "
    "word",
    rules=SV_RULES,
)

LANGUAGES: dict[str, Language] = {lang.code: lang for lang in (ENGLISH, SWEDISH)}


def get(code: str) -> Language:
    if code not in LANGUAGES:
        raise ValueError(f"unknown language {code!r}; have {', '.join(sorted(LANGUAGES))}")
    return LANGUAGES[code]


__all__ = ["ENGLISH", "LANGUAGES", "SWEDISH", "Language", "get"]
