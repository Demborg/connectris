import type { Answer, Board, CheckResult, Position, Puzzle, Row, Tile } from './types';

/** Words per row / row width. */
export const COLS = 4;
/** Rows on a full board, i.e. number of categories. */
export const ROWS = 5;
/**
 * Checks allowed in a run. Every check spends one, whether it clears rows or not.
 *
 * The floor is four: clearing a single row at a time takes 1+1+1+2 checks, because three
 * rows solved leaves two, and if the top of those two is right the other one is forced.
 * So four is the floor exactly, and there is nothing spare. A run that clears one row at a
 * time has to be perfect; every miss has to be bought back by taking two rows in a single
 * check later. That makes batching the way through rather than a way to save money, which
 * is the strongest version of the ordering bet the game is built on.
 */
export const CHECKS = 4;

/* -------------------------------------------------------------------------- */
/* Deterministic dealing                                                       */
/* -------------------------------------------------------------------------- */

/** xmur3 — string to a well-mixed 32-bit seed. */
function hashSeed(str: string): number {
	let h = 1779033703 ^ str.length;
	for (let i = 0; i < str.length; i++) {
		h = Math.imul(h ^ str.charCodeAt(i), 3432918353);
		h = (h << 13) | (h >>> 19);
	}
	return h >>> 0;
}

/** mulberry32 — small, fast, good enough, and identical in every JS engine. */
function rng(seed: number): () => number {
	let a = seed >>> 0;
	return () => {
		a = (a + 0x6d2b79f5) >>> 0;
		let t = Math.imul(a ^ (a >>> 15), 1 | a);
		t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
		return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
	};
}

function shuffled<T>(items: T[], next: () => number): T[] {
	const out = items.slice();
	for (let i = out.length - 1; i > 0; i--) {
		const j = Math.floor(next() * (i + 1));
		[out[i], out[j]] = [out[j], out[i]];
	}
	return out;
}

/** A dealt board and the key that grades it. Only `rows` is safe to hand to a player. */
export type Deal = { rows: Row[]; answer: Answer };

function tilesOf(puzzle: Puzzle): { tiles: Tile[]; answer: Answer } {
	const answer: Answer = new Map();
	let id = 0;
	const tiles = puzzle.groups.flatMap((g) =>
		g.words.map((word) => {
			const tile = { id: id++, word };
			answer.set(tile.id, g.id);
			return tile;
		})
	);
	return { tiles, answer };
}

/**
 * Deal a puzzle into its starting layout, and the key that grades it.
 *
 * Deterministic: every player gets byte-identical starting rows, which is what makes
 * a move-count leaderboard fair. Re-seeds until no row is accidentally complete, so
 * nobody is handed a free lock.
 *
 * Determinism is also what keeps checking cheap to do remotely: the key is a pure
 * function of the puzzle id, so it can be re-derived on demand rather than stored.
 */
export function deal(puzzle: Puzzle): Deal {
	const { tiles, answer } = tilesOf(puzzle);
	for (let attempt = 0; attempt < 64; attempt++) {
		const next = rng(hashSeed(`${puzzle.id}#${attempt}`));
		const flat = shuffled(tiles, next);
		const rows: Row[] = [];
		for (let i = 0; i < flat.length; i += COLS) rows.push(flat.slice(i, i + COLS));
		if (!rows.some((row) => isComplete(row, answer))) return { rows, answer };
	}
	throw new Error(`could not deal a non-trivial board for puzzle ${puzzle.id}`);
}

/** Deal a board for a player: the rows, and nothing that says how to grade them. */
export function boardOf(puzzle: Puzzle): Board {
	const { id, name, language } = puzzle;
	return { puzzle: { id, name, language }, rows: deal(puzzle).rows };
}

/* -------------------------------------------------------------------------- */
/* Rules                                                                       */
/* -------------------------------------------------------------------------- */

/** A row is complete when all its tiles share a group. Order within a row is irrelevant. */
export function isComplete(row: Row, answer: Answer): boolean {
	const group = answer.get(row[0]?.id ?? -1);
	return row.length === COLS && row.every((t) => answer.get(t.id) === group);
}

/** Length of the leading run of `true`. */
export function leadingRun(flags: boolean[]): number {
	const i = flags.indexOf(false);
	return i === -1 ? flags.length : i;
}

/**
 * Resolve a check against the rows still in play.
 *
 * Two rules do the work here (see DESIGN.md):
 *  - only the leading run of correct rows clears, so the player is betting on their
 *    own confidence ordering, not just on the grouping;
 *  - a check that clears nothing costs a life, so progress is free and stalling bites.
 *
 * `correctCount` is reported without saying *which* rows, so a miss still teaches you
 * something without collapsing the ordering puzzle.
 */
export function check(rows: Row[], answer: Answer): CheckResult {
	const correct = rows.map((row) => isComplete(row, answer));
	const locked = leadingRun(correct);
	const correctCount = correct.filter(Boolean).length;
	return { correct, locked, correctCount, costLife: locked === 0 };
}

/* -------------------------------------------------------------------------- */
/* Moves                                                                       */
/* -------------------------------------------------------------------------- */

/**
 * Swap two tiles. The only move in the game — rows are reordered by moving their
 * contents, so there is one verb to learn and nothing to optimise.
 */
export function swapTiles(rows: Row[], a: Position, b: Position): Row[] {
	const next = rows.map((r) => r.slice());
	const tmp = next[a.row][a.col];
	next[a.row][a.col] = next[b.row][b.col];
	next[b.row][b.col] = tmp;
	return next;
}
