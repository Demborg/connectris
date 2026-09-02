# Connectris

A word-grouping puzzle where **the order of your rows is part of the answer**.

Twenty words, five rows of four. Every row is a category. Hit _Check_ and only the leading
run of correct rows clears — a correct row sitting below a wrong one doesn't count. So you
rank your rows by how sure you are, and bet. Clearing rows light up in a wave rolling down
the board and lock in place. Every check spends one of six, so getting the order right —
and clearing several rows at once — is what keeps them.

**Play it:** https://demborg.se/connectris/

This is phase 0 — a prototype with hand-written puzzles and no backend, built to find out
whether the mechanics are fun before anything else gets built. The reasoning behind every
rule, what is deliberately dropped, what is still undecided, and where this is going next
is in **[DESIGN.md](./DESIGN.md)**.

## Running it

```sh
pnpm install
pnpm dev
```

| Command       | Does                                    |
| ------------- | --------------------------------------- |
| `pnpm dev`    | Dev server                              |
| `pnpm test`   | Unit tests (game rules and puzzle data) |
| `pnpm check`  | Type check                              |
| `pnpm lint`   | Prettier + ESLint                       |
| `pnpm format` | Fix formatting                          |
| `pnpm build`  | Static build into `build/`              |

## Layout

```
src/lib/game/engine.ts          Pure rules: dealing, checking, moves. No UI, no state.
src/lib/game/session.svelte.ts  Runtime state for one run — budget, verdict, animation beats.
src/lib/game/log.ts             Local play log and personal bests.
src/lib/data/puzzles.json       Demo puzzles.
src/lib/components/             Board, tiles, solved rows, end card.
```

The rules live in `engine.ts` as pure functions on purpose — they're the part most likely to
change while tuning, and they're unit-tested independently of the UI.

## Adding a puzzle

Append to `src/lib/data/puzzles.json`: five groups of four words each, unique across the
puzzle, **at most 12 characters per word** (four columns on a phone is about 70px a tile).
`pnpm test` enforces all of that.

Write real traps — a word that looks like it belongs to another group, where that group is
already full without it. And check there is no _second_ valid partition; that's the failure
mode that makes players furious.

## Deployment

Pushes to `main` build and publish to GitHub Pages via `.github/workflows/deploy.yml`.
`ci.yml` runs lint, type check, tests and a build on every push and PR.
