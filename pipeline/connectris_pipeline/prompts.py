"""Prompts, and the seed vocabulary that keeps a batch from converging.

Kept as code rather than template files because they are the thing under active tuning
and they are meaningless apart from the schemas in schema.py.

Note what the solver prompt does *not* contain: the game's name, the rules, the trap
design, or any hint that the words were constructed. The solver's job is to be an
ordinary confused player, and every extra sentence makes it a better one than the
players we are calibrating against.
"""

from __future__ import annotations

from . import prompts_sv
from .categories import Slot
from .language import ENGLISH, Language
from .schema import RedTeamReport
from .spec import CHECKS, COLS, MAX_ENTRY_LEN, MAX_TOKEN_LEN, ROWS, Puzzle

GAME_BRIEF = f"""\
Connectris is a word-grouping puzzle. The board is {ROWS * COLS} words in {ROWS} rows of \
{COLS}. Each row is one category. The player rearranges the whole board and commits to a \
full arrangement, and only the leading run of correct rows from the top clears — so the \
player must also rank their rows by confidence. They get {CHECKS} checks.

This means a puzzle is judged on two things at once:
- Each category must have exactly one defensible membership, or a player who is right is \
told they are wrong.
- The categories must differ in how obvious they are. A board of five equally-easy \
categories gives the player nothing to rank, and the ranking is the game.
"""

CONSTRUCTION_RULES = f"""\
Hard constraints — a puzzle breaking any of these is thrown away unread:
- Exactly {ROWS} categories of exactly {COLS} words. {ROWS * COLS} distinct words, no repeats.
- Every entry at most {MAX_ENTRY_LEN} characters including spaces, and no single word \
inside an entry longer than {MAX_TOKEN_LEN}. A tile wraps between words and never inside \
one, so AIR CONDITIONER fits on two lines and TRANSUBSTANTIATE does not fit at all.
- Plain uppercase. No punctuation, no digits. Two-word entries are fine and are often \
what a board needs — do not avoid them, but do not pad a one-word entry into two either.
- No word may appear inside another category's label.

What makes one good — and this is the distinction the whole thing turns on:

- **Misdirection is never a word that two categories both admit.** Write a category whose
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
- Vary the kind of category: {{kinds}}. Do not use five of the same kind.
- **There are two kinds of misdirection and a good board has both.** The first lives in a
category that reads wider than it is: "stone fruit" read as "fruit", "circus performers"
read as "circus things", "birds that cannot fly" read as "birds". It resolves the moment
the label is read precisely.
- **The second lives in no category at all, and it is the stronger one.** Build a set of
words a player can see and name that matches *none* of your five labels. On one real
board, ACTINIUM (its symbol is Ac), ATLANTIC CITY, AIR CONDITIONER, ADULT CONTEMPORARY and
ALTERNATING CURRENT are all "AC" — a pattern anyone spots in seconds, spread across four
different rows, worth precisely nothing. The player sees something real, and it does not
help. Put at least one of these on every board.
- **Give such a set {COLS + 1} members or more, never exactly {COLS}.** At {COLS + 1} the
player cannot build a row from it without arbitrarily dropping a member, every choice is
wrong, and seeing it buys them nothing — which is the whole point. At exactly {COLS} they
can submit it whole; that still works as a trap, but it hands them a clean-looking group
and one wrong answer instead of a dead end, so it is the weaker build. Count the members
before you answer.
- What genuinely breaks a board is narrower: {COLS} words that cohere *and* leave the
other sixteen still sorting into four sensible rows without them. Then there are two right
answers and the player who found the second one is told they are wrong. Check that before
you answer.
- Draw its members from the words a player is *most* sure of — the transparent element,
the obvious window fitting. Misdirection is worth most where confidence is highest.
- **Do not make all five categories a kind of thing.** "What you might see sticking out of
a window" is a situation, not a taxonomy, and no amount of asking "what sort of word is
this?" will crack it. A board of five taxonomies is solved by sorting words into subject
areas, which is filing, not puzzling. At most three of your five may be taxonomies; build
the rest from situations, properties, what someone does, how something is said, or where a
word came from.
- **Vary the surface within a wordplay row too.** If four entries hide a word, do not hide
it the same way four times — one as the whole second word of a two-word entry, one buried
across a syllable boundary inside a single word. REPRESENT hides PRESENT and SEXTANT hides
EXTANT at a different depth than ADULT CONTEMPORARY hides CONTEMPORARY. When every member
is disguised identically, finding one member hands over the other three.
- Vary difficulty deliberately. One category should be gettable at a glance, one should be \
the last thing anyone sees.
- No proper nouns that need specific regional or generational knowledge.
"""


def rules_for(lang: Language) -> str:
    """The shared construction rules, with the language's own menu and addendum."""
    return CONSTRUCTION_RULES.format(kinds=lang.kinds) + lang.rules


def output_language(lang: Language) -> str:
    """Stated once, at the top, and repeated at the ask. Empty for English.

    Repeating it is not belt-and-braces. The example boards below it are English — there
    are no shipped Swedish boards to few-shot from on day one — and a model shown five
    English boards and asked for a sixth will produce an English one unless told otherwise
    at the moment of asking. That the examples are in the wrong language at all is the
    single biggest confound in the first Swedish run; see the report.
    """
    if lang.is_default:
        return ""
    return (
        f"\nThe board you write is in {lang.name}. Every word on it and every category "
        f"label is {lang.name}. The instructions here are in English; your output is not.\n"
    )


def _puzzle_as_example(p: Puzzle) -> str:
    rows = "\n".join(f"  {g.label}: {', '.join(g.words)}" for g in p.groups)
    return f"{p.name}\n{rows}"


def _sample(items: list[str], cap: int) -> list[str]:
    """At most `cap` of them, spread across the alphabet rather than taken off the front.

    These lists were capped and then sorted, which is fine until the corpus passes the cap
    — at which point the proposer stops being told about anything after about the letter
    C, and dedupe degrades without saying so. A board a day reaches 200 words in under two
    months, so this is not a distant problem.

    Evenly spaced rather than random, because the prompt is otherwise deterministic and a
    reproducible seed should reproduce a run. The list is still sorted on the way out: a
    caller passes a set, and a prompt that differs only in the order of a word list is a
    prompt cache that never hits.
    """
    ordered = sorted(items)
    if len(ordered) <= cap:
        return ordered
    step = len(ordered) / cap
    return [ordered[int(i * step)] for i in range(cap)]


def propose(
    *,
    slot: Slot,
    examples: list[Puzzle],
    avoid_words: list[str],
    avoid_labels: list[str],
    avoid_concepts: list[str] | None = None,
    lang: Language = ENGLISH,
) -> tuple[str, str]:
    if lang.prompt_native:
        return prompts_sv.propose(
            slot=slot,
            examples=examples,
            avoid_words=avoid_words,
            avoid_labels=avoid_labels,
            avoid_concepts=avoid_concepts,
            lang=lang,
        )
    # The fallback is not decoration: a language with no shipped boards and no seeds hands
    # this an empty list, and an empty examples block reads as a truncated prompt.
    shown = "\n\n".join(_puzzle_as_example(p) for p in examples) or "(none shipped yet)"
    words = ", ".join(_sample(avoid_words, 200)) or "(nothing yet)"
    labels = "; ".join(_sample(avoid_labels, 80)) or "(nothing yet)"
    concepts = "; ".join(_sample(avoid_concepts or [], 80)) or "(nothing yet)"
    system = (
        "You are a puzzle constructor. You write one board at a time and you care more "
        "about whether it has exactly one answer than about whether it is clever.\n\n"
        + GAME_BRIEF
        + output_language(lang)
        + "\n"
        + rules_for(lang)
    )
    standard = (
        "Hand-written boards that set the standard"
        if lang.is_default
        else f"Hand-written boards that set the standard. They are in English because no "
        f"{lang.name} board has shipped yet — copy their construction, not their vocabulary, "
        f"and do not translate them"
    )
    prompt = f"""\
{standard}:

{shown}

Write one new board{"" if lang.is_default else f", in {lang.name}"}.

Two of your five categories are assigned. Build the other three yourself, and choose them
so their words collide with these two.

  Assigned device: {slot.device}
  Assigned theme: {slot.theme or "(none — the pool was empty, so choose all five)"}

Already shipped, so do not reuse — words: {words}
Already shipped, so do not repeat the idea — categories: {labels}
Already shipped in some language, so do not repeat the idea in yours — concepts: {concepts}

Give every category a `concept`: the same idea as a short English noun phrase, whatever \
language the label is written in. It is an identifier, not a translation for the player. \
If the concept you are about to write is on the list above, the category is a repeat even \
though its label is new, and you should replace it.

Then list this board's `lures`: the sets of words a player could look at and defensibly \
group, whether or not they are rows. For each, give the name a player would put on it, the \
words in it, and for each of those words the row it is really filed under.

Two you should be able to name. One of them must span three or more rows — that is the \
set that matches no label, and it is what makes the board hard rather than long. Count \
its words before you answer: {COLS + 1} or more is what you want, exactly {COLS} is the
weaker build, and exactly {COLS} that still leaves the rest of the board sorting cleanly
without them is a second right answer and ruins it.

And check, before you answer, that no word genuinely satisfies two of your five labels. \
That is different from a lure and it is the one defect that makes a board unsolvable \
rather than hard: a lure is a set the labels all *exclude*, and an ambiguous word is one \
two labels both admit.
{"" if lang.is_default else f"Write the words and the labels in {lang.name}."}
"""
    return system, prompt


def solve(words: list[str], lang: Language = ENGLISH) -> tuple[str, str]:
    """Deliberately bare. See the module docstring.

    The one addition for a non-English board is naming the language, and it is not
    optional: the words arrive with no context and a weak model handed HÖNA, PANNA, KAKA
    will answer in English, which makes every category name score near zero on legibility
    and turns the fairness proxy into a translation test. Naming the language is the
    smallest thing that keeps the measurement about grouping.
    """
    system = (
        "You group words. Given 20 words, split them into 5 groups of 4 that each share "
        "something. Use every word exactly once. Name each group. Answer even if you are "
        "unsure — a guess is more useful than a refusal."
        + (
            ""
            if lang.is_default
            else f" The words are {lang.name}; name the groups in {lang.name}."
        )
    )
    prompt = "\n".join(words)
    return system, prompt


def _lures_as_prompt(lures: list[dict]) -> str:
    """The proposer's declared lures, for the two stages that judge the board.

    Plain dicts rather than the pydantic model: `regrade` rebuilds a candidate from stored
    JSON and must not need the schema that wrote it.
    """
    if not lures:
        return "Lures the proposer declared: none stated."
    lines = []
    for lure in lures:
        words = list(lure.get("words", []))
        homes = list(lure.get("where_each_lives", []))
        # A model can return fewer homes than words, or more; neither should raise here.
        homes = (homes + [""] * len(words))[: len(words)]
        spread = ", ".join(f"{w} (filed under {h})" for w, h in zip(words, homes, strict=True))
        lines.append(f"- {lure.get('name', '(unnamed)')}: {len(words)} words — {spread or words}")
    return "Lures the proposer declared — sets that look like groups and are not:\n" + "\n".join(
        lines
    )


def red_team(puzzle: Puzzle, lures: list[dict], lang: Language = ENGLISH) -> tuple[str, str]:
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
        "It is also built to suggest groupings that are not rows at all — a set of words "
        "sharing something real and obvious that matches none of the five labels, spread "
        "across several rows. That is intended too, and it is the board's main defence. "
        "It is fair when no member satisfies a label it is not filed under. Four such words "
        "that cohere are still fair on their own — the player submits them and is simply "
        "wrong — so report them only if the remaining sixteen would still sort into four "
        "sensible rows without them, which would make them a second right answer, or if "
        "one of the members genuinely satisfies a second label.\n"
        "A fault is a word that genuinely satisfies two of the five labels under a precise "
        "reading — where a player could file it either way and defend it. Judge the labels "
        "as written, on their own terms, and ignore how many words each row already has: "
        "'the other row is full' is not a resolution, it is the bug."
        + (
            ""
            if lang.is_default
            else f"\nThis board is in {lang.name}. Judge it as a {lang.name} speaker would: "
            f"a second reading only counts if it is a real {lang.name} sense of the word, not "
            f"a sense its English cognate has. Report separately any word that is misspelled, "
            f"is not current {lang.name}, or is a calque of an English expression."
        )
    )
    rows = "\n".join(f"{g.label}: {', '.join(g.words)}" for g in puzzle.groups)
    prompt = f"""\
Board (all 20 words): {", ".join(puzzle.words)}

{_lures_as_prompt(lures)}

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
    lures: list[dict],
    solver_digest: str,
    red: RedTeamReport | None,
    warnings: list[str],
    lang: Language = ENGLISH,
) -> tuple[str, str]:
    system = (
        "You are the editor. You decide whether a puzzle ships as it stands, goes to a "
        "human, or is killed, using evidence gathered by other models. Nothing rewrites "
        "the board after you — there is no revision step, so do not ask for one.\n\n"
        + GAME_BRIEF
        + "\n"
        + rules_for(lang)
        + (
            ""
            if lang.is_default
            else f"\nThis board is in {lang.name}. Rate its {lang.name} as well as its "
            f"construction: a board whose words are misspelled, whose rows mix definite and "
            f"indefinite forms, or whose categories only work as translations of English ones "
            f"is not fair, whatever its structure looks like. Say so in `reasons`, in English."
        )
        + "\nHow to read the red-team report: this board is *meant* to contain categories "
        "that read wider than they are, so a word being tempted by another row is the "
        "puzzle working. What the red team reports is different — a word two labels both "
        "genuinely admit — and that is a defect, not difficulty.\n"
        "The board is also meant to contain lures: sets of words that look like a group, "
        "match none of the five labels, and are listed for you below. A lure spanning "
        "three or four rows is the strongest thing a board can have and you should mark a "
        "board up for it, not down. A lure of exactly four words drawn from more than one "
        "row is weaker but not a fault — a coherent foursome the board rejects is the "
        "oldest trap there is, and the automatic checks flag it as a warning. The board "
        "is only broken if those four leave the other sixteen still sorting into four "
        "sensible rows without them, which is a second right answer; that is the red "
        "team's second question, not something to infer from the count.\n"
        "A row may also disguise its members at different depths on purpose — one entry "
        "ending in a whole word, another hiding the same kind of word inside a longer one. "
        "That is not incoherence and it is not unfairness. It is what stops the row "
        "falling the instant a player sees one member, and a row built that way is doing "
        "its job.\n"
        "How to read the solver evidence: the solvers are deliberately weak models. "
        "A low recovery rate means hard OR broken, and it is your job to say which — the "
        "red-team report is the tiebreaker, and a clean red team plus low recovery means "
        "hard. Do not treat 0% recovery on one row as proof it is unfair; the hardest row "
        "on a good board is often the one no weak solver finds. A category the solvers "
        "found but could not name is the specific shape of unfair that nothing else in "
        "this pipeline catches.\n"
        "Use 'review' when the board is sound but something specific is wrong — name it "
        "in your reasons, precisely enough that a human can check the claim in seconds. "
        "Use 'reject' when the board is not worth a human's time."
    )
    rows = "\n".join(f"{g.label}: {', '.join(g.words)}" for g in puzzle.groups)
    flags = "\n".join(f"- {w}" for w in warnings) or "- none"
    prompt = f"""\
Puzzle: {puzzle.name}
{rows}

{_lures_as_prompt(lures)}

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


def gloss(puzzle: Puzzle, lang: Language = ENGLISH) -> tuple[str, str]:
    """The last stage, and the only one written for the player rather than about them.

    Everything else in this file is judgement — is the board fair, is it solvable, is it
    dull. This is reference: the board is already accepted and the question is only what
    the row *was*. Playtesters finish a board and go and google the category, so the
    answer is written once, here, and shipped with it.

    Note what the prompt does not do: it does not grade, does not congratulate, and does
    not explain the trap. A player who has solved the row knows it was hard. What they do
    not know is who Adolphe Sax was.

    The word caps and the two worked examples are the correction from the first real run.
    Without them the notes came back accurate and unreadable — 30-word sentences in
    reference-work register ("the principal vegetative and reproductive organs of vascular
    angiosperms"), and, worst of all, summaries that restated the label the player had
    just read: "___ BONE" glossed as "names for anatomical structures ending in the word
    bone", which is the one sentence that adds nothing at all. The old prompt banned that
    move for the word notes and forgot to ban it for the summary.

    This is the only stage whose output a *player* reads, which makes it the only one where
    the board's language is not a detail. A Swedish board glossed in English ships English
    prose under Swedish rows — and because nothing downstream reads the notes, no check in
    the pipeline would have said a word about it.
    """
    system = (
        "You write the short reference note that appears under a solved row of a word "
        "puzzle. The player has already found this category; nothing here is a hint and "
        "nothing is a spoiler.\n\n"
        "Write the sentence that saves them a search. For a category, what the set is. "
        "For a word, the fact that puts it in the set — who the person was, where the "
        "place is, which meaning of the word is in play.\n"
        "Rules:\n"
        "- One sentence each, and short: at most 25 words for a category, at most 20 for a "
        "word. A note is read in about three seconds or it is not read.\n"
        "- Facts only, and only facts you are sure of. If you are not certain what a word "
        "refers to, write the plain definition rather than a detail you are guessing at.\n"
        "- Write for a curious player, not for an encyclopedia. Prefer the concrete fact to "
        "the technical term: 'the thighbone, the longest bone in the body' beats 'a major "
        "skeletal element of the lower extremity'.\n"
        "- Never restate the label. Not in a word's note ('a breed of hound dog' under "
        "BEAGLE says nothing) and not in the summary either. The player has just read the "
        "label; the summary has to add to it.\n"
        "- For a fill-in-the-blank category ('___ CLIP', 'STAR ___'), do not describe the "
        "pattern — it is visible. Say what the four completions have in common, or what is "
        "worth knowing about the set: for '___ BONE', that none of the four is the "
        "anatomical name.\n"
        "- No praise, no commentary on the puzzle, no second person.\n"
        "- Plain prose. No markdown, no lists inside a note.\n\n"
        "Two examples of the register, both at the right length:\n"
        "  Words derived from people's names — 'Eponyms: everyday words that started out as "
        "somebody's name.'\n"
        "  BOYCOTT — 'Charles Boycott, the Irish land agent whose tenants refused to deal "
        "with him in 1880.'"
        + (
            ""
            if lang.is_default
            else f"\n\nThis board is in {lang.name} and the player reads these notes, so "
            f"write every summary and every word note in {lang.name}. The two examples above "
            f"are English because the board they came from was; copy their length and their "
            f"register, not their language."
        )
    )
    rows = "\n".join(f"{g.label}: {', '.join(g.words)}" for g in puzzle.groups)
    prompt = f"""\
Explain this board's five categories and all {ROWS * COLS} of its words.

{rows}

Copy each label and each word exactly as written above.
"""
    return system, prompt


def invent(*, count: int, known: list[str], lang: Language = ENGLISH) -> tuple[str, str]:
    """Stage 0. Cheap, bulk, and run before any board exists.

    Asking for forty categories in one call is fine where asking for ten boards is not: a
    board is a design with five interacting parts and degrades when batched, a category is
    a one-line idea.
    """
    if lang.prompt_native:
        return prompts_sv.invent(count=count, known=known, lang=lang)
    system = (
        "You invent categories for a word puzzle. Not boards — just categories, one line "
        "each, to be drawn on later.\n\n" + GAME_BRIEF + "\n"
        "The best category reads wider than it is. 'Stone fruit' looks like 'fruit' and "
        "tempts APPLE, but an apple is a pome, so the temptation resolves the moment the "
        "label is read precisely. 'Circus performers' looks like 'circus things' and "
        "excludes TRAPEZE. That narrowing is what you are being asked for.\n"
        "Not every category should be a kind of thing. A situation ('what you might see "
        "sticking out of a window'), a property ('things with a hole in the middle'), an "
        "action ('what a barber does to you') or an origin ('words from people's names') "
        "all make better rows than another taxonomy, because they cannot be cracked by "
        "asking what sort of word something is.\n"
        "Avoid categories that need regional or generational knowledge. Members may be up "
        "to 20 characters and may be two words, but no single word in one may pass 12."
        + (
            ""
            if lang.is_default
            else f"\nWrite the labels in {lang.name}, for a board that will be played in "
            f"{lang.name}. The 12-character limit on a single word is the hard one here: "
            f"{lang.name} compounds are written closed and run long, and the allowance for "
            f"two-word entries does not help a language that joins its words, so a category "
            f"whose natural members are all long compounds is not usable however good the "
            f"idea is. Invent {lang.name} categories rather than "
            f"translating English ones — a category that is only interesting in English is "
            f"worse than useless, because it will read as a translation."
        )
    )
    have = ", ".join(sorted(known)[:300]) or "(the pool is empty)"
    prompt = f"""\
Invent {count} categories{"" if lang.is_default else f", in {lang.name}"}.

For each, give the label as a player would read it, and the wider reading it will be
mistaken for along with the word that mistake pulls in.

Already in the pool, so do not repeat the idea: {have}
"""
    return system, prompt
