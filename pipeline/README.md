# Puzzle pipeline

Offline batch generation for Connectris — the phase 2 sketch in
[DESIGN.md](../DESIGN.md#puzzle-generation-pipeline-phase-2-sketch), built. A strong model
proposes a board, a quorum of deliberately weak ones try to solve it and say what they
think each category was, a red team is paid to break it, and an editor model rates or
repairs what survives. Everything is written to disk; the accept/review/reject call is a
pure function over that record, so thresholds can be re-tuned against old runs for free.

It is a separate Python job on purpose. It runs nightly, it never touches a request path,
and it is the only part of this repo that is allowed to be slow.

## Running it

No credentials needed for the dry run — the mock provider plays every role:

```sh
cd pipeline
uv run --with pydantic python -m connectris_pipeline.cli run --count 6 --provider mock
```

Against real models — Vertex, ADC, nothing to leak:

```sh
gcloud auth application-default login
export GOOGLE_CLOUD_PROJECT=your-project GOOGLE_CLOUD_LOCATION=global

uv run --python 3.12 python -m connectris_pipeline.cli run --count 8
```

| Command                                                             | Does                                                  |
| ------------------------------------------------------------------- | ----------------------------------------------------- |
| `... cli run --count N`                                             | The whole pipeline, into `runs/<timestamp>/`          |
| `... cli regrade runs/<stamp>`                                      | Re-decide a finished run under new thresholds. Free.  |
| `... cli export runs/<stamp>`                                       | Append accepted boards to `src/lib/data/puzzles.json` |
| `... cli check`                                                     | Run the pipeline's rules over the shipped puzzles     |
| `uv run --with pytest --with pytest-asyncio --with pydantic pytest` | Tests, all offline                                    |

## The stages

**1. Propose** — strong model, structured output, **one puzzle per call**. A single call
asked for ten boards spends its attention on the first two and reuses their vocabulary;
independent calls also buy independent retries and cheap parallelism. Each call is handed
a diversity seed (two domains and a wordplay device drawn from rotating lists) and the
words and categories already shipped, and is required to state each category's _trap_:
which of its words looks like it belongs to another row on this board. Twenty calls a
night costs nothing.

**2. Validate** — free, deterministic, and before any solver spends a token. Mirrors
`engine.ts` and the `puzzle data` block in `engine.spec.ts`: five rows of four, twenty
distinct words, nothing over twelve characters. A generated puzzle must never be able to
turn CI red. Dedupe against shipped words and categories lives here too, and it runs
in-batch as well — proposals fold into the corpus as they land, so the fifth board of a
night already knows what the first four used.

**3. Solve** — the weak ensemble, several attempts each. Yields _recovery_: what fraction
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
and where one word is doing the damage, rewrites the board. A revision goes back around
from validation, once; a puzzle that needs three rewrites was a bad idea rather than a bad
draft.

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
quality decides the night — propose, red-team, grade — and a mixed weak ensemble of
`gemini-3.5-flash-lite`, `gemini-3.1-flash-lite` and `gemini-2.5-flash-lite` for solving.
Gemini 3 takes a thinking _level_; 2.5 takes a token _budget_; `ModelSpec` carries both and
sends whichever is set. All of it is overridable in `config.toml` — see
`config.example.toml`, and expect the model names to age faster than anything else here.

`tests/test_request_shape.py` covers the parts of the request that are pure. It is there
because this shape has already moved once.

## The honest caveat

Cheap-model difficulty is not human difficulty, and the mapping is unknown until there is
human data. Until then this is a filter for **broken** puzzles, not a difficulty oracle —
the thresholds in `config.py` are reasoned from the design, not measured. Bootstrap by
logging real runs and fitting model-solve-rate against human-solve-rate once there are a
few dozen puzzles; `regrade` exists so that refit costs nothing.

## Layout

```
connectris_pipeline/spec.py      Puzzle shape and every deterministic rule. Mirrors engine.ts.
connectris_pipeline/schema.py    Structured-output schemas. Field descriptions are prompt.
connectris_pipeline/prompts.py   Prompts, and the seed vocabulary that keeps a batch varied.
connectris_pipeline/llm.py       Provider seam + token ledger. Vertex, via generate_content.
connectris_pipeline/mock.py      A provider that never leaves the machine. Not a stub.
connectris_pipeline/scoring.py   Recovery and legibility.
connectris_pipeline/record.py    The per-candidate record, and `decide`.
connectris_pipeline/pipeline.py  Orchestration, artifacts, regrade.
connectris_pipeline/stages/      One module per stage.
```

`cli.py` is Typer — the options are already typed and the annotations carry their own help,
so there is no second copy of the signature to keep in sync. It is Click underneath.

Adding another model family to the solver ensemble is a new class implementing `LLM`, not
a refactor — Vertex serves Claude as well as Gemini and auth is plain ADC either way.
