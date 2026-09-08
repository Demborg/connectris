# Prompting in Swedish

Yes, at the stage where it turns out to matter — and the reason is not the one I expected.

Boards written under a Swedish prompt are not obviously better boards. What changes is the
**register of what gets invented** and the **language the model reasons in**. The inventor
prompted in English reached for Sweden as a subject: folklore, Nordic capitals, Christmas
food. Prompted in Swedish it reached for citrus fruit, choir parts, boxing and geometry —
ordinary categories that happen to be in Swedish. And the proposer prompted in English
wrote two thirds of its own trap notes in English, which matters because those notes are
shipped verbatim into the red team's and the grader's prompts.

This is a follow-up to [swedish-generation.md](swedish-generation.md), whose §9 left the
question open. It also closes two of the three blockers that report named. Spend: **$2.76
of a $4 budget**, across 22 boards.

---

## 1. What was run

A 2×2, three boards an arm, plus one follow-up of four.

|                                        | English seeds       | Swedish seeds       |
| -------------------------------------- | ------------------- | ------------------- |
| **English prompt** (today's behaviour) | `en-seed_en-prompt` | `sv-seed_en-prompt` |
| **Swedish prompt** (`prompts_sv`)      | `en-seed_sv-prompt` | `sv-seed_sv-prompt` |

**Seeds** are the few-shot boards the proposer copies its standard from: either the three
shipped English boards, or three hand-written Swedish ones ([`seeds.sv.json`](../pipeline/seeds.sv.json)).
**Prompt** is the language the _authoring_ instructions are written in. `prompts_sv`
translates the game brief, the construction rules, the device list and the propose and
invent asks clause for clause; it does not improve them, because a prompt that were better
as well as Swedish would answer a question nobody asked.

Three things were held constant, and the third is the one that costs something:

- **Solve, red-team and grade stay in English in every arm.** They are the measuring
  instruments. An instrument that moves between arms measures nothing.
- **Three examples per arm, not two.** Production shows `[:2]` and the Swedish seeds are
  three; handing one arm two examples and the other three would confound example count with
  example language. (That `[:2]` is itself worth revisiting — it silently discards a third
  of any seed set someone writes.)
- **One category pool, shared by all four arms.** Letting each prompt language invent its
  own pool was tried and rejected: the two pools come back with different _themes_, and at
  three boards an arm's subject matter would have swamped its prompt. So the pool question
  is answered separately and far more cheaply, by running the inventor both ways and reading
  the two pools side by side. That turned out to be where the answer was.

The harness is [`pipeline/experiments/swedish_prompt_arms.py`](../pipeline/experiments/swedish_prompt_arms.py).

### The confound I introduced on purpose

The 2×2 ran **after** the cross-language concept index landed, so `en-seed_en-prompt` is
"production plus the fix", not production as the earlier report measured it. Calque rate
went from 3-of-15 to **0 of 60 categories across all four arms** — and that drop belongs to
the concept index, which every arm shared, not to the prompt language or the seeds. Fixing
a known defect before measuring what is left is the right order to do things in, but it
means this run cannot restate the 20% baseline.

---

## 2. The inventor: the result that actually matters

Two calls, twelve categories each, $0.04.

| Inventor prompted in English      | Inventor prompted in Swedish |
| --------------------------------- | ---------------------------- |
| Hjortdjur                         | Citrusfrukter                |
| Ugglor                            | Stråkinstrument              |
| **Stenfrukter**                   | Barrträd                     |
| **Stater med kust mot Östersjön** | Gnagare                      |
| Rotfrukter                        | Primtal                      |
| Stråkinstrument                   | Kastgrenar i friidrott       |
| Ädelmetaller                      | Giftsormar                   |
| Jätteplaneter i solsystemet       | Stenplaneter i solsystemet   |
| **Nordiska huvudstäder**          | Tävlingssimsätt              |
| **Väsen i nordisk folktro**       | Sticktagningsspel            |
| **Volymmått i svenska recept**    | Månar i solsystemet          |

Two things at once.

**The English-prompted inventor calqued its own worked example.** _Stenfrukter_ is "stone
fruit", the phrase the prompt uses to explain what a narrowing category is. It did this in
the September run too. The Swedish-prompted inventor did not — it produced _Citrusfrukter_
instead, a fruit category that is not that fruit category. Note that the concept index
cannot catch this one: stone fruit has never shipped, so it is not in the index. Only the
prompt can fix a prompt's own example bleeding into the output.

**Four of eleven English-prompted categories are Sweden-as-a-subject, against zero.**
Östersjön, Nordic capitals, folklore, measures in Swedish recipes. Asked in English to write
Swedish categories, the model treats Swedishness as the topic. Asked in Swedish, it treats
Swedish as the medium and writes about prime numbers and swimming strokes.

I first wrote this up as a cost. It is the opposite, and the correction is the owner's: the
game is not about chasing polar bears away from the faluröda stuga with surströmming. A
Swedish board should be a board a Swede plays, not a board about Sweden.

---

## 3. The 2×2

| arm                 | acc/rev/rej | word len | >8 chars | Å Ä Ö | recovery | legibility | traps in Swedish |
| ------------------- | ----------- | -------- | -------- | ----- | -------- | ---------- | ---------------- |
| `en-seed_en-prompt` | 2/0/1       | 5.37     | 10.0%    | 18.3% | 0.644    | 0.741      | **5/15**         |
| `sv-seed_en-prompt` | 2/0/1       | 5.27     | 10.0%    | 20.0% | 0.733    | 0.573      | **5/15**         |
| `en-seed_sv-prompt` | 1/0/2       | 5.27     | 6.7%     | 26.7% | 0.889    | 0.581      | **14/15**        |
| `sv-seed_sv-prompt` | 3/0/0       | 5.60     | 13.3%    | 11.7% | 0.711    | 0.493      | **15/15**        |

Grader fairness and elegance were **5/5 on every one of the twelve boards**, so that column
is omitted: it carries no signal here and the grader is saturated, which is its own finding.
Zero automatic warnings fired anywhere — no stale words, no stale concepts, no
label-gives-it-away.

**The one clean effect is the last column.** Under an English prompt the proposer wrote a
third of its trap notes in Swedish and the rest in English; under a Swedish prompt, all but
one. This is not cosmetic. The trap note is the proposer's account of what its own board is
doing, and it goes straight into the red team's prompt and the grader's. An English note
about a Swedish board is the mode that produced the September run's worst moment — a trap
reading _"BUTTER lockar en tvåspråkig spelare mot köksgruppen"_, a decoy that only works on
a player who knows the English word.

**Everything else is noise at this n.** Acceptance is 2/2/1/3 and recovery is 0.64/0.73/
0.89/0.71 with no pattern that survives three boards an arm. Word length, diacritic density
and legibility are flat. Anyone reading a difference into those columns is reading noise.

---

## 4. The follow-up: the neutral pool

The 2×2 held the pool fixed at the English-prompted one, which meant every arm was pushed
toward folklore and capital cities whatever its prompt said. So the winning configuration —
Swedish seeds, Swedish prompt — was run again against the _Swedish-prompted_ pool. Four
boards, $0.78.

**3 accepted, 1 to review, 0 rejected**, the best outcome of any arm. And the register
followed the pool exactly as hoped:

|                          | Nordic pool | Neutral pool |
| ------------------------ | ----------- | ------------ |
| Sweden-as-a-subject rows | **3/15**    | **1/20**     |

The one survivor is _Svenska rovdjur på land_ (BJÖRN, VARG, JÄRV, RÄV), which is a fair
category rather than a costume. The other nineteen rows are string instruments, retail
packaging, conifers, citrus, flightless birds, choir parts, spices, throwing events, birds of
prey, firearms, post, venomous snakes, neckwear, eusocial insects, root vegetables — a board
a Swede plays.

### The red team found something, for the first time

`KAST OCH SKOTT` went to review because the red team reported that **SLÄGGA satisfies two
labels**: it is a throwing event, and _slägga → slagga_ is also a real Å/Ä/Ö minimal pair
("slagga" is an established verb). The intended restriction was to noun pairs (fara, hona,
lada, mossa) and the label never said so. The grader agreed and asked for the label to be
tightened before shipping.

That is the first genuine dual-membership the red team has caught in either language. The
September report left it an open question whether the stage worked at all, having reported
"clean" on all three Swedish boards and found zero alternative partitions in twenty English
ones. It works.

### And the untested device got tested

Because of a bug (§6), all four boards were allocated the same device — the **Å/Ä/Ö minimal
pair**, one of the two invented for Swedish in the September prototype and never exercised
since. Four boards is a real trial of it, and the verdict is: it works, and it is delicate.

```
BÅR  SÄL  LÖK  NÖT      bår→bar, säl→sal, lök→lok, nöt→not     accepted
BÄCK GÅS  HÄLL RÖST     bäck→back, gås→gas, häll→hall, röst→rost   accepted
FÅRA HÖNA LÅDA MÖSSA    fåra→fara, höna→hona, låda→lada, mössa→mossa   review
```

All twelve pairs are correct Swedish. The failure mode is exactly the one the review board
found: the category as stated ("changes meaning if Å, Ä or Ö becomes A or O") is wider than
the set intended, because Swedish has a great many such pairs and some of them are verbs. The
label has to name the word class. **The fixed-expression device remains untested.**

---

## 5. Convergence, and why the concept index earns its keep in Swedish

Across the twelve 2×2 boards, five four-word rows are byte-identical between arms:

| row                                  | arms | was the theme allocated? |
| ------------------------------------ | ---- | ------------------------ |
| HELSINGFORS KÖPENHAMN OSLO STOCKHOLM | 4/4  | yes                      |
| DOVHJORT KRONHJORT REN ÄLG           | 4/4  | yes                      |
| **BRIS KULING ORKAN STORM**          | 3/4  | **no**                   |
| MARA TOMTE VÄTTE ÄLVA                | 2/4  | yes                      |
| **BLÅBÄR HALLON HJORTRON LINGON**    | 2/4  | **no**                   |

Two of them nobody asked for. The Beaufort scale turned up unprompted in three of four arms;
so did the wild berries in two. ALN/FAMN/FOT/TUM appeared here _and_ in the September run.
Even where the theme was allocated, the word choice converged — four arms independently
picked the same four capitals and the same four deer.

There is a small attractor set for "a Swedish puzzle category", and Swedish starts with an
empty corpus. A nightly Swedish run would ship the wind scale and the forest berries inside
a fortnight and keep proposing them until something remembered. That is a concrete argument
that the cross-language concept index is load-bearing for Swedish specifically, rather than
merely tidy — and an argument for seeding the pool generously before the first live night.

---

## 6. What changed in the code

All of it rebased onto `main` at `b8a68ca`, which had moved a long way (a backend,
`store.py`, `nightly.py`, `gloss.py`). CI green: ruff, ruff format, ty, 148 Python tests,
`cli check`, 164 JS tests, prettier.

**The two the September report asked for.**

- **`max_reused_words` was 4 with a `>` gate**, and a row is exactly four words, so one
  wholly duplicated row went unflagged — which is how FÄNRIK, LÖJTNANT, KAPTEN, MAJOR shipped
  identically on two boards of one run. Now 3.
- **Cross-language category dedupe.** A group and a pool entry carry a `concept`: the idea as
  a short English noun phrase, whatever language the label is in. `Corpus.concepts` is the one
  index deliberately _not_ narrowed by language, matched by set containment so "brass
  instruments" catches "orchestral brass instruments". Backfilled onto the fifteen shipped
  English categories, and checked against the three calques the September run actually
  produced: it catches all three and passes the Swedish-native rows. It is a backstop; the
  stronger half is that the concept list is now _in the proposer's prompt_, where a model
  about to write "drinking vessels" can see "drinking glasses" already there.

**One that was necessary for the experiment to be coherent.** `ProposedGroup.label`'s field
description told the model to write `___ WORD`, which is English orthography and is where
`JÄRN ___` came from. It now asks for the notation the board's own language writes. Every
compound row in all sixteen boards came back correctly closed — `MED___`, `BOK___`,
`TROLL___`, `___VAKT`, `SOL___`, `ÖGON___` — with no stray space anywhere.

**Three the rebase exposed, none of which existed in September.**

- **`gloss.attach` dropped `concept` on the way to publication.** It rebuilds every board
  that ships and listed each `Group` field by hand. Boards would have published fine and the
  index they were meant to fill would have stayed empty for ever. Built with `replace` now.
- **The gloss prompt never mentioned the board's language.** It is the only stage a _player_
  reads, and nothing downstream reads a note, so a Swedish board would have shipped English
  prose under its Swedish rows with no check objecting. Verified end to end for $0.004:
  _"SÄL: Att ta bort prickarna ger sal, ett stort och rymligt rum."_
- **`FirestoreCategories.bank` is the production pool**, so the cross-language guard had to
  land there too and not only in the file adapter.

**One the experiment found in `main`.** `run` asks for one slot at a time and `draw` picks
the device at `date + i`, where `i` is now always 0 — so every board in a run gets the same
device. Right for `nightly`, which proposes competing drafts of one board; wrong for `--all`,
which exists to compare configurations. A four-board sample where every board shares a device
measures the device. `stop_on_accept` already tells the two callers apart, so the offset
follows it.

---

## 7. Cost

| what                        | boards | billed tokens | cost      |
| --------------------------- | ------ | ------------- | --------- |
| two category pools          | —      | 10,525        | $0.04     |
| `en-seed_en-prompt`         | 3      | 115,214       | $0.42     |
| `sv-seed_en-prompt`         | 3      | 130,373       | $0.47     |
| `en-seed_sv-prompt`         | 3      | 150,571       | $0.55     |
| `sv-seed_sv-prompt`         | 3      | 139,704       | $0.51     |
| `sv-seed_sv-prompt` neutral | 4      | 215,128       | $0.78     |
| one gloss, to check the fix | —      | 1,158         | $0.004    |
| **total**                   | **22** |               | **$2.76** |

**Swedish prompting costs about 19% more**: $0.148 a board against $0.177, from a longer
system prompt and more thinking. On a board a night that is under a pound a year.

I am not spending the remaining $1.24. The next experiment worth running is a batch of ten
in the recommended configuration with a Swedish reviewer reading the output, and ten boards
is $1.77 — more than is left, and it wants a human in the loop rather than another number.

---

## 8. Recommendation

**Prompt the inventor in Swedish. Prompt the proposer in Swedish too, but for a different
reason. Then ship a batch of ten past a human.**

1. **`--language sv-native` for the inventor** is the strongest single result here. It is
   what stops the pool being a pool of categories _about Sweden_, and it is the only thing
   that stops the prompt's own worked example calquing into it.
2. **`sv-native` for the proposer** as well — not because the boards are visibly better at
   n=3, but because it makes the proposer's trap notes Swedish, and those notes are the
   evidence the red team and the grader reason from. Keeping the reviewers' own prompts in
   English is deliberate and should stay.
3. **Use the Swedish seed boards.** The arm that won on every soft measure was seeds _and_
   prompt in Swedish. `corpus.load`'s `[:2]` should become `[:3]` or the seed set's length,
   or a third of any seed set anyone writes is silently thrown away.
4. **Seed the category pool generously before the first live night** — §5's attractor set is
   real, and the index only helps once something has shipped.
5. **Then ten boards with a Swedish reader.** `regrade` is free, so the thresholds can be
   refitted afterwards against Swedish evidence without spending again.

Still open from the September report and untouched here: **the tile cannot wrap**, and the
12-character cap goes on quietly deleting Swedish categories at authoring time where nobody
sees it. Nothing in this run changes that analysis — the boards stayed short (mean 5.3
characters) because the prompt tells them to.

---

## 9. What I am unsure about

- **n = 3 an arm.** Only two columns in §3 are outside the noise, and I have said which.
- **The 0% calque rate is the concept index, not the prompt.** §1. And it depends on the
  model writing an honest `concept`; it always did here, but nothing forces it to.
- **The register finding rests on two calls.** Eleven categories each. It is a large effect
  and it reproduced in the boards, but it is two samples.
- **Containment matching misses synonym drift.** "drinking glasses" and "drinking vessels"
  match only because I wrote the shipped concept at the level of the idea. Had I written
  "drinking glass styles", the Swedish translation would have walked straight through. The
  prompt-side half of the mechanism does not have this weakness, which is the half I trust.
- **I am still the only Swedish judge.** The boards read as idiomatic to me and I found only
  small nits — _kikärta_ for _kikärt_, _kustvakt_ where _kustbevakning_ is the Swedish
  institution, ARG in a row glossed as _ursinnig_. That is the same conflict of interest the
  September report flagged, and this time I also wrote the seeds.
- **The grader gave 5/5 to twelve of sixteen boards, including one it then sent to review.**
  A scale that saturates is not grading. That is now the weakest instrument in the pipeline
  and it is not a Swedish problem.
- **The fixed-expression device is still untested**, and the minimal-pair device has been
  tested exactly once, on four boards that all drew it because of a bug.
