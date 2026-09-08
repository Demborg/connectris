# Connectris

A word-grouping puzzle where **the order of your rows is part of the answer**.

Twenty words, five rows of four. Every row is a category. Hit _Check_ and only the leading
run of correct rows clears — a correct row sitting below a wrong one doesn't count. So you
rank your rows by how sure you are, and bet. Clearing rows light up in a wave rolling down
the board and lock in place. Every check spends one of four, so getting the order right —
and clearing several rows at once — is what keeps them.

When a row clears it names its category, and tapping it opens the rest: one sentence on
what the category was, and one line per word. Everybody who played a board went and
searched for it afterwards, so the search is answered in place.

**Play it:** https://connectris-214765692756.europe-north1.run.app

A SvelteKit app on Cloud Run backed by Firestore, serving a board a day from a generator
that writes them nightly. The client never holds the answer key — it gets twenty words, and
every check is graded by the server. Runs and a two-question survey are recorded, because
the point of this phase is to find out how real people play.

Everyone picks a name before their first board. It is not an account — no password, no
email — but it is server-side: the id is minted on registration and kept in an httpOnly
cookie, so a run, an opinion and a place in the standings all belong to the same someone.
Which boards you have solved and where you stand come from the database rather than from
the browser, so they say the same thing on your phone as on your laptop. The reasoning
behind every rule, what is deliberately dropped, what is still undecided, and where this is
going next is in **[DESIGN.md](./DESIGN.md)**.

## Running it

```sh
pnpm install
pnpm dev
```

With no `GOOGLE_CLOUD_PROJECT` set, the app runs entirely on itself: boards come from
`src/lib/data/puzzles.json` on a schedule derived from today, and players, runs, progress
and survey answers are written as JSON files under `.data/`. No cloud project, no emulator,
no network. Registering on a dev server is real — delete `.data/players` and `.data/handles`
to start over.

| Command       | Does                                           |
| ------------- | ---------------------------------------------- |
| `pnpm dev`    | Dev server (`--host` to reach it from a phone) |
| `pnpm test`   | Unit tests                                     |
| `pnpm check`  | Type check                                     |
| `pnpm lint`   | Prettier + ESLint                              |
| `pnpm format` | Fix formatting                                 |
| `pnpm build`  | Server build into `build/`                     |

To run against the real database instead, set `GOOGLE_CLOUD_PROJECT=connectris-507519`
and have ADC (`gcloud auth application-default login`).

## Layout

```
src/lib/game/engine.ts          Pure rules: dealing, checking, moves. Client and server.
src/lib/game/checker.ts         Grading, local or over the wire. The answer key's seam.
src/lib/game/session.svelte.ts  Runtime state for one run — budget, verdict, animation beats.
src/lib/game/log.ts             Local play log — kept so a run that failed to post is not lost.
src/lib/alias.ts                What a player may call themselves, and how names compare.
src/lib/server/ports.ts         What the game needs from outside. Five ports.
src/lib/server/{memory,json,firestore}.ts   Three adapters answering to one contract.
src/lib/server/identity.ts      Registration, and who a request belongs to.
src/lib/server/progress.ts      A run folded into a board record; those folded into standings.
src/lib/server/stores.ts        The one place that picks an adapter.
src/routes/+layout.server.ts    The gate: no name, no game.
src/routes/{hello,top}/         Pick a name; who is ahead.
src/routes/api/                 checks, runs, feedback.
pipeline/                       Offline puzzle generation (Python, separate job).
```

The rules live in `engine.ts` as pure functions on purpose — they're the part most likely to
change while tuning, they're unit-tested independently of the UI, and the server grades with
the same functions the client used to, rather than a second copy that can drift.

`contract.ts` is one test suite per port, run against every adapter. A behaviour only one
adapter has is a bug in the port.

## Adding a puzzle

Append to `src/lib/data/puzzles.json`: five groups of four words each, unique across the
puzzle, **at most 12 characters per word** (four columns on a phone is about 70px a tile).
`pnpm test` enforces all of that.

A group may also carry `notes` — the summary and the per-word lines a player reads once
the row has cleared. Optional, and all-or-nothing per board: `pnpm test` will reject a
board that explains some of its rows and not the others, because five bars where three
open reads as three that are broken. Write them by hand, or buy them with
`cd pipeline && uv run python -m connectris_pipeline.cli gloss`.

Write real traps — a word that looks like it belongs to another group, where that group is
already full without it. And check there is no _second_ valid partition; that's the failure
mode that makes players furious.

Or generate one. `pipeline/` is an offline job that proposes a board with a strong model,
has a weak one try to solve it, red-teams it for that second partition, and grades what
survives — one board at a time, stopping at the first that is accepted. Run nightly it
publishes tomorrow's board, and it does that only if somebody finished today's, so a game
nobody is playing costs nothing. Its tests run offline against a scripted stand-in for the
model, with no credentials:

```sh
cd pipeline && uv run --locked --extra dev pytest -q
```

See [pipeline/README.md](./pipeline/README.md) for how to run and deploy it,
[docs/generation-cost.md](./docs/generation-cost.md) for what it costs, and
[DESIGN.md](./DESIGN.md#puzzle-generation-pipeline) for why it is shaped that way. The
honest caveat: it is a filter for **broken** boards, not a difficulty oracle — its
thresholds are reasoned, not fitted to human play, and they stay that way until there is
enough of it to fit them to.

## Deployment

Pushes to `main` build with Cloud Build and deploy to Cloud Run in `europe-north1`, via
`.github/workflows/deploy.yml`. Authentication is Workload Identity Federation, so there is
no key anywhere; only this repository may exchange a token.

`ci.yml` runs lint, type check, tests and a build, holds the Firestore adapters to the same
store contract against the emulator, and runs the pipeline's own checks.

Boards live in the `puzzles` collection, each with a `liveOn` date. Today's board is the
most recent one dated on or before today, so a board stays up until a later one is due and
a night that generates nothing repeats a day rather than leaving a hole.
`scripts/seed.mjs` puts the bundled boards there, dated one a day ending today; the
generator adds one a night after that.

The generator is a second Cloud Run Job, deployed by `.github/workflows/deploy-pipeline.yml`.
**Deploying it does not start it** — a job that is never executed costs nothing, and the
`gcloud scheduler` command that turns it on is in `pipeline/README.md`, to be run on
purpose.
