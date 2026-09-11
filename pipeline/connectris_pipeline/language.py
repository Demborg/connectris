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

from dataclasses import dataclass, replace

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
    "four entries that each end in a shorter word of the same kind, hidden at different "
    "depths — one as the whole second word of a two-word entry, one buried across a "
    "syllable boundary inside a single word (REPRESENT hides PRESENT, SEXTANT hides "
    "EXTANT). Do not disguise all four the same way",
    "four things joined by a situation rather than a category — what you would see in one "
    "place, or what someone would be holding at one moment. Not a kind of thing",
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
    "four words that each hide a shorter word of the same kind, but at different depths — "
    "one as the whole efterled of a closed compound, one buried inside a simplex word. Do "
    "not hide them the same way all four times",
    "four things joined by a situation rather than a category — what you would see in one "
    "place, or what someone would be holding at one moment. Not a kind of thing",
]

#: The same eight devices, written in Swedish. Only used by the `sv-native` arm, where the
#: whole authoring prompt is Swedish and an English device string would be a leak in it.
#: Translated clause for clause from `SV_DEVICES`, deliberately not improved.
SV_DEVICES_NATIVE: list[str] = [
    "fyra förled — fyra stammar som var och en bildar en verklig, vardaglig "
    "sammansättning med samma efterled (SOL, MÅN, STJÄRN + LJUS). Sätt bara förledet på "
    "brickan. Alla fyra sammansättningarna måste vara ord folk faktiskt säger",
    "fyra efterled — fyra efterled som var och ett bildar en verklig sammansättning med "
    "samma förled. Sätt bara efterledet på brickan",
    "fyra ord som var och ett gömmer ett kortare ord av samma slag",
    "fyra ord som skiljer sig från ett vanligt ord enbart på Å, Ä eller Ö — ett minimalt "
    "par på vokalen (RÅTTA/RATTA, HÖNA/HONA). Ordet på brädet är det riktiga",
    "fyra medlemmar av en ordnad följd (grader, storlekar, stadier)",
    "fyra ord som alla betyder ungefär samma sak",
    "fyra ord som vart och ett är det bärande substantivet i ett fast svenskt uttryck",
    "fyra ord som alla är ett bestämt slags substantiv med en vardaglig andrabetydelse",
    "fyra ord som var och ett gömmer ett kortare ord av samma slag, men på olika djup — "
    "ett som hela efterledet i en sammansättning, ett begravt inuti ett osammansatt ord. "
    "Göm dem inte på samma sätt alla fyra",
    "fyra saker som hålls ihop av en situation snarare än av en kategori — vad man ser på "
    "ett visst ställe, eller vad någon håller i vid ett visst tillfälle. Inte ett slags sak",
]

SV_KINDS_NATIVE = (
    "sådant-som-är-X, förled eller efterled i en gemensam sammansättning, minimala par på "
    "Å/Ä/Ö, substantiv ur fasta uttryck, medlemmar av en följd, ord som gömmer ett annat "
    "ord, situationer snarare än slags saker, egenskaper, vad någon gör"
)

#: Extra construction rules, appended to the shared ones. Empty for English, because the
#: shared rules were written for English and already say what they need to.
SV_RULES = """\
Writing in Swedish, specifically:
- Swedish spelling, including Å, Ä and Ö where the word has them. Never write A for Å or O \
for Ö — RÅTTA and RATTA are different words and the board is wrong if you confuse them.
- The 12-character cap on a single word is the binding constraint in Swedish, not a \
formality. Swedish compounds are written closed and run long: SOMMARSTUGA is 11, \
KAFFEBRYGGARE is 14 and does not fit. The 20-character allowance for a whole entry buys \
Swedish much less than it buys English, because a tile only wraps at a space and Swedish \
puts no space in a compound — so KAFFEBRYGGARE is still too long however generous the \
entry cap is. Prefer simplex words and short compounds. If a category's natural members \
are all long compounds, that category is wrong for this board — pick a different one \
rather than abbreviating, and never invent a clipped form nobody writes.
- Where Swedish *does* get two words, take them: particle verbs, fixed expressions and \
open noun phrases (GÅ BÄRSÄRK, RÖD TRÅD) are genuinely two words and fit the tile.
- The set that matches no label is harder to build in Swedish, because initialisms are \
less idiomatic here than in English — AC does not read as anything. Build it from what \
Swedish does have instead: a shared förled that several unrelated words all take, a string \
of letters hiding in words from four different rows, or one cultural domain (jul, \
midsommar, allemansrätten) that several words evoke without any row being about it.
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
    #: Whether the *authoring* prompts (invent, propose) are written in this language
    #: rather than in English about it. Solve, red-team and grade stay English either way:
    #: they are the measurement, and an instrument that moves between arms measures
    #: nothing. See `prompts_sv`.
    prompt_native: bool = False

    @property
    def is_default(self) -> bool:
        return self.code == "en"


ENGLISH = Language(
    code="en",
    name="English",
    devices=EN_DEVICES,
    kinds="things-that-are-X, ___ WORD and WORD ___ compounds, homophones, members of a "
    "set, words hiding another word, situations rather than kinds, properties, what "
    "someone does, where a word came from",
)
SWEDISH = Language(
    code="sv",
    name="Swedish",
    devices=SV_DEVICES,
    kinds="things-that-are-X, förled or efterled of a shared closed compound, minimal "
    "pairs on Å/Ä/Ö, nouns from fixed expressions, members of a set, words hiding another "
    "word, situations rather than kinds, properties, what someone does",
    rules=SV_RULES,
)

#: Same board language, same alphabet, same validation — the prompts differ and nothing
#: else. Registered under its own key so `--language` can select it, while `code` stays
#: "sv" so every board it writes is stamped, validated and deduped as ordinary Swedish.
SWEDISH_NATIVE = replace(
    SWEDISH, devices=SV_DEVICES_NATIVE, kinds=SV_KINDS_NATIVE, prompt_native=True
)

LANGUAGES: dict[str, Language] = {
    "en": ENGLISH,
    "sv": SWEDISH,
    "sv-native": SWEDISH_NATIVE,
}


def get(code: str) -> Language:
    if code not in LANGUAGES:
        raise ValueError(f"unknown language {code!r}; have {', '.join(sorted(LANGUAGES))}")
    return LANGUAGES[code]


def of(puzzle_language: str) -> Language:
    """The language of a board already in hand, falling back rather than raising.

    `get` is for configuration, where an unknown code is a typo worth stopping for. This is
    for data: a board read back out of the database carries whatever tag it was written
    with, and a stage that runs at publish time must not die because a row says "no".
    """
    return LANGUAGES.get(puzzle_language, ENGLISH)


__all__ = ["ENGLISH", "LANGUAGES", "SWEDISH", "SWEDISH_NATIVE", "Language", "get", "of"]
