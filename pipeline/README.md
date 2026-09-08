# Puzzle pipeline

Offline batch generation for Connectris — the phase 2 sketch in
[DESIGN.md](../DESIGN.md#puzzle-generation-pipeline-phase-2-sketch), built. A strong model
proposes a board, a quorum of deliberately weak ones try to solve it and say what they
think each category was, a red team is paid to break it, an editor model rates or
repairs what survives, and the board that is accepted gets the notes a player reads under
each solved row. Everything is written to disk; the accept/review/reject call is a
pure function over that record, so thresholds can be re-tuned against old runs for free.

It is a separate Python job on purpose. It runs nightly, it never touches a request path,
and it is the only part of this repo that is allowed to be slow.

## Running it

Vertex, ADC, nothing to leak:

```sh
gcloud auth application-default login
export GOOGLE_CLOUD_PROJECT=your-project GOOGLE_CLOUD_LOCATION=global

uv run --python 3.12 python -m connectris_pipeline.cli nightly
```

| Command                              | Does                                                     |
| ------------------------------------ | -------------------------------------------------------- |
| `... cli nightly`                    | The scheduled job: gate, generate, publish one board     |
| `... cli run --count N`              | The generator alone, into `runs/<timestamp>/`. No writes |
| `... cli run --count N --all`        | Same, but without stopping at the first accept           |
| `... cli regrade runs/<stamp>`       | Re-decide a finished run under new thresholds. Free.     |
| `... cli export runs/<stamp>`        | Append accepted boards to `src/lib/data/puzzles.json`    |
| `... cli gloss [--published]`        | Backfill the notes under solved rows. One-off, by hand   |
| `... cli check`                      | Run the pipeline's rules over the shipped puzzles        |
| `uv run --locked --extra dev pytest` | Tests, all offline                                       |

## One night

`nightly` is the whole job, and most of what it does is decide not to spend anything.

```
                                 no ─── nothing to do, $0
tomorrow already written? ──────┤
                                 yes
                                  ↓
                                 no ─── nobody is playing, $0
anyone finished today's board? ──┤
                                 yes
                                  ↓
     propose → validate → solve → red-team → grade → decide
                                  ↓
                        accepted? ─── no ── try again, up to `--count` times
                                  ↓ yes
                                gloss ─── the notes under each solved row
                                  ↓
                        publish for tomorrow, stop
```

**Gloss is last, and after the accept.** It writes the reference note a player reads once
a row is on the table — what the category was, what each word is — and it runs on the one
board that is shipping rather than on all of them, because 45% of candidates are thrown
away and explaining those is paying to annotate puzzles nobody will see. It is also the
only stage that is allowed to fail without costing the night: a board with no notes is the
board this game shipped for its first weeks, and a day with no puzzle on it is worse.

Boards published before the stage existed have no notes and their rows do not open.
`cli gloss` buys them — over `puzzles.json` by default, over the game's database with
`--published`, and `--limit` is there to buy a few and read them before buying the rest.

**The demand gate is the point.** A night costs about $0.33 and this game may have nobody
playing it. The signal is a _finished run_ — the client posts one from `finish()` and
nowhere else, so a record is a player who saw a board through to a win or a loss — against
the board that is currently live, within the last 36 hours. That window is what makes the
job safe to leave running: "has this board ever been played" is true forever once it is
true once, and a generator gated on that would keep billing a project whose last player
left in March.

Run it late in the evening and it publishes for tomorrow, which is what makes the gate
fair: the board it measures has had most of a day in front of whoever was going to play
it, and the board it writes does not go up for another couple of hours.

**The ceiling is a reliability knob, not a cost one.** `--count` is how many boards it may
propose, not how many it will: generation stops at the first accepted board. At the
measured acceptance rate a ceiling of five costs about 1.8 candidates and lands a board on
98% of nights, where proposing five every night would cost 5.0 for the same 98%.

**A night that accepts nothing publishes nothing, and is not retried.** The board that is
up stays up — a day repeated is a smaller failure than a day missing, and a retry would
only spend the same money on the same bad idea. `nightly` exits 0 for both of the outcomes
that publish nothing, so a non-zero exit really is something broken.

## Deploying it

The job image is built and deployed by `.github/workflows/deploy-pipeline.yml` on any push
that touches `pipeline/`. **Deploying it does not start it** — a Cloud Run Job that is
never executed costs nothing, and starting a nightly bill should be something a person
does on purpose:

```sh
# One-time, and before the deploy workflow first runs, or it is red: the identity the job
# runs as, and the deploying account's permission to act as it.
GEN=connectris-generator@connectris-507519.iam.gserviceaccount.com
gcloud iam service-accounts create connectris-generator --project=connectris-507519
for role in roles/datastore.user roles/aiplatform.user; do
  gcloud projects add-iam-policy-binding connectris-507519 \
    --member="serviceAccount:$GEN" --role=$role
done
gcloud iam service-accounts add-iam-policy-binding "$GEN" \
  --member=serviceAccount:connectris-deploy@connectris-507519.iam.gserviceaccount.com \
  --role=roles/iam.serviceAccountUser --project=connectris-507519

# Required once, and before deploying the game: boards are now found by `liveOn <= today`,
# and Firestore range filters skip documents that do not have the field at all. Every board
# already in the collection was written with an `order` and no date, so until this is run
# the query matches nothing and the game answers 503. `set` replaces the document, so this
# also clears the `order` field it is replacing.
GOOGLE_CLOUD_PROJECT=connectris-507519 node scripts/seed.mjs --dry-run   # read it first
GOOGLE_CLOUD_PROJECT=connectris-507519 node scripts/seed.mjs

# Try it once, by hand, and read what it decided before trusting it with a schedule.
gcloud run jobs execute connectris-generator --region=europe-north1 --wait

# Then, and only then, turn it on. 22:00 UTC: today's board has had most of a day, and
# what this writes goes live at midnight.
#
# `europe-west1`, not the job's own `europe-north1` — Cloud Scheduler is not offered
# there. It only makes an HTTPS call to the Run Admin API, so where it runs from is
# independent of where the job runs.
# One schedule per language, and one board a night from each. Two jobs rather than a loop
# inside one: a night that fails for Swedish must not take English's board down with it,
# and two jobs are two lines in the log and two bills that can be read apart. Ten minutes
# apart so they do not contend for the same quota.
for lang in en sv-native; do
  gcloud scheduler jobs create http connectris-nightly-$lang \
    --location=europe-west1 --time-zone=UTC \
    --schedule="$([ $lang = en ] && echo '0 22 * * *' || echo '10 22 * * *')" \
    --uri="https://europe-north1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/connectris-507519/jobs/connectris-generator:run" \
    --http-method=POST \
    --message-body="{\"overrides\":{\"containerOverrides\":[{\"args\":[\"nightly\",\"--language\",\"$lang\"]}]}}" \
    --headers=Content-Type=application/json \
    --oauth-service-account-email=connectris-deploy@connectris-507519.iam.gserviceaccount.com
done

# And to stop either, at any time, without deleting anything:
gcloud scheduler jobs pause connectris-nightly-sv-native --location=europe-west1
```

`sv-native`, not `sv`: the language a _board_ is written in is Swedish either way — the
difference is that the authoring prompts are themselves in Swedish, which is what
[../docs/swedish-prompting.md](../docs/swedish-prompting.md) recommends and what keeps the
category pool from filling up with categories about Sweden rather than categories in
Swedish. Boards it writes are stamped `sv` and are indistinguishable to the game.

Swedish starts with nothing published, so the first Swedish night has no demand to measure
and is allowed through unconditionally — the gate is per language, and a language with no
live board can always start. Until that first night lands, `/sv` says so rather than
erroring.

`--task-timeout=45m` is sized for the ceiling, not the average. A candidate takes about
five minutes end to end and `propose` is three and a half of them — the same stage that is
two thirds of the bill is three quarters of the wall clock — so a typical night is five to
ten minutes and a night that proposes five boards and accepts none is about twenty-five.

The run directory is written inside the container and dies with the task, so `nightly`
prints its ledger to stdout, where Cloud Logging keeps it for a month for nothing, and
logs the accepted board in full just before writing it. Those two lines are the only
record that survives the task: one of what the night cost, one that makes a board
recoverable by hand if the publish itself is what failed.

## The stages

**1. Propose** — strong model, structured output, **one puzzle per call**. A single call
asked for ten boards spends its attention on the first two and reuses their vocabulary;
independent calls also buy independent retries and cheap parallelism. Each call is handed
a diversity seed (two domains and a wordplay device drawn from rotating lists) and the
words and categories already shipped, and is required to state each category's _trap_:
which of its words looks like it belongs to another row on this board. It is also two
thirds of what a board costs, which is why the generator stops as soon as one is good
enough: the only saving of any size available here is a proposal not made.

**2. Validate** — free, deterministic, and before any solver spends a token. Mirrors
`engine.ts` and the `puzzle data` block in `engine.spec.ts`: five rows of four, twenty
distinct words, nothing over twelve characters. A generated puzzle must never be able to
turn CI red. Dedupe against published words and categories lives here too, and it runs
in-batch as well — candidates are proposed one at a time and each folds into the corpus
as it lands, so a second draft cannot repeat the first.

**3. Solve** — one deliberately weak model, three attempts. Yields _recovery_: what fraction
of attempts reproduced each intended four exactly. Both ends of the band get pruned,
because 0% and 100% are both "not a puzzle". The solver prompt is deliberately bare — no
rules, no traps, no mention that the words were constructed — because every extra sentence
makes it a better player than the ones we are calibrating for.

Attempts differ by **seed and board order, not temperature**. Gemini 3's guidance is to
leave temperature at its default: below 1.0 the models loop and degrade on exactly the kind
of reasoning being measured here. So each attempt carries its own `seed` and its own
shuffle of the twenty words — which is the better lever anyway, because it varies the input
rather than the sampler, and a category only counts as recovered if it survives being
presented in a different order.

**4. Legibility** — solvers name the category they think they found; that name is compared
to the true label. A board where solvers find the grouping but name it differently is
fine. One where nobody can articulate why is unfair, and this is the only stage that
catches it. Embeddings when there's an endpoint, token overlap when there isn't — the
fallback is a floor, not a measurement, so it sends fair puzzles to review rather than
rejecting them.

**5. Red team** — the critical stage, and not the same job as solving. A solver that
happens to find the intended answer proves nothing about whether a _second_ answer exists,
and ambiguity is the failure mode that makes players furious. This model is shown the
answer key and paid to break it: a whole alternative partition is fatal, a single
double-filed word blocks auto-accept.

**6. Grade** — the only stage that sees everything at once. Rates fairness and elegance,
and says so. There was a revision loop here — a grader that wanted one word changed handed
back a rewritten board, which went round again from validation — and a real run retired
it: it fired on 6 candidates in 20, cost 22% of the batch's calls, and the grader rejected
its own rewrite in 4 of those 6. Proposing a fresh board is one call and re-evaluating a
rewrite is three, so a grader that wants a revision now just says so and the board goes to
review.

**7. Decide** — `record.decide`, a pure function over the stored record. The bar for
_reject_ is evidence the puzzle is wrong; the bar for _accept_ is evidence it is right;
everything else is a human's problem, which is the point of having a queue rather than a
second threshold. Nothing that landed low on recovery is rejected on that alone — hard and
broken look identical from there, and the red team is the tiebreaker.

## What a run leaves behind

```
runs/<timestamp>/
  config.json       exactly the knobs this run used
  candidates.jsonl  one record per board: proposal, traps, every solver attempt, scores,
                    red-team report, grade, decision
  accepted.json     ready for `export`
  reviewed.json     the queue
  ledger.json       calls and tokens, by model and by stage
  summary.txt       what you'd want printed
```

Tokens rather than money: prices move, tokens don't. Thinking tokens are counted
separately because they are billed as output and are the reason a "cheap" stage isn't.

## Models and API surface

**Vertex only, one transport.** Vertex's Interactions endpoint rejects every Gemini model
with `Unsupported model interaction`, so generation goes through `models.generate_content`
— the older surface, but the one Vertex actually serves. Supporting AI Studio alongside it
bought a second code path for a second set of failure modes and was cut. Structured output
is a Pydantic class handed to `response_schema` and parsed back by the SDK; the schemas in
`schema.py` are the contract, and their `Field(description=...)` text ships to the model as
part of that schema.

Defaults are `gemini-3.8-flash` at `thinking_level: "high"` for the three jobs where
quality decides the night — propose, red-team, grade — and `gemini-3.1-flash-lite` at
`low` for solving.
Gemini 3 takes a thinking _level_; 2.5 takes a token _budget_; `ModelSpec` carries both and
sends whichever is set. All of it is overridable in `config.toml` — see
`config.example.toml`, and expect the model names to age faster than anything else here.

`tests/test_request_shape.py` covers the parts of the request that are pure. It is there
because this shape has already moved once.

## What it costs

[docs/generation-cost.md](../docs/generation-cost.md) is the ledger-by-ledger account.
The short version, measured across 26 candidates and then across consecutive simulated
nights of the shape that ships today:

- **A candidate is $0.18**, of which `propose` is 69%, `red_team` 22%, `grade` 8% and
  `solve` under 1%. Thinking tokens are 96% of it; every input token in a run is under 2%.
  The stage everyone guesses is expensive is the cheap one.
- **A night is one to two candidates**, because generation stops at the first accept.
- **A night nobody played is $0**, because the gate runs before the first token.

The three-stage split is why `red_team` stays at `high` and is not a candidate for
economising: over 26 candidates it found 2 complete alternative partitions and 10 words
that two labels both admit, including one the grader had waved through as "change one
word". It is 22% of the bill and it is the only stage that catches the failure this
pipeline exists to prevent.

**The honest caveat still stands:** cheap-model difficulty is not human difficulty, and the
mapping is unknown until there is human data. This is a filter for **broken** puzzles, not
a difficulty oracle, and the three surviving thresholds are still reasoned rather than
fitted. Bootstrap by logging real runs and fitting model-solve-rate against human-solve-rate
once there are a few dozen puzzles; `regrade` exists so that refit costs nothing — it has
already paid for itself once, recovering a whole counterfactual verdict distribution for
zero tokens after a bug was found.

## Layout

```
connectris_pipeline/spec.py      Puzzle shape and every deterministic rule. Mirrors engine.ts.
connectris_pipeline/schema.py    Structured-output schemas. Field descriptions are prompt.
connectris_pipeline/prompts.py   Prompts, and the seed vocabulary that keeps a batch varied.
connectris_pipeline/llm.py       Provider seam + token ledger. Vertex, via generate_content.
connectris_pipeline/scoring.py   Recovery and legibility.
connectris_pipeline/record.py    The per-candidate record, and `decide`.
connectris_pipeline/pipeline.py  The generator: propose, evaluate, stop at the first accept.
connectris_pipeline/nightly.py   The gate, and the night around it. Where money is decided.
connectris_pipeline/store.py     The game's database, as the generator sees it. Two adapters.
connectris_pipeline/day.py       Days as `YYYY-MM-DD`. The Python half of server/day.ts.
connectris_pipeline/stages/      One module per stage.
tests/conftest.py                A scripted stand-in for the model. Not a simulator.
```

`cli.py` is Typer — the options are already typed and the annotations carry their own help,
so there is no second copy of the signature to keep in sync. It is Click underneath.

Adding another model family is a new class implementing `LLM`, not a refactor — Vertex
serves Claude as well as Gemini and auth is plain ADC either way. That protocol is worth
having only because it is checked: `tests/test_request_shape.py` asserts both
implementations satisfy it, so a drifting signature fails CI.
