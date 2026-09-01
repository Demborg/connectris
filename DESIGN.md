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

**3. A check that clears nothing costs a life. Progress is free.**
Four lives. This is the direct analogue of Connections not charging you for a correct group.
It is self-limiting (you can only clear so many times), and it means the skill that keeps
you alive is exactly the ordering skill the mechanic is built around.

DN's _Dagens fyra_ has no fail state at all — it just counts misses upward — and that is
the main thing it does worse than Connections. Keeping real lives is deliberate.

**4. A check reports how many rows are correct, never which.**
With top-down-only clearing, a failed check would otherwise teach you almost nothing: `0`
locked tells you only that row 1 is wrong. Paired with a tight life budget that is the worst
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
Time and lives remaining are shown when the run ends. Moves and checks are recorded but
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

**Nothing on screen counts upward.** The header carries the wordmark, the lives, and a way
to the rules. That is all. See pin 11 — this is the rule the first playtest bought us, and
it is worth defending against every future addition that wants a corner of the screen.

**The board never resizes.** Five row slots for the whole game. A solved row keeps a full
row's height, and since only leading runs clear, cleared rows are always the topmost ones —
so they convert in place and nothing below them moves. Shrinking solved rows into slim
banners made the whole layout shuffle on every clear, which was the single worst thing about
the first build.

**Colour means category and nothing else.** Selection, buttons, life pips and chrome are all
neutral, so a lit-up row is the only saturated thing on screen. The palette is the tetromino
set — cyan, amber, purple, green, red — darkened toward near-black rather than mixed with
the tile grey, because mixing toward a desaturated blue turns amber to olive.

**One type size.** Every word that fits gets the same size; only words too long for the
column shrink, and only as far as the column demands. A visible ladder of sizes made the
board look accidental.

**The clear rolls top-down.** Tiles within a row light in quick succession and each row
starts well after the one above, so a multi-row clear reads as a wave rolling down the board
rather than one flash. Each tile ends on exactly the colour the solved row uses, so the row
consolidating into a single bar is a swap the eye doesn't catch. Bars in a multi-row clear
land in sequence rather than all on one frame.

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

**A bigger clear hits harder.** Two rows or more gets a Tetris-style callout — DOUBLE,
TRIPLE, CONNECTRIS — in the slack below the well, and the clear glows brighter and lands
heavier as the count goes up. The end card is held back while a callout is on screen: the
winning move is the one clear most worth celebrating, and it's exactly the one the card
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
  against a build that had the shortcut, so this is untested. If it bites, the drag-native
  fix is a long-press on a row to pick the whole row up — a gesture rather than a returning
  column of numbers.
- **Number of lives.** Four is genre muscle memory, not a measured number.
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

**Phase 2 — generated puzzles** (below).

**Phase 3 — accounts and histograms.** Percentile distributions once a puzzle has ~30 plays.

---

## Puzzle generation pipeline (phase 2 sketch)

Offline batch, nightly, one puzzle a day — cost rounds to nothing, and it constrains nothing
about the serving stack.

1. **Generate** — strong model, batches of candidates, with the trap design stated
   explicitly: which word is the decoy and which category it's baiting.
2. **Solve** — an ensemble of deliberately weak models, N attempts each at temperature.
   Yields a solve rate → difficulty proxy. Target a band; 0% and 100% both get pruned.
3. **Name** — solvers state the category they think they found; compare to the true label by
   embedding similarity. This measures _legibility_. A puzzle where solvers find the grouping
   but name it differently is fine; one where nobody can articulate why is unfair, and this
   is the only stage that catches it.
4. **Red-team** — a separate model whose only job is to find an alternative consistent
   partition, or a word that legitimately fits two categories. **This is the critical stage
   and it is not the same as solving.** Ambiguity is the failure mode that makes players
   furious, and a solver that happens to find the intended answer won't surface it.
5. **Dedupe** — against previously shipped words and category concepts.

Auto-accept above thresholds, everything else into a review queue.

Mixing providers in the solver ensemble is a feature — it stops puzzle quality being
overfitted to one model's blind spots.

**The honest caveat:** cheap-model difficulty is not human difficulty, and the mapping is
unknown until there is human data. Until then the pipeline is a filter for _broken_ puzzles,
not a difficulty oracle. Bootstrap by logging real runs and fitting model-solve-rate against
human-solve-rate once there are a few dozen puzzles.

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

**Models: Vertex AI.** Note that Vertex serves Claude as well as Gemini, so "stay
Google-native" does not force a single model family; auth is plain GCP ADC either way.

**Auth: deferred.** A display name in localStorage is enough to compete with family. Google
sign-in when it's needed. Shape the score payload now so a user id can be attached later.
