"""The authoring prompts, written in Swedish rather than about Swedish.

This is one arm of an experiment, not a second copy of the prompt library. Only the two
*generative* stages are here — invent and propose — because those are where a board is
authored. Solve, red-team and grade stay in English in every arm on purpose: they are the
measuring instruments, and an instrument that changes between arms measures nothing.

Two rules were followed in translating, and both matter for reading the result:

- **Faithfulness over improvement.** Every clause of the English original has a
  counterpart here, in the same order, saying the same thing. Where the Swedish is
  clumsier than the English it was left clumsy. A prompt that is *better* as well as
  Swedish would answer a question nobody asked.
- **The worked example stays an English board.** APPLE / PEACH / PLUM / MANGO / OLIVE is
  described in Swedish but not translated, and is marked as an English board. Translating
  it would hand the Swedish arm a Swedish worked example the English arm never had — and
  worse, it would hand it *stenfrukt*, which is precisely the calque the last run
  produced from this very example. Holding it identical is what isolates the variable.
"""

from __future__ import annotations

from .categories import Slot
from .language import Language
from .spec import CHECKS, COLS, MAX_WORD_LEN, ROWS, Puzzle

GAME_BRIEF = f"""\
Connectris är ett ordgrupperingspussel. Brädet är {ROWS * COLS} ord i {ROWS} rader om \
{COLS}. Varje rad är en kategori. Spelaren flyttar om hela brädet och låser en komplett \
uppställning, och bara den obrutna följden av rätta rader uppifrån räknas av — så \
spelaren måste dessutom rangordna sina rader efter hur säker man känner sig. Man har \
{CHECKS} rättningar.

Det betyder att ett pussel bedöms på två saker samtidigt:
- Varje kategori måste ha exakt en försvarbar uppsättning medlemmar, annars får en \
spelare som har rätt beskedet att det är fel.
- Kategorierna måste skilja sig åt i hur uppenbara de är. Ett bräde med fem lika lätta \
kategorier ger spelaren ingenting att rangordna, och rangordningen är själva spelet.
"""

CONSTRUCTION_RULES = f"""\
Hårda krav — ett pussel som bryter mot något av dem slängs oläst:
- Exakt {ROWS} kategorier om exakt {COLS} ord. {ROWS * COLS} olika ord, inga upprepningar.
- Varje ord högst {MAX_WORD_LEN} tecken. Brädet är fyra kolumner på en telefon. Kortare är \
bättre; de flesta orden bör vara under 8.
- Enbart versaler. Inga skiljetecken, inga siffror. Två ord går bra om uppslagsordet
verkligen är två ord och det får plats på brickan.
- Inget ord får stå skrivet i en annan kategoris etikett.

Vad som gör ett bra pussel — och det är den här skillnaden allt hänger på:

- **Vilseledningen ligger i kategorin, inte i ordet.** Skriv en kategori vars uppenbara
läsning är vidare än dess verkliga, så att ett ord ser ut att höra hemma ända tills man
läser kategorin noga och ser att det inte gör det. Ta ett engelskt bräde med APPLE, PEACH,
PLUM, MANGO och OLIVE: raden är inte "fruit", den är "stone fruit" — PEACH, PLUM, MANGO
och OLIVE har alla en kärna, APPLE har det inte, och därmed frigörs APPLE till raden med
teknikföretag. Spelaren räknar inte platser; spelaren upptäcker att kategorin var smalare
än den såg ut.
- **Skriv aldrig ett ord som på riktigt hör hemma i två av brädets kategorier.** Om det
enda som skiljer dem åt är att den andra raden redan är full, löser sig pusslet med
huvudräkning i stället för med insikt, och en spelare som läser det åt andra hållet har
rätt men får fel. Ett ord ska ha exakt ett hem när etiketterna läses noga.
- Föredra kategorier som spelaren kan *sätta namn på*. Om någon grupperar de fyra rätt men \
inte kan säga varför är pusslet orättvist, även om det gick att lösa.
- Variera sorten av kategori: {{kinds}}. Använd inte fem av samma sort.
- En kategori som tyst smalnar av är det bästa greppet du har: "stone fruit" läst som
"fruit", "cirkusartister" läst som "cirkussaker", "fåglar som inte kan flyga" läst som
"fåglar". Sträck dig efter en sådan innan du sträcker dig efter en krock.
- Variera svårighetsgraden medvetet. En kategori ska gå att se direkt, en ska vara det \
sista någon får syn på.
- Inga egennamn som kräver särskild regional kunskap eller kunskap om en viss generation.
"""

#: The Swedish-specific addendum, in Swedish. A translation of `language.SV_RULES`,
#: clause for clause.
SV_RULES = """\
Och specifikt för att det du skriver är svenska:
- Svensk stavning, med Å, Ä och Ö där ordet har dem. Skriv aldrig A för Å eller O för Ö — \
RÅTTA och RATTA är olika ord, och brädet är fel om du blandar ihop dem.
- Tolvteckensgränsen är den bindande begränsningen på svenska, inte en formalitet. Svenska \
sammansättningar skrivs ihop och blir långa: SOMMARSTUGA är 11, KAFFEBRYGGARE är 14 och \
får inte plats. Föredra osammansatta ord och korta sammansättningar. Om en kategoris \
naturliga medlemmar alla är långa sammansättningar är den kategorin fel för det här brädet \
— välj en annan i stället för att förkorta, och hitta aldrig på en stympad form som ingen \
skriver.
- Bestämd och obestämd form är olika ord på en bricka. Välj en form per rad och håll den: \
en rad som lyder HUND, KATTEN, HÄST, RÄVEN ser ut som ett misstag och läses som ett.
- Blanda inte en-ord och ett-ord eller singular och plural inom en rad heller, av samma \
skäl.
- Idiom måste vara idiom, inte översatt engelska. "Sparka hinken" är inte ett svenskt \
uttryck. Om en kategori bara fungerar därför att den är en översättningslån från en \
engelsk kategori är den ingen svensk kategori, och då ska du slänga den.
- Undvik ord som bara är gångbara i Sverige men inte i Finland, eller tvärtom, och undvik \
slang som daterar ett bräde till ett visst årtionde.
"""


def rules_for(lang: Language) -> str:
    return CONSTRUCTION_RULES.format(kinds=lang.kinds) + SV_RULES


def _puzzle_as_example(p: Puzzle) -> str:
    rows = "\n".join(f"  {g.label}: {', '.join(g.words)}" for g in p.groups)
    return f"{p.name}\n{rows}"


def propose(
    *,
    slot: Slot,
    examples: list[Puzzle],
    avoid_words: list[str],
    avoid_labels: list[str],
    avoid_concepts: list[str] | None = None,
    lang: Language,
) -> tuple[str, str]:
    shown = "\n\n".join(_puzzle_as_example(p) for p in examples) or "(inget har publicerats än)"
    words = ", ".join(sorted(avoid_words)[:200]) or "(ingenting än)"
    labels = "; ".join(sorted(avoid_labels)[:80]) or "(ingenting än)"
    concepts = "; ".join(sorted(avoid_concepts or [])[:80]) or "(ingenting än)"
    system = (
        "Du konstruerar pussel. Du skriver ett bräde i taget, och du bryr dig mer om "
        "huruvida det har exakt ett svar än om huruvida det är fyndigt.\n\n"
        + GAME_BRIEF
        + "\nBrädet du skriver är på svenska. Varje ord på det och varje kategorietikett "
        "är svensk. Den här instruktionen är på svenska och ditt svar ska också vara det.\n"
        + "\n"
        + rules_for(lang)
    )
    every_example_is_swedish = all(p.language == "sv" for p in examples) and bool(examples)
    standard = (
        "Handskrivna bräden som sätter ribban"
        if every_example_is_swedish
        else "Handskrivna bräden som sätter ribban. De är på engelska eftersom inget "
        "svenskt bräde har publicerats än — härma deras konstruktion, inte deras ordförråd, "
        "och översätt dem inte"
    )
    prompt = f"""\
{standard}:

{shown}

Skriv ett nytt bräde, på svenska.

Två av dina fem kategorier är redan bestämda. Bygg de tre andra själv, och välj dem så att
deras ord krockar med de två givna.

  Tilldelat grepp: {slot.device}
  Tilldelat ämne: {slot.theme or "(inget — poolen var tom, så välj alla fem själv)"}

Redan publicerat, så återanvänd inte — ord: {words}
Redan publicerat, så upprepa inte idén — kategorier: {labels}
Redan publicerat på något språk, så upprepa inte idén på ditt — koncept: {concepts}

Ge varje kategori ett `concept`: samma idé som en kort engelsk nominalfras, oavsett vilket \
språk etiketten är skriven på. Det är en identifierare, inte en översättning för spelaren \
att läsa. Om det koncept du står i begrepp att skriva redan står i listan ovan är \
kategorin en upprepning fastän etiketten är ny, och då ska du byta ut den.

Ange för varje kategori dess fälla: vilket ord på det här brädet som dess *uppenbara* \
läsning skulle dra till sig, och vad i den noggranna läsningen som håller det ordet ute. \
"Stenfrukt — läses som frukt, så den drar till sig APPLE, men ett äpple har kärnhus och \
ingen kärna." Om en kategori inte har något sådant drag, säg det; ett bräde där tre \
kategorier svarar "inget" är ett bräde du bör skriva om innan du svarar. Och kontrollera, \
innan du svarar, att inget ord på riktigt uppfyller två av dina fem etiketter — det är den \
enda defekten som gör ett bräde olösligt i stället för svårt.

Skriv orden och etiketterna på svenska.
"""
    return system, prompt


def invent(*, count: int, known: list[str], lang: Language) -> tuple[str, str]:
    system = (
        "Du hittar på kategorier till ett ordpussel. Inte hela bräden — bara kategorier, "
        "en rad var, att bygga vidare på senare.\n\n" + GAME_BRIEF + "\n"
        "Den bästa kategorin läses vidare än den är. Engelskans 'stone fruit' ser ut som "
        "'fruit' och lockar in APPLE, men ett äpple har kärnhus, så frestelsen löser upp "
        "sig i samma stund som etiketten läses noga. 'Cirkusartister' ser ut som "
        "'cirkussaker' och utesluter TRAPETS. Det är den avsmalningen du ombeds leverera.\n"
        "Undvik kategorier som kräver regional kunskap eller kunskap om en viss "
        "generation, och undvik sådana vars medlemmar är längre än 12 tecken.\n"
        "Skriv etiketterna på svenska, för ett bräde som kommer att spelas på svenska. "
        "Tolvteckensgränsen är den hårda gränsen här: svenska sammansättningar blir långa, "
        "så en kategori vars naturliga medlemmar alla är långa sammansättningar är "
        "oanvändbar hur god idén än är. Hitta på svenska kategorier i stället för att "
        "översätta engelska — en kategori som bara är intressant på engelska är sämre än "
        "värdelös, eftersom den kommer att läsas som en översättning."
    )
    have = ", ".join(sorted(known)[:300]) or "(poolen är tom)"
    prompt = f"""\
Hitta på {count} kategorier, på svenska.

Ge för var och en etiketten så som en spelare skulle läsa den, och den vidare läsning den
kommer att misstas för tillsammans med det ord den misstaget drar in.

Ge dessutom varje kategori ett `concept`: samma idé som en kort engelsk nominalfras. Det
är en identifierare som gör det möjligt att se att en kategori redan finns på ett annat
språk, inte en översättning för spelaren.

Redan i poolen, så upprepa inte idén: {have}
"""
    return system, prompt
