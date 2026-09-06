# Can the pipeline write Swedish?

Yes, and better than [DESIGN.md](../DESIGN.md) expected. Three boards were generated
against Vertex for $0.58; two are at roughly the standard of the hand-written English ones,
the Swedish is idiomatic throughout, and the wordplay devices survive the crossing with one
rewrite. The two things DESIGN.md flagged — the 12-character cap and weak LLM Swedish —
are not what stands in the way.

What stands in the way is the corpus. There are no Swedish seed boards, so the proposer is
shown English ones; and the category dedupe index cannot compare across languages, so the
first Swedish batch is told nothing has shipped. Between them, **3 of the 15 categories the
run produced are translations of categories already shipped in English**. Neither problem
needs a model to fix and neither is about Swedish.

The recommendation is therefore _later, and soon_ — the reasoning is at the end.

---

## 1. What is language-specific

Line numbers are as of `9ecc5dc`, before the prototype below.

### Must change — a Swedish board is wrong or rejected without it

| Where                                     | What                                                                                                                                                        |
| ----------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `pipeline/connectris_pipeline/spec.py:27` | `WORD_RE` is `[A-Z][A-Z'\- ]{0,11}` — ASCII only, so Å Ä Ö are a `charset` fatal.                                                                           |
| `spec.py:94`                              | `normalise_word` does `NFKD` + `encode("ascii", "ignore")`, which **destroys** Å Ä Ö instead of rejecting them. This is the serious one; see below.         |
| `spec.py:134`                             | `label_key` strips to `[^a-z ]+`, so a Swedish label is compared as its consonant skeleton: `stjärnor` → `stjrnor`.                                         |
| `spec.py:174`                             | The label-gives-it-away check strips the same way.                                                                                                          |
| `scoring.py:124`                          | `_tokens` strips the same way, and this one feeds the fairness proxy.                                                                                       |
| `categories.py:36–43`                     | Two of the seven `DEVICES` are English grammar, not puzzle design: `___ WORD` and `WORD ___` describe open compounds, and Swedish writes compounds closed.  |
| `prompts.py:36`                           | "Plain uppercase English."                                                                                                                                  |
| `prompts.py:55–56`                        | The menu of category kinds names `___ WORD` and homophones.                                                                                                 |
| everywhere                                | Nothing tells any model to answer in Swedish. `Config` had no language; `Puzzle.language` (`spec.py:60`) defaulted to `"en"` and was never set by anything. |

**`normalise_word` is the defect that matters**, because it is the one that hides itself.
The fold ran _before_ the regex, so the regex never fired: not one of the offending words
would have raised an error. And solver output is compared to the answer key through the
same function, so the corruption was symmetric — recovery and legibility would have scored
normally on a board full of misspellings.

Measured against the boards this run actually produced: **13 of 60 tiles (22%) carry Å, Ä
or Ö**, 11 of them distinct. The old code rewrites every one, silently:

```
BÄGARE → BAGARE      RIDÅ → RIDA        SVÄRTA → SVARTA
FÄNRIK → FANRIK      KÅSA → KASA        LÖJTNANT → LOJTNANT
FLÖJT  → FLOJT       NÄVE → NAVE        LÖPARE → LOPARE
TVÄR   → TVAR        ÅLDER → ALDER
```

Three of those land on a _different real Swedish word_: BÄGARE (goblet) becomes BAGARE
(baker), RIDÅ (curtain) becomes RIDA (to ride), SVÄRTA (velvet scoter) becomes SVARTA
(black). BAGARE would have shipped in a row labelled "Traditionella dryckeskärl" —
drinking vessels — with a clean bill of health from every stage.

### Would want to change — legal, but worse

- `schema.py:39` — `ProposedGroup.label` says _"Use '\_\_\_ WORD' or 'WORD \_\_\_' for
  word-joining categories."_ This ships to the model as part of the JSON schema, so it is
  prompt. I left it alone in the prototype, and the Swedish run duly produced the label
  `JÄRN ___`. Swedish writes JÄRNNÄVE closed; the notation should be `JÄRN‑` or `JÄRN+`.
  A small anglicism, traceable to one line of a field description.
- `spec.py:117` — `Corpus.from_game_json` has no language. The **word** axis must be
  scoped (BAND, PARK, HAND and KORT are ordinary words in both languages, and one board
  should not forbid the other from using them). The **category** axis must _not_ be; §5
  shows what happened when I scoped it.
- `corpus.py:20` — `load()` returns every shipped puzzle as a few-shot example regardless
  of language.
- `scoring.py:29–44` — `_STOPWORDS` is English. `scoring.py:140–142`'s 0.5 penalty is
  calibrated on "unrelated English phrases".
- `prompts.py` throughout — every worked example is "stone fruit". It calqued: the Swedish
  category pool came back containing _Stenfrukter_.
- `Tile.svelte:101` (`white-space: nowrap`) and `engine.spec.ts:28` (the 12 cap). §6.
- `spec.py:188` — `max_reused_words` is 4 and the gate is `>`. A row is exactly four
  words, so **one entire duplicated row slides through unflagged**. This is language-
  neutral and pre-existing, and it fired in this run: FÄNRIK, LÖJTNANT, KAPTEN, MAJOR
  appears identically on two of three boards.

### Explicitly not a problem

`spec.py:98` `slugify` folds Å→A, Ä→A, Ö→O. That is the correct Swedish convention for
slugs, group ids are internal, and the existing `-b` suffix loop handles the collisions it
creates. Leave it.

---

## 2. How language should be modelled

**Per run for configuration, per puzzle for data.** `Config.language` decides what a batch
writes; `Puzzle.language` records what a board is.

Per-run is not a convenience. Four things a batch shares are all language-bound — the
category pool, the few-shot examples, the device list and the dedupe index — and a mixed
batch would need every one of them keyed by language and would still propose half its
boards against the wrong pool. Per-puzzle stays because the _data_ is mixed even when no
single run is: `puzzles.json` holds both and the app reads it.

A language is not a flag. Three things vary together and there is no useful way to vary one
alone: the alphabet (a validation question), the devices (the interesting one), and the
register — "no knowledge that needs a particular region" means something else when the
language picks the region. So the prototype has a `Language` record and the prompts take
one, rather than taking a code and branching. Adding Norwegian is adding an entry.

### The pool

One file per language: `categories.json`, `categories.sv.json`. Not one file with a column
— a pool entry is _a label in a language_, "Stone fruit" is not a slot a Swedish board can
fill, so the two never share a row, and keeping English at the unsuffixed name means every
existing path still works.

### The shared-corpus question, and the mistake I made

I scoped **both** axes of `Corpus` by language and wrote a docstring admitting the category
half was "the conservative call rather than the correct one". The run proved it wrong
within three boards. With the index narrowed to `sv`, the first Swedish batch was told
_nothing has shipped_ — and promptly re-invented the English catalogue in translation:

| Swedish, generated                                 | Already shipped, in English                            |
| -------------------------------------------------- | ------------------------------------------------------ |
| Traditionella dryckeskärl                          | Styles of drinking glasses                             |
| Bleckblåsinstrument (TRUMPET, TROMBON, TUBA)       | Orchestral brass instruments (TRUMPET, TROMBONE, TUBA) |
| Träblåsinstrument (FLÖJT, OBOE, KLARINETT, FAGOTT) | Woodwinds with reeds (CLARINET, OBOE, BASSOON)         |
| _Stenfrukter_ (in the pool)                        | the prompt's own worked example, "stone fruit"         |

Three of fifteen categories, 20%. So:

- **Words: scope by language.** A word being taken in English says nothing about Swedish.
- **Categories: do not.** "Stone fruit" and "stenfrukt" are the same board idea in two
  costumes, and shipping both a week apart is exactly the repetition the index exists to
  prevent.

But `label_key` is lexical, so it _cannot_ do the cross-language comparison — the folded
keys share nothing. This needs either a concept id stored on the pool entry (cheap, and the
inventor can emit one) or an embedding. It is the one place where the embedding path that
was cut for English is worth revisiting, because the English argument for cutting it — that
free token overlap was stricter and more accurate — is an argument about two English
phrases and does not transfer.

---

## 3. What I changed to prototype

Minimum to get a real run, on branch `worktree-agent-a999ab0c774ebd048`. Full CI sequence
green (`ruff check`, `ruff format --check`, `ty check`, 78 tests, `cli check`).

- **`spec.py`** — `ALPHABETS` per language and `word_re(language)`, so "not in this
  language" is an error a run can see. `normalise_word` now folds decoration but protects
  Å Ä Ö: CAFÉ still becomes CAFE, RÅTTA stays RÅTTA. The protected set is per-alphabet, not
  per-board, because the dedupe index and the scorer both call this without a language in
  hand and a fold that varied by caller would make a word compare unequal to itself.
  `label_key` and the label check keep Swedish letters. `Corpus.from_game_json` takes an
  optional language.
- **`language.py`** (new) — `Language` records for English and Swedish: alphabet, device
  list, category-kind menu, and an addendum to the construction rules.
- **`categories.py`** — devices move to `language.py`; `pool_for` / `source_for` give each
  language its own pool file.
- **`prompts.py`** — every prompt takes a `Language`. The instructions stay in English with
  the output language stated explicitly, which is one variable rather than two: if Swedish
  boards come out weak, an English prompt asking for Swedish output has an obvious next
  thing to try. The solver prompt is told the words are Swedish — without that a weak model
  names its groups in English and the legibility measure becomes a translation test.
- **`config.py` / `cli.py`** — `language` knob and a `--language` flag.
- **`scoring.py`** — Swedish stopwords, Swedish letters in the tokeniser.
- **6 new tests** pinning the Å Ä Ö behaviour and the corpus scoping.

### The Swedish device list

Four of the seven English devices translate unchanged and are kept (hidden words, ordered
sets, synonyms, second meanings). The two compound devices are rewritten around closed
compounds — "four stems that take the same second element", with only the stem on the tile.
Two are added that only exist here: the Å/Ä/Ö minimal pair (free wordplay in a language
with three extra vowels) and the fixed expression (where Swedish idiom actually lives).
Homophones are dropped; Swedish has them but nothing like English's density.

**Only three of the eight were exercised in this run** (efterled, ordered set, synonyms).
Both of the ones I invented for Swedish are untested.

---

## 4. The boards

Run `20260905-171202`, seed 0, `gemini-3.8-flash` at `thinking_level: high`.

### `gen-…-00` — "TITLAR OCH BERG" · rejected (87% solver recovery) · graded 5/5

```
Magmatiska bergarter                       BASALT  DIABAS  GRANIT  PORFYR
Militära officersgrader i stigande ordning FÄNRIK  LÖJTNANT KAPTEN MAJOR
Adelstitlar                                BARON   FURSTE  GREVE   HERTIG
Traditionella dryckeskärl                  BÄGARE  KALK    KÅSA    SEJDEL
Schackpjäser                               BONDE   DAM     KUNG    LÖPARE
```

**Good, and rejected for the wrong-ish reason.** The Swedish is impeccable and the drinking
vessels are a genuinely Swedish row — KÅSA (a Nordic burl cup) and SEJDEL (a beer stein)
are words no translation from English would produce. The KALK trap is a pun that exists
only in Swedish: _kalk_ is both a chalice and limestone, so it pulls hard toward the rocks
and resolves cleanly. Chess pieces colliding with nobility is elegant — DAM and KUNG both
tempt, and the labels exclude them precisely (a monarch is not _adel_; _dam_ is not a
Swedish title, unlike English "Dame").

It was rejected only for 87% weak-solver recovery, i.e. for being easy. I do not trust that
number in Swedish: see §7.

### `gen-…-01` — "Fasta förbindelser" · accepted (47% recovery)

```
Gamla längdmått      ALN     FAMN    FOT     TUM
Delar av ett drama   AKT     EPILOG  PROLOG  SCEN
Dykänder             BRUNAND EJDER   KNIPA   SVÄRTA
Träförbindningar     FOG     NOT     SKARV   TAPP
JÄRN ___             NÄVE    RIDÅ    SPIK    ÅLDER
```

**The best of the three, and the one that answers the device question.** JÄRNNÄVE,
JÄRNRIDÅ, JÄRNSPIK and JÄRNÅLDER are all real and common closed compounds, and every decoy
is real and Swedish-specific: NÄVE pulls to the old measures (_en näve_ is a rough
quantity), RIDÅ to the drama, SPIK to the joinery. SKARV is filed under joinery and is also
the cormorant, which pulls at the diving ducks — a pun with no English counterpart. ALN,
FAMN, FOT, TUM is culturally specific in the way the game wants.

So the compound device works in a closed-compound language. Two nits: the label notation
`JÄRN ___` implies a space Swedish does not write (§1, `schema.py:39`), and _Dykänder_ is
specialist — BRUNAND is a birdwatcher's word, and the weak solver could only name the row
"Fåglar".

### `gen-…-02` — "KLARA TONER" · accepted (73% recovery)

```
Bleckblåsinstrument             TRUMPET TROMBON  TUBA    KORNETT
Träblåsinstrument               FLÖJT   OBOE     KLARINETT FAGOTT
Officersgrader i Försvarsmakten FÄNRIK  LÖJTNANT KAPTEN  MAJOR
Betyder 'surmulen'              BUTTER  VRESIG   TVÄR    TRUMPEN
Köksredskap                     VISP    KAVEL    SLEV    TRATT
```

**The weakest, and it should not have been accepted.** Three faults. It repeats an entire
row from board 00, verbatim, unflagged. Its two instrument rows are translations of two
shipped English categories. And one of its stated traps is _"BUTTER lockar en tvåspråkig
spelare mot köksgruppen"_ — a decoy that only works if the player knows English "butter".
That is the few-shot examples bleeding into the design, and it is not a Swedish trap.

What is good: BUTTER / VRESIG / TVÄR / TRUMPEN is an idiomatic set for _surmulen_, and
TRUMPEN sitting one letter from TRUMPET in another row is a genuinely Swedish device.
KORNETT is a live risk — both a brass instrument and a historical cavalry rank — and
although the label "Officersgrader i Försvarsmakten" excludes it, this is exactly the
double-filed word the red team exists to find, and the red team reported "clean".

### Would a Swedish speaker call these fair?

Two of three, yes. No misspellings, no en/ett errors, no definite/indefinite mixing inside
a row, correct Å Ä Ö on all 13 words that need them, and no calqued idiom in the _labels_.
That is better than DESIGN.md's prediction of "noticeably weaker". The failure is not
Swedish competence — it is that a fifth of the categories were English ones in translation,
which a Swedish player would not notice and an English-speaking one would.

---

## 5. Word length: the cap did not bind, and that is the finding

All 60 tiles, measured:

| Corpus                      | n   | mean      | median | max   | >8    | >12    |
| --------------------------- | --- | --------- | ------ | ----- | ----- | ------ |
| **Swedish, generated**      | 60  | **5.18**  | 5      | **9** | 1.7%  | **0%** |
| English, generated (3 runs) | 800 | 5.25–5.63 | 5      | 10    | 3–7%  | 0%     |
| English, shipped            | 60  | 6.23      | 6      | 10    | 13.3% | 0%     |

The Swedish boards are **shorter than the English ones**. The longest word on any of them is
KLARINETT, at 9. The cap has never fired in any run, in either language.

That is not the same as "the cap is fine", and the difference matters. The prompt told the
model the cap was the binding constraint and to prefer simplex words — so the constraint
bound at _authoring_ time, and what it cost is invisible in the artifacts. The lexicon-level
pressure is real: there is no Swedish dictionary on this machine, but German is available
and shares the one relevant feature, and **39.7% of German nouns exceed 12 characters
against 5.0% of English words**. German compounds run longer than Swedish ones, so treat
that as an upper bound on direction, not a measurement.

The model routed around the cap by choosing categories with short members. The categories it
could not choose are the cost, and from its own pool they are visible: _Plattfiskar_
(HÄLLEFLUNDRA 12, SKRUBBSKÄDDA 12, SANDSKÄDDA 10), _Skalbaggar_ (NYCKELPIGA 10, GULDBAGGE 9,
DYKARBAGGE 10, BLADHORNSBAGGE 14). Beyond the pool, the everyday domestic and occupational
vocabulary a general-audience puzzle wants: KAFFEBRYGGARE 13, SJUKSKÖTERSKA 13,
MIKROVÅGSUGN 12, TVÄTTMASKIN 11, DAMMSUGARE 10, TANDLÄKARE 10, BARNMORSKA 10.

**So: the cap will not reject Swedish boards. It will quietly delete Swedish categories,
and you will never see it happen.**

### Does the cap move, or the layout?

The layout. On a 375px phone the board gets 331px (`.app` 12px padding, `.well` 10px), minus
three 7px gaps, so a tile is 77.5px. `Tile.svelte:96` sizes type at
`min(0.95rem, (100cqw − 12px) / (len × 0.62))`, which gives:

| chars | 7    | 9    | 10   | 11  | **12**  | 13  | 14  |
| ----- | ---- | ---- | ---- | --- | ------- | --- | --- |
| px    | 15.1 | 11.7 | 10.6 | 9.6 | **8.8** | 8.1 | 7.5 |

The 12-character cap already renders at ~8.8px. It is not a conservative cap with headroom
— it is already sitting on the legibility floor, which is why the shipped English boards
top out at 10. Raising it to 14 means 7.5px type. So the cap cannot move on its own.

The cheap lever is `Tile.svelte:101`, `white-space: nowrap`. `--row-h` is
`clamp(56px, 11.5vh, 80px)` and `line-height` is 1.05, so there is vertical room for two
lines, and Swedish compounds break cleanly at the morpheme boundary: KAFFE|BRYGGARE renders
as two ~7-character lines at full 15.2px, which is far more legible than one line at 8.1px.
That is a `Tile.svelte` change, not a data change — but it touches the board's visual rhythm,
which pin 7 cares about, so it wants a design pass and not just a CSS edit. `MAX_WORD_LEN` is
mirrored in `engine.spec.ts:28` and `schema.py:42`, so moving the number means moving three.

---

## 6. Two other things the run measured

**Legibility degrades in Swedish, structurally.** Mean legibility was **0.430** against
0.557–0.769 across the three English runs. The cause is mechanical: closed compounds hide
the shared head _inside_ a word, where a whitespace tokeniser cannot see it.

|                                                        | Swedish | English equivalent |
| ------------------------------------------------------ | ------- | ------------------ |
| "Officersgrader i Försvarsmakten" vs "Militära grader" | 0.136   | 0.400              |
| "Bleckblåsinstrument" vs "Blåsinstrument"              | 0.424   | 0.667              |
| "Gamla längdmått" vs "Gammaldags måttenheter"          | 0.270   | 0.512              |

Swedish compound heads are final, so counting two tokens as matching when one is a _suffix_
of the other recovers part of it — 0.136 → 0.333 and 0.424 → 1.000 on the two above, with
no regression on five English cases I checked. It is a partial fix: _längdmått_ vs
_måttenheter_ still scores 0.270, because there the shared morpheme is the head of one and
the modifier of the other. The measure errs toward the review queue, which is the safe
direction, but it carries less signal in Swedish than the thresholds assume.

**The solvers preserved Å Ä Ö exactly.** Zero stray words across nine attempts — every
echoed word matched the board. The corruption risk was entirely in our own code.

---

## 7. Cost

One run, no retries, `--count 3`, `invent_batch 12`.

| Stage     | Calls  | Input      | Output    | Thinking    |
| --------- | ------ | ---------- | --------- | ----------- |
| invent    | 1      | 653        | 555       | 6,388       |
| propose   | 3      | 5,463      | 1,514     | 98,978      |
| solve     | 9      | 2,934      | 1,909     | 1,038       |
| red_team  | 3      | 5,771      | 108       | 41,658      |
| grade     | 3      | 6,404      | 312       | 7,010       |
| **total** | **19** | **21,225** | **4,398** | **155,072** |

Thinking is 97% of billed output; propose alone is 64% of the thinking. Scaling against the
reference run's 1,146,408 billed output tokens for $4.15 gives **≈ $0.58**, i.e. **$0.19 a
board** — statistically identical to English's $0.21. Swedish is not more expensive to
generate. Spend against the $1 cap: **$0.58, with $0.42 unspent.**

I chose not to spend the remainder. The obvious second experiment is a batch with
hand-written Swedish seed boards to confirm the calque goes away, but at ~$0.19 a board that
buys n=2, which is not enough to conclude anything the textual correspondence in §2 does not
already establish.

---

## 8. Recommendation

**Pursue Swedish — later, and the blocker is not Swedish.**

Not _now_, because shipping the current output would ship translated English categories
under a Swedish flag, which is the worst available version of a second language. Not _never_,
because the run refutes the pessimistic half of DESIGN.md's note: the generation quality is
good, the devices survive, the cost is identical, and the orthography and agreement were
correct without a human touching them.

Three things gate it, and none needs a model:

1. **Three hand-written Swedish seed boards.** This is the single highest-value item. The
   proposer currently sees English examples and is asked politely not to translate them; it
   translated them anyway, in 20% of categories. Seeds are free and they fix the largest
   observed defect.
2. **Cross-language category dedupe** — a concept id on the pool entry, emitted by the
   inventor. `label_key` cannot do this and no amount of tuning will make it.
3. **A tile that can wrap**, before the cap silently narrows the Swedish category space any
   further.

Then a batch of ten with a Swedish reviewer in the loop. `regrade` is free, so the
thresholds can be refitted against Swedish evidence afterwards without spending again.

The one thing I would change in DESIGN.md today: the note says the word-length cap "will
bite on compounds". It will, but not by blowing out a tile — the model avoids long words
long before validation sees them. It bites by deleting categories, invisibly. That is a
harder problem than the one the note anticipated and it argues for the layout change rather
than for trusting the cap.

---

## 9. What I am unsure about

- **n = 3.** One batch, one seed, one model. Everything above rests on three boards.
- **I am the only Swedish judge here, and I wrote the prompts**, so I am partly marking my
  own homework. The register calls in §4 in particular want a second Swedish speaker.
- **Five of eight Swedish devices were never allocated**, including both I invented for
  Swedish (the Å/Ä/Ö minimal pair and the fixed expression). Whether they produce anything
  good is untested.
- **The difficulty proxy is less trustworthy in Swedish than in English.**
  `gemini-3.1-flash-lite`'s Swedish is not its English, so board 00's 87% recovery may be
  measuring that the model knows Swedish rock names rather than that a human finds the board
  easy. That number is what rejected the board I liked best. This compounds DESIGN.md's
  existing caveat rather than being a new one.
- **The red team reported "clean" on all three**, consistent with finding zero alternative
  partitions in 20 English boards. I think it missed KORNETT. So either Swedish boards are
  unusually clean, or the stage does not work, and now that question is open in two
  languages at once.
- **Whether prompting _in_ Swedish beats prompting in English about Swedish.** I chose
  English deliberately to keep one variable, but I do not know which is better and it is
  cheap to find out.
- **Whether `normalise_word` protecting Å Ä Ö but folding É is the right line.** It is the
  line that keeps English behaviour identical and makes Swedish correct, but it is a
  judgement about which marks are letters, and it will need revisiting for the first
  language where that call is less obvious.
