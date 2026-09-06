# What the puzzle pipeline costs

Measured from the three run ledgers in `pipeline/runs/`, plus two 3-candidate experiments
bought for this document ($0.70 of a $1 budget). Prices are Vertex list, September 2026:
`gemini-3.8-flash` $0.75/$3.75 per million in/out, `gemini-3.1-flash-lite` $0.25/$1.50.
Thinking tokens bill as output. **These are introductory rates; 3.8 Flash goes to
$1.50/$7.50 on 1 January 2027, so every number below doubles that day.**

The prices check out against the ledger: run `20260904-053959`'s 3.8-flash tokens come to
$4.151 at those rates, which is the $4.15 the README quotes, to the cent.

## Where the money goes

The two runs that used the current pipeline shape — `20260904-153114` and
`20260905-054612`, 20 candidates between them, `invent` excluded — cost **$3.64**.

| Stage      | Model               | Calls | Thinking/call |  $/call |     $ |     % |
| ---------- | ------------------- | ----: | ------------: | ------: | ----: | ----: |
| `propose`  | 3.8-flash, high     |    20 |        32,702 | $0.1251 | $2.50 | 68.8% |
| `red_team` | 3.8-flash, high     |    20 |        10,480 | $0.0407 | $0.81 | 22.4% |
| `grade`    | 3.8-flash, high     |    20 |         3,511 | $0.0146 | $0.29 |  8.0% |
| `solve`    | 3.1-flash-lite, low |    40 |           196 | $0.0007 | $0.03 |  0.8% |

**$0.182 per candidate.** Thinking tokens on 3.8-flash are 96% of the bill. Every input
token in both runs, all four stages together, is $0.071 — **under 2%**.

Three things follow immediately, and two of them close questions this repo has left open:

**The README's cost-per-board is six times too high.** The "2 boards per 20 at $4.15,
about $2 a board" line describes run `20260904-053959`, a configuration that no longer
exists: three solver models at three attempts each, an embedding stage, a revision loop,
and the corpus-staleness bug that flagged all 20 boards as recycled and drove the grader
to reject 13 of them. It accepted nothing. On the shape that ships today, those 20
candidates produced **11 accepts, 6 reviews, 3 rejects** — 55% acceptance, and
**$0.33 per accepted board.**

**Cost is not concentrated in a tail.** `propose` thinking runs 17,580–49,038 tokens
across the 20 calls, p25 25,556 and p75 39,666. The most expensive single call in the
entire corpus is $0.18, which is 5% of a ten-candidate run. There is no outlier candidate
to kill early; the bill is twenty flat `propose` calls.

**Nothing dies at `validate`.** Zero of 50 candidates across all three runs hit a fatal
deterministic problem. So "generate more and cheaper, let the free filter sort it out" has
nothing to filter with — every rejection happens at the expensive end, after the money is
spent. This is the hypothesis I most expected to pay off and it is dead on the evidence.

## Recommendations, ranked

### 1. Run 3 candidates a night, not 20 — measured, ~85%

This is the whole problem, and it is free.

The game ships **one puzzle a day**. At 55% acceptance, 20 candidates a night produce
about 330 shippable boards a month for a game that needs 30. Twenty a night is $3.64 a
night and **$111 a month**; three a night is $0.55 and **$17 a month**, yielding ~1.65
boards a night with slack for the review queue. A weekly run of 12 is the same arithmetic
and less operational surface.

Nothing about how a board is made or filtered changes. The only real cost is optionality:
the pipeline currently _accepts_ rather than _ranks_, so a small batch is only equivalent
while that stays true. If it ever picks the best of N, N goes back up and this saving
goes away.

### 2. `propose` at `thinking_level = "medium"` — measured at n=3, ~14%

`medium` is 3.8 Flash's own default; `high` is an explicit opt-in that has never been
compared against it. Experiment E1 (`runs/20260905-170917`, 3 candidates, seed 1, only the
proposer changed) measured **25,139 thinking tokens per call against 32,702 at high** —
23% off the stage that is 69% of the bill, so 14% off the run. $0.182 → $0.157 a
candidate.

Quality at n=3: 2 accepted clean, 1 rejected — and the reject was the machinery working,
with the red team flagging DUMMY as admitted by two labels and the grader agreeing. That
is three boards. It is a direction, not a result.

### 3. Do not go to `low`. It is a cliff, not a slope — measured, decisive

`thinking_level = "low"` on `gemini-3.8-flash` returns **zero thinking tokens**. It is not
less thinking, it is thinking off. `propose` falls from $0.125 to $0.0029 a call — 43×
cheaper, and by far the largest saving available anywhere in this document.

It is also unshippable. E2 (`runs/20260905-171430`, same seed, same slots, only the
proposer's thinking level changed) accepted **0 of 3**, and all three failed the same way:
JAGUAR and KNIGHT, RIBBONS, and DOVE/SWALLOW/PITCHER each genuinely satisfy two labels on
their board, and one board had a complete alternative partition. That is not "less
elegant". That is exactly the defect this pipeline exists to prevent — the one where a
player is right and is told they are wrong.

The pairing is what makes this readable: E1 and E2 ran the same seed, so both proposers
were handed the same assigned devices and themes. The only difference was reasoning
effort, and the ambiguity check is the first thing that goes when you take it away.

**The corollary is that `red_team` is untouchable.** Over 26 candidates on the sharpened
prompt it has found **2 complete alternative partitions and 10 words that two labels both
admit** — including SWORD/CLOWN in run `20260904-153114`, which the grader saw as "change
one word" and only the red team called fatal. DESIGN.md's open question, "whether the
sharpened red team finds anything at all", is answered: it does, and it is the only stage
that catches the thing it was built to catch. It is 22% of the bill and it stays at high.

### 4. Let the recovery gate short-circuit the expensive stages — measured, 3%

`evaluate` runs solve → red_team → grade unconditionally, but `decide` rejects on
`mean_recovery > 0.80` no matter what those two stages say. `solve` costs $0.0007 and the
two stages after it cost $0.055. Runs 2 and 3 paid that on 2 of 20 candidates: **3.0%**.

Correct, but marginal, and it is not free of consequence: skipping those stages destroys
the record `regrade` would need if `max_mean_recovery` is ever raised, and `regrade`
against stored records is this project's only cheap tuning mechanism. Take it only once
that threshold is considered settled, or put it behind a flag.

### 5. Prompt size — measured, nothing to win, but there is a bug

The proposer's corpus lists are already hard-capped in `prompts.py` at
`sorted(avoid_words)[:200]` and `sorted(avoid_labels)[:80]`. They cannot grow without
bound; a saturated `propose` prompt is about 3k tokens, $0.002. Input is 2% of spend and
that is its ceiling.

The cap is worth a separate fix for a different reason. It truncates _after_ sorting
alphabetically, so the moment the corpus passes 200 words the proposer stops being told
about anything after roughly the letter C, and dedupe degrades silently. Sample, or keep
the most recent, rather than taking the alphabetical head. That is a quality bug wearing a
performance cap's clothes.

### 6. A cheaper proposer — untested

`gemini-3-flash` ($0.50/$3.00) or `gemini-3.1-flash-lite` ($0.25/$1.50) at high thinking
is the one model-choice idea E2 does not already refute. E2 argues the binding constraint
is _reasoning effort spent checking for dual membership_, not model tier — so a lite model
allowed to think hard might still clear the bar, at a third of the output price. It might
also be exactly the trade this document warns against. Untested; ~$0.30 buys a 3-candidate
read and n≈20 buys a real one.

## Revised config

```toml
attempts = 3

[proposer]
name = "gemini-3.8-flash"
thinking_level = "medium"   # was "high" — the model's own default, 23% cheaper

[red_team]
name = "gemini-3.8-flash"
thinking_level = "high"     # do not touch; this is the stage that earns the bill

[grader]
name = "gemini-3.8-flash"
thinking_level = "high"

[solver]
name = "gemini-3.1-flash-lite"
thinking_level = "low"
```

Run it with `--count 3`.

Predicted: $0.0968 propose + $0.0407 red_team + $0.0146 grade + $0.0021 solve =
**$0.154 a candidate**, $0.46 a night, **$14 a month**. At 55% acceptance that is ~1.65
boards a night and **$0.28 per shippable board** — against $111 a month and $0.33 a board
for 20 nightly candidates on today's config, and against the $60 a month the README's
stale numbers imply.

**Confidence.** High on the per-night figure: it is arithmetic over per-call costs
measured across 26 real candidates, and the one changed number was measured directly in
E1. Moderate on the boards-a-night figure, which rests on 55% acceptance holding at
`medium` thinking, where the evidence is three boards. If it does not hold, raise
`--count`; the cost per candidate is the robust number and the yield is the fragile one.

## What this could not settle

**Whether `medium` holds quality at n≥20.** Three boards cannot distinguish a 55%
acceptance rate from a 40% one. The experiment worth buying is two paired 10-candidate
runs on the same seed, one at `medium` and one at `high`, about **$3.40** — one night's
current spend to settle the second-largest lever permanently.

**Whether `red_team` at `medium` is safe.** Deliberately not tested. It is 22% of the bill
and the only stage that catches ambiguity, and E2 showed how quickly ambiguity appears
when reasoning effort is withdrawn. Settling it properly means running both levels over
the _same_ stored boards, which the pipeline cannot do today. A `re-red-team <rundir>`
command — `regrade`'s trick, but re-running one stage against stored candidates instead of
re-deciding from them — would make this and several other questions cost $0.81 instead of
a whole run. That is the highest-value thing to build next.

**Whether 55% acceptance survives a growing corpus.** Both current-shape runs went against
a three-puzzle corpus. Run `20260904-053959` failed for exactly one reason — everything
read as stale — and novelty gets harder every night the game ships. The cost per candidate
is stable; the cost per _shippable_ board is a hostage to a novelty rate nobody has
measured over more than three days. Not testable today, and it is the largest threat to
every per-board number here.

## What was spent writing this

$0.6973, against a $1 budget. Two runs, 36 calls, 36,920 input / 8,276 output / 174,849
thinking tokens.

| Run                                      | Candidates | Calls |       $ |
| ---------------------------------------- | ---------: | ----: | ------: |
| E1 `20260905-170917` — proposer `medium` |          3 |    18 | $0.5082 |
| E2 `20260905-171430` — proposer `low`    |          3 |    18 | $0.1891 |

Everything else in this document came out of ledgers that had already been paid for.

---

# Addendum, 6 September 2026 — what the pipeline shape changed

Everything above still describes the per-candidate economics correctly, and two of its
recommendations have now been superseded by something cheaper. Written after building the
nightly job; the numbers here come from consecutive simulated nights against the shape
that ships, plus the arithmetic that follows from an early exit.

## 1. Stopping at the first accept beats sizing a batch — supersedes recommendation #1

`propose` is 69% of a candidate, and nothing before it is expensive enough to filter with
(recommendation #3 above: nothing dies at `validate`). So the only saving of any size is
**a proposal that never happens** — which a batch cannot do, because it commits to `N`
before it knows whether the first one worked.

Cost per night is `E[candidates] x cost per candidate`. With acceptance `p` and a ceiling
`k`, `E[candidates] = (1 - (1-p)^k) / p`, and the chance of landing a board is `1-(1-p)^k`.
At the measured `p = 0.55` and $0.182 a candidate — the shipped `high` proposer, not the
`medium` one recommendation #2 proposed:

| shape                | E[candidates] | $/night | P(board that night) |
| -------------------- | ------------: | ------: | ------------------: |
| batch of 3 (rec. #1) |          3.00 |  $0.546 |               90.9% |
| early exit, k = 3    |          1.65 |  $0.301 |               90.9% |
| early exit, k = 5    |          1.78 |  $0.325 |               98.2% |
| batch of 5           |          5.00 |  $0.910 |               98.2% |

**45% cheaper for identical yield**, and the second-order effect matters more than the
first: once the night stops early, **the ceiling is a reliability knob rather than a cost
one**. Going from 3 to 5 buys seven points of "there is a puzzle tomorrow" for two cents.
Raise it before you lower it.

The shipped default is `--count 5`.

## 2. It also re-ranks recommendation #2, and not in its favour

Cost per _shipped board_ is `(1/p) x c`. Acceptance multiplies; per-candidate cost only
adds. `medium` measured 23% off `c` at n=3 — but it is only a saving while `p` holds
above

    p_breakeven = 0.55 x (0.157 / 0.182) = **47.4%**

Below that, `medium` costs more per shipped board than `high` does, and the n=3 evidence
for `medium` cannot distinguish 55% from 47%. The doc above called this "a direction, not
a result"; under an early exit the direction could point either way, so the default stays
`high` and the paired experiment it asks for is still the one worth buying. `run --all`
exists so that experiment can still take a fixed-size sample.

## 3. The gate is bigger than any of it

None of the above matters as much as not running. The job now refuses to generate unless a
**finished run** — a win or a loss, the only thing the client ever posts — was recorded
against the board that is currently live, within the last 36 hours. A month nobody plays
is $0.00 rather than $9.75.

The window is the part that took a second attempt to get right. The obvious predicate,
"has anyone played the current board", is true forever once it is true once — so a
generator whose board stopped changing (because it broke, or because nothing was accepted)
would see the same six-month-old run every night and bill for a new board every night. Only
a predicate relative to _now_ actually stops.

## 4. Recommendation #5's bug is fixed; #4 is now not worth doing

The alphabetical truncation is fixed — `prompts.py` now takes an evenly-spaced sample
across the sorted list rather than its first 200 entries, so a corpus past the cap still
tells the proposer about words after the letter C. A board a day reaches 200 words in
under two months, so this was about to start mattering.

Recommendation #4, short-circuiting `solve`'s recovery gate, was worth 3% of a run. Three
per cent of $0.33 is a cent a night, against permanently destroying the record
`regrade` reads. Not worth it, and now clearly so.

## What this cost, and what it measured

**$1.20 against a $4 budget.**

Six consecutive nights, run against a `MemoryStore` seeded with the shipped boards — the
real gate, the real generator, the real models, the real publish step, and each night's
accepted board folded into the next night's corpus. Everything except the database.

| Night | Candidates | Verdicts       | Calls | Thinking |       $ |
| ----- | ---------: | -------------- | ----: | -------: | ------: |
| 1     |          1 | accept         |     6 |   41,180 | $0.1599 |
| 2     |          1 | accept         |     6 |   51,797 | $0.2005 |
| 3     |          1 | accept         |     6 |   33,317 | $0.1309 |
| 4     |          1 | accept         |     6 |   47,267 | $0.1830 |
| 5     |          1 | accept         |     6 |   38,588 | $0.1507 |
| 6     |          2 | review, accept |    12 |   97,191 | $0.3781 |

**$1.2031 for six nights and six boards.** Mean **$0.2005 a night**, **$0.1719 a
candidate**, 1.17 candidates a night. Every night published.

The per-candidate number is the one worth trusting: $0.172 measured against $0.182
predicted from 26 earlier candidates, on a different pipeline shape, a week apart. That
figure is solid.

**The acceptance rate is not.** Six of seven candidates were accepted, against the 55% this
document assumes — but at n=7 the 95% interval on that is roughly 42%–98%, which contains
55% comfortably. It is not evidence that acceptance improved. What it does mean is that
$0.20 a night is a *lucky* six nights and $0.33 remains the number to budget against; at
$0.20 a month is $6, at $0.33 it is $9.75, and both are inside the noise of what the
project costs anyway.

Night 6 is the one worth reading. Its first board put DRUM in _Percussion instruments_ and
in _Verbs meaning to strike repeatedly_ — a word two labels both admit, which is the exact
defect the red team exists to catch and did. The grader agreed, added that tightening the
label to "heavy or violent blows" would fix it, and the night went on to propose a second
board and accept it. That is the whole design working end to end: caught, not shipped, not
thrown away either — the reviewable board goes into the log with the fix attached.

**And a bug fell out of it.** Nights 1 and 2 were run in separate processes that happened
to share seed 0, and both drew the same wordplay device. That is the device selection being
a shuffle whose front a one-candidate night never gets past — reasoned about above, and
then observed by accident. Devices now walk their seven-item cycle from the date's ordinal,
so a week gets all seven.

## What is still open

**Whether acceptance holds at `medium`.** Unchanged from above, and now with a sharper
number to beat: 47.4%.

**Whether acceptance survives a growing corpus.** Still the largest threat to every
per-board figure here, and still not settled — but it is now measurable for free, because
every night writes a ledger and a verdict, and the corpus grows by one real board a day.
Come back to this after a month of it.

**Theme variety over a year.** The category pool tops itself up only when it has fewer
categories than the ceiling — which, once the first `invent` call has banked forty, never
happens again. Forty themes on strict least-recently-used rotation means a theme returns
about every forty nights, and the 60-board cooldown that was meant to hold it back longer
cannot, because the pool is smaller than the cooldown. Wordplay _devices_ are fine — those
now walk their seven-item cycle by date, so a week gets all seven — but the subjects will
start to feel familiar before the words do. The fix is to top up against a floor above the
cooldown rather than above the ceiling; it costs an `invent` call now and then, and it has
not been done because a top-up that keeps failing to find new ideas would be a slow leak
of exactly the kind this document is about.
