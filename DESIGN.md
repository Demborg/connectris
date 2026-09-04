# Connectris — design notes

A word-grouping puzzle in the family of NYT _Connections_ and DN's _Dagens fyra_, with one
structural change: **you commit to a full arrangement of the board, and the order of your
rows is part of the answer.**

This file is the running record of what is decided and what is not. Phase 0 exists to find
out whether the mechanics are actually fun, so expect the open questions to move.

---

## The game

Twenty words. Five rows of four. Every row is a category; the order of words _within_ a row
is irrelevant, the order of the _rows_ is not.

You rearrange until you're happy, then hit **Check**.

### Pinned

**1. Full-partition commits, not set selection.**
You don't pick four words and submit them. Every word is always on the board in some row,
so every board state is checkable. A blind check is worthless — a random arrangement hits
any given row with probability 1/1820, and the space is 20!/(4!⁵) ≈ 3×10¹¹ arrangements —
so there is nothing to brute-force.

**2. Check clears from the top down only.**
Only the leading run of correct rows clears. A correct row sitting below a wrong one does
not count. This is the rule that makes the whole thing work: without it, reordering is
decoration and this is just Connections with extra steps. With it, "which of my groups am
I surest about" becomes a separate skill from "what are the groups", and you're betting on
your own confidence ranking every time you check.

It also makes the tetris framing literal — cleared rows light up and lock off the top of the
well.

**3. Every check costs one of six. Clearing several rows in one go is how you keep them.**
_Supersedes the original rule, which charged only for a check that cleared nothing._

The old rule read well — "progress is free" — but it priced the game wrongly. Mis-ordering
your rows cost nothing: a check that cleared one row when it could have cleared three was
free, so the ordering mechanic, which is the entire point of the game, had no price on
getting it wrong. And the DOUBLE/TRIPLE callouts were celebrating something the rules did
not reward. Charging for every check fixes both at once: the order you put your rows in now
decides how many checks the board costs you, and batching is worth real money.

Six is chosen from the floor. See `CHECKS` in `engine.ts` for the arithmetic: clearing one
row at a time takes four checks, so six leaves two spare, and the pressure escalates into
the interesting strategy rather than into a dead run.

DN's _Dagens fyra_ has no fail state at all — it just counts misses upward — and that is
the main thing it does worse than Connections. Keeping a real one is deliberate.

**4. A check reports how many rows are correct, never which.**
With top-down-only clearing, a failed check would otherwise teach you almost nothing: `0`
locked tells you only that row 1 is wrong. Paired with a tight check budget that is the worst
kind of fail state — you lose without learning. Reporting the count fixes the information
starvation while keeping the ordering puzzle fully intact, because it never says _where_.

With five rows the reachable counts are 0, 1, 2, 3 and 5 — four correct forces the fifth.
So a check can come back _"2 rows are right — none of them at the top"_, which is the good
kind of agonising.

**5. Losing must feel like the puzzle beat you, not the interface.**
Everything above is in service of this. If a run ends, it should be because you genuinely
couldn't see the grouping.

**6. Deterministic starting layout.**
The opening arrangement is derived from the puzzle id, so every player starts from a
byte-identical board and a move-count comparison is meaningful. It re-seeds until no row is
accidentally complete, so nobody is handed a free clear.

**7. 4 columns × 5 rows, phone-first.**
Phone is the target by roughly a factor of ten. Four columns in portrait is what fits; a
tall well is what suits the clear-from-the-top framing. The fifth category is a real
difficulty jump rather than a size change — more room for decoys — and it makes generation
meaningfully harder, which pushes the red-team stage of the pipeline from nice-to-have to
load-bearing.

Four columns on a 375px screen is ~70px a tile, so **word length is a hard constraint on
puzzle data, not a style note**: capped at 12 characters and enforced by a unit test. This
will bite if puzzles go Swedish — compound words will blow the tile out.

**8. Scoring axes stay separate, and nothing counts up while you play.**
Time and checks remaining are shown when the run ends. Moves and checks are recorded but
never displayed — see pin 11. Zachtronics' real insight isn't the histograms, it's that
incomparable axes mean there's no single "best" and everyone can be proud of something. A
failed run scores nothing for the day; your parents being able to actually lose is a
feature.

**9. One verb: swap two tiles.**
Drag a word onto another, or tap the two in turn. There is no row-level move and no second
tool to learn. Rows are reordered by moving their contents — four swaps to exchange two
rows, and since nothing is counted, that costs patience rather than score.

**10. Everything is logged from the first prototype.**
Every move and check, with timings, kept locally. Logging means old runs can be retro-scored
against metrics we haven't committed to — which is exactly what saved us when pin 11
removed a metric from the UI.

**11. The game is about finding groups, so nothing on screen may suggest otherwise.**
_Set by the first playtest._ A visible move counter turned it into an optimisation problem:
the tester started playing to minimise moves rather than to find categories, and every added
flourish read as a distraction rather than a reward. So the timer, move counter, check
counter and row-rank column are all gone from play. This is the general rule, not just a
list of deletions: anything that counts upward while you think changes what the game feels
like it is about.

### Feel

The game lives or dies on this, so these are decisions, not styling.

**The row is the unit, and its rank is visible.** Each row still in play sits in its own
frame, spaced further from its neighbours than its four words are from each other — so the
eye reads a row as a thing containing words, not a grid of twenty tiles. The frames fade
from the top down, which says the top row is the one a check reaches first. That tiering is
neutral, never hued: colour on this board means category and is not spent on anything else.
It also uses a linear ramp with a floor rather than a decay, because a bottom row faded to
nothing stops reading as a container at all — which would win the argument about order at
the cost of the one about rows.

The board itself carries no border any more. An outer frame around framed rows just nests
boxes inside boxes, and the rows are the structure now.

**Nothing on screen counts upward.** The header carries the wordmark and a way to the rules;
the goal line under it says what you are trying to do; the check budget sits on the button
that spends it. That is all. See pin 11 — this is the rule the first playtest bought us, and
it is worth defending against every future addition that wants a corner of the screen.

**A check says one thing, and only when it has something to say.** The count of correct rows
is the single piece of information the board cannot show by itself (pin 4), so it is the
only thing written in words — set as a number that matters rather than a status line. That a
row cleared, that the board is solved, that the checks ran out: the clear animation, the
crash and the end card already say all of that, and repeating it in small grey type
undercut them. A check that clears cleanly and leaves nothing else right says nothing at
all.

**The board never resizes.** Five row slots for the whole game. A solved row keeps a full
row's height, and since only leading runs clear, cleared rows are always the topmost ones —
so they convert in place and nothing below them moves. Shrinking solved rows into slim
banners made the whole layout shuffle on every clear, which was the single worst thing about
the first build.

**Colour means category and nothing else.** Selection, buttons, budget pips and chrome are all
neutral, so a lit-up row is the only saturated thing on screen. The palette is the tetromino
set — cyan, amber, purple, green, red — darkened toward near-black rather than mixed with
the tile grey, because mixing toward a desaturated blue turns amber to olive.

**One type size.** Every word that fits gets the same size; only words too long for the
column shrink, and only as far as the column demands. A visible ladder of sizes made the
board look accidental.

**The clear rolls top-down, and only top-down.** A row's four tiles light on one frame:
the wave has one direction, and a left-to-right roll inside each row is a second direction
crossing it. Everything left over is vertical — the tiles are pressed down as the wave
passes, the bar squashes as it forms, the category name drops in from above. Each tile ends
on exactly the colour the solved row uses, so the row consolidating into a single bar is a
swap the eye doesn't catch.

**One row's whole life, then the next.** A row lights, converts into its bar, and names its
category before the row below it lights. The first build lifted every cleared row off first
and then ran a second pass of labels rolling in, which is two waves for one thing the player
did — and the labels arrived long after the moment they were the payoff for. Rows leave the
board as they land, so the row currently lifting is always the top one and the board never
changes height.

**The press causes the wave.** Hitting check sends two light rails up the side of the board
from button height, arriving at the top just as the clear starts rolling down. Without it
the wave simply appeared at the top with no connection to the thing the player touched.
It also buys an anticipation beat before the payoff, which is the oldest trick in animation.

**The wave crashes into the row that stopped it.** When it runs out of correct rows it slams
into the first row that isn't one — which is, by definition, the row the player got wrong.
The impact squashes that row and the shock travels further down at a decaying amplitude.
This is not decoration: the crash _is_ the feedback, pointing at where the run broke, and
it's information the top-down rule otherwise has to state in words.

**A miss is the same motion, not a different one.** Nothing clearing means row 1 is wrong,
so the wave has no correct rows to travel through and slams straight into it — the
degenerate case where the run has length zero, and the crash still lands on the row that
stopped it. There is one impact vocabulary rather than a clear animation plus an unrelated
board shake. Only two things separate them: the impact flashes red instead of neutral, and
a miss rings much further down the stack, because a clear is absorbed by the rows that took
it and a miss was absorbed by nothing.

**The callout counts up as the wave rolls.** Two rows or more gets a Tetris-style callout
in the slack below the well, and it is a running tally rather than a final figure: the
second row landing says DOUBLE, the third rolls it over to TRIPLE, and a five-row clear
climbs the whole ladder to CONNECTRIS. Announcing the total once at the end throws away the
best part — the count still going up while you watch. Each word arrives from below and
shoves the last one out of the top, because a crossfade in place reads as a correction
rather than a tally.

**Each rung is louder than the last.** Size, weight and tracking all escalate, and
CONNECTRIS — the whole board in one check — is painted in the tetromino palette sweeping
across the letters, the only place on screen where all five category colours appear at once,
because it is the only moment that has all five rows. The clear also glows brighter and
lands heavier as the count goes up. The end card is held back while a callout is on screen:
the winning move is the one clear most worth celebrating, and it's exactly the one the card
would otherwise cover.

### Deliberately dropped

- **Shuffle.** Cut entirely.
- **Pinning rows.** It mostly existed to protect rows from shuffles. Without shuffle it
  solves a problem we no longer have, and every extra verb costs snappiness. If accidental
  drags turn out to annoy, that's a hit-target problem, not a new mechanic.
- **"One away" feedback.** Far too strong here — with full-partition commits it would
  effectively point at the row to attack. The count in pin 4 is the calibrated version.
- **The rank column.** It numbered the rows down the left edge and doubled as the handle
  for swapping whole rows. The numbers were redundant — the top row is visibly the top row
  — and the handle was a second verb for a rare action. Both went in the declutter.
- **On-screen counters.** Timer, moves, checks. All still logged. See pin 11.

Un-dropped: **drag and drop**, which was deferred as an enhancement and turned out to be
the thing that lets the tap-and-rank scaffolding go away. Tap-to-swap is kept alongside it —
it costs nothing, and it is what keeps the board reachable from a keyboard.

### Open

- **Language.** English dummy data for now. Swedish is likely (see the word-length note, and
  expect noticeably weaker LLM generation for Swedish idiom and wordplay — human review
  stays in the loop longer).
- **Is four swaps too much friction to promote a row?** Reordering rows by confidence is the
  core mechanic, and it now costs four swaps rather than one move. The first playtest was
  against a build that had the shortcut, so this is untested — and pin 3 raised the stakes:
  now that every check is paid for, getting the order right before checking is worth real
  money, so players will want to reorder more often than they did. If it bites, the
  drag-native fix is a long-press on a row to pick the whole row up — a gesture rather than
  a returning column of numbers.
- **Size of the check budget.** Six is reasoned from the four-check floor, not measured. It
  is the single number most likely to need tuning, and it sets how hard the game leans on
  batching: tighter makes multi-row clears essential, looser makes them optional.
- **Is the count feedback too generous?** It's the most reversible of the pinned rules.
- **Grid size.** 4×5 is hardcoded in `engine.ts` as `COLS`/`ROWS`. A 5×5 hard mode is not a
  v1 question but shouldn't be designed out.

---

## Roadmap

**Phase 0 — find the fun** _(where we are)_
Static SvelteKit app, hand-written puzzles in JSON, no backend, no accounts, full local
logging. Questions to answer: is top-down clearing tense or frustrating? Does move-counting
add a puzzle or add anxiety? How many checks does a real person take?

The first puzzles are hand-written on purpose — you learn more about what makes a good
category in an hour of writing them than in a week of prompt engineering, and the pipeline
needs a target to be judged against.

**Phase 1 — real play**
Server-side puzzle delivery and check validation, shared leaderboard, share a link to
family. The client must never hold the answer key, or the leaderboard is decorative;
retrofitting this later means reworking the state model.

**Phase 2 — generated puzzles** _(pipeline built, unproven)_. Below, and in `pipeline/`.

**Phase 3 — accounts and histograms.** Percentile distributions once a puzzle has ~30 plays.

---

## Puzzle generation pipeline

Offline batch, nightly, one puzzle a day — cost rounds to nothing, and it constrains nothing
about the serving stack. Built as a separate Python job in `pipeline/`; that README is the
operational detail, this is what was decided and why.

1. **Propose** — strong model, structured output, with the trap design stated explicitly:
   which word is the decoy and which category it's baiting.
2. **Validate** — deterministic, free, and before a single solver token. Mirrors `engine.ts`
   and the `puzzle data` block in `engine.spec.ts`, plus dedupe against shipped words and
   category concepts.
3. **Solve** — one deliberately weak model. Yields a solve rate → difficulty proxy.
4. **Name** — the solver states the category it thinks it found; compare to the true label.
   This measures _legibility_. A puzzle where the grouping is found but named differently is
   fine; one where nobody can articulate why is unfair, and this is the only stage that
   catches it.
5. **Red-team** — a separate model whose only job is to find an alternative consistent
   partition. **This is the critical stage and it is not the same as solving.** Ambiguity is
   the failure mode that makes players furious, and a solver that happens to find the
   intended answer won't surface it.
6. **Grade** — the only stage that sees the board, the traps, the solver evidence and the
   red-team report at once. Rates, and says what is wrong.

Auto-accept above thresholds, everything else into a review queue.

Mixing providers in the solver ensemble is a feature — it stops puzzle quality being
overfitted to one model's blind spots.

### Decided while building it

**One puzzle per call, not a batch.** A call asked for ten boards spends its attention on
the first two and then reuses their vocabulary. Independent calls also buy independent
retries and cheap parallelism, and the cost of twenty calls a night is not a number worth
optimising. Variety comes from the input instead: each call draws two domains and a
wordplay device from rotating lists, which is a more reliable diversity lever than asking
a model to be varied.

**Temperature is left alone.** The original sketch said "N attempts each at temperature".
Gemini 3's guidance is to keep temperature at its default of 1.0, because below that the
models loop and degrade on exactly the kind of reasoning this stage measures. The board is
still shuffled before the solver sees it, so recovery measures the puzzle rather than the
proposer's formatting.

**Dedupe runs during proposal, not after it.** Each board folds into the corpus as it
lands, so the fifth proposal of a night knows what the first four used. Deduping a
finished batch tells you about a collision when there is nothing left to do about it.

**The accept/review/reject call is a pure function over a stored record.** Every stage
writes what it learned to disk and nothing decides anything until the end, so thresholds
can be re-tuned and old runs re-decided for free — which is exactly what the honest caveat
below says will be needed. This is pin 10 applied to the pipeline rather than to play.

**Low recovery never rejects on its own.** Hard and broken look identical from the solve
stage, and the red team is the tiebreaker. The review queue exists precisely so that this
ambiguity does not have to be resolved by a threshold.

**There is a mock provider that plays every role.** The whole pipeline runs end to end
with no credentials, which is what makes the orchestration testable and lets thresholds be
exercised against a known answer key. It is a fixture, not a puzzle designer.

**The honest caveat:** cheap-model difficulty is not human difficulty, and the mapping is
unknown until there is human data. Until then the pipeline is a filter for _broken_ puzzles,
not a difficulty oracle, and every threshold in it is reasoned rather than measured.
Bootstrap by logging real runs and fitting model-solve-rate against human-solve-rate once
there are a few dozen puzzles.

### What the first real run changed

_20 candidates, 306 calls, $4.15, 2 boards at hand-written quality._

**The evidence stages earn their place as grader input, not as gates.** Of seven
thresholds, four never changed a verdict across 20 candidates — the grader had already
decided, and its rejections were specific and correct. So solver recovery, legibility and
the red-team report all still run and all still reach the grader as prose, and only three
thresholds survive. The one that matters most is the one the grader structurally cannot
supply: a board can read as elegant and still be trivial, because the grader never sees it
played.

**A decoy is not an ambiguity, and the red team had to be told so.** All 37 of its
findings were traps the proposer had declared in its own prompt — handed the trap list, it
handed it back. Since the construction rules require a decoy per category, the stage was
taxing exactly the boards that followed the brief, and the only two boards that would have
auto-accepted got there by having traps it happened to miss. The full-partition rule is
what resolves an ordinary decoy; the red team now has to show that resolution failing.

**Nine solver calls a board bought nothing that one call did not.** Three models
correlating 0.71–0.85 is a capability ladder, not independent blind spots.

**Embeddings lost to token overlap.** 344 calls, no decisions changed, and the free
version was stricter and more accurate — the embedder charged 0.13 cosine for a
capitalisation change, wider than the band being cut.

**The grader would not repair its own boards.** The revision loop fired 6 times in 20, cost
22% of the batch, and the grader rejected its own rewrite in 4 of those 6. Proposing fresh
is one call; re-evaluating a rewrite is three.

### Open

- **Whether the three surviving thresholds are anywhere near right.** They are reasoned,
  not fitted, and no human has played a generated board yet.
- **Whether the single solver is weak enough.** If it solves everything the difficulty
  proxy is measuring nothing; if it solves nothing the grader is carrying the pipeline
  alone.
- **Whether the sharpened red team finds anything at all.** It found zero alternative
  partitions in 20 boards — the stage this document calls critical has not yet fired. That
  may be 20 being too few for a rare-but-fatal event, or it may be the stage not working.
  Re-check at n=100 before trusting either reading.
- **Cost per shippable puzzle.** At a 10% hit rate and $4 a run, that is roughly $40 of
  thinking tokens per board worth keeping. Fine for one a day; worth knowing.
- **Swedish.** The word-length cap will bite on compounds, and LLM generation for Swedish
  idiom and wordplay is expected to be noticeably weaker — human review stays in the loop
  longer.

---

## Stack

**Frontend: SvelteKit 5 + Vite + pnpm.** Not just taste — `animate:flip` gives correct,
interruptible reorder animations for free, and reorder animation is most of the feel here.

**Backend (phase 1): SvelteKit server routes on Cloud Run.** It's about five endpoints. A
separate service buys a deploy unit, a CORS config and duplicated types in exchange for
nothing. The generation pipeline is a separate Python batch job (Cloud Run Job + Cloud
Scheduler) because that's where the tooling lives and it's offline anyway.

**Database: Postgres.** The whole app is leaderboards, and "rank me among N, show the
distribution" is window functions — exactly what Firestore is bad at. Also wanted for
analysing pipeline output.

**Models: Vertex AI**, and only Vertex. The pipeline runs as a Cloud Run Job in the same
project, so ADC is already there and there is no key to manage; supporting AI Studio
alongside it bought a second code path for a second set of failure modes, and was cut.
Generation goes through `models.generate_content` — Vertex's newer Interactions endpoint
answers `Unsupported model interaction` for every Gemini model, so the legacy surface is
the only one actually available there. Note that Vertex serves Claude as well as Gemini,
so "stay Google-native" does not force a single model family, and mixing families in the
solver ensemble is a feature rather than a compromise.

Model names are the fastest-ageing thing in this repo and live in config, not in code. The
generation split matters more than the names: Gemini 3 takes a thinking _level_ and wants
temperature left alone, 2.5 takes a token _budget_ and does not.

**Auth: deferred.** A display name in localStorage is enough to compete with family. Google
sign-in when it's needed. Shape the score payload now so a user id can be attached later.
