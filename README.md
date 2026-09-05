# Connectris

A word-grouping puzzle where **the order of your rows is part of the answer**.

Twenty words, five rows of four. Every row is a category. Hit _Check_ and only the leading
run of correct rows clears — a correct row sitting below a wrong one doesn't count. So you
rank your rows by how sure you are, and bet. Clearing rows light up in a wave rolling down
the board and lock in place. Every check spends one of four, so getting the order right —
and clearing several rows at once — is what keeps them.

**Play it:** https://connectris-214765692756.europe-north1.run.app

Phase 1: a SvelteKit app on Cloud Run backed by Firestore, serving a small set of boards. The
client never holds the answer key — it gets twenty words, and every check is graded by the
server. Runs and a two-question survey are recorded, because the point of this phase is to
find out how real people play. The reasoning behind every rule, what is deliberately
dropped, what is still undecided, and where this is going next is in
**[DESIGN.md](./DESIGN.md)**.

## Running it

```sh
pnpm install
pnpm dev
```

With no `GOOGLE_CLOUD_PROJECT` set, the app runs entirely on itself: boards come from
`src/lib/data/puzzles.json` on a schedule derived from today, and runs and survey answers
are written as JSON files under `.data/`. No cloud project, no emulator, no network.

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
src/lib/game/log.ts             Local play log and personal bests.
src/lib/server/ports.ts         What the game needs from outside. Four ports.
src/lib/server/{memory,json,firestore}.ts   Three adapters answering to one contract.
src/lib/server/stores.ts        The one place that picks an adapter.
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

Write real traps — a word that looks like it belongs to another group, where that group is
already full without it. And check there is no _second_ valid partition; that's the failure
mode that makes players furious.

Or generate one. `pipeline/` is an offline batch job that proposes boards with a strong
model, has a quorum of weak ones try to solve them, red-teams the survivors for that second
partition, and grades what's left. Its tests run offline against a scripted stand-in for the
model, with no credentials:

```sh
cd pipeline && uv run --locked --extra dev pytest -q
```

See [pipeline/README.md](./pipeline/README.md), and
[DESIGN.md](./DESIGN.md#puzzle-generation-pipeline) for why it is shaped that way. It is
unproven against real models — its thresholds are reasoned, not measured.

## Deployment

Pushes to `main` build with Cloud Build and deploy to Cloud Run in `europe-north1`, via
`.github/workflows/deploy.yml`. Authentication is Workload Identity Federation, so there is
no key anywhere; only this repository may exchange a token.

`ci.yml` runs lint, type check, tests and a build, holds the Firestore adapters to the same
store contract against the emulator, and runs the pipeline's own checks.

Boards live in the `puzzles` collection, ordered by an `order` field — roughly easiest
first. `scripts/seed.mjs` puts the bundled ones there. There is deliberately no date on
them yet: nothing schedules ahead, so a daily rollover would be a concept with nothing to
do. It arrives with the nightly job, in the same commit that gives it something to mean.
