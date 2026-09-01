import type { CheckResult, Position, Puzzle, Row, Tile } from './types';

/** Words per row / row width. */
export const COLS = 4;
/** Rows on a full board, i.e. number of categories. */
export const ROWS = 5;
/** Failed checks allowed before the run ends. */
export const LIVES = 4;

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

export function tilesOf(puzzle: Puzzle): Tile[] {
	let id = 0;
	return puzzle.groups.flatMap((g) => g.words.map((word) => ({ id: id++, word, group: g.id })));
}

/**
 * Deal a puzzle into its starting layout.
 *
 * Deterministic: every player gets byte-identical starting rows, which is what makes
 * a move-count leaderboard fair. Re-seeds until no row is accidentally complete, so
 * nobody is handed a free lock.
 */
export function deal(puzzle: Puzzle): Row[] {
	const tiles = tilesOf(puzzle);
	for (let attempt = 0; attempt < 64; attempt++) {
		const next = rng(hashSeed(`${puzzle.id}#${attempt}`));
		const flat = shuffled(tiles, next);
		const rows: Row[] = [];
		for (let i = 0; i < flat.length; i += COLS) rows.push(flat.slice(i, i + COLS));
		if (!rows.some(isComplete)) return rows;
	}
	throw new Error(`could not deal a non-trivial board for puzzle ${puzzle.id}`);
}

/* -------------------------------------------------------------------------- */
/* Rules                                                                       */
/* -------------------------------------------------------------------------- */

/** A row is complete when all its tiles share a group. Order within a row is irrelevant. */
export function isComplete(row: Row): boolean {
	return row.length === COLS && row.every((t) => t.group === row[0].group);
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
export function check(rows: Row[]): CheckResult {
	const correct = rows.map(isComplete);
	const locked = leadingRun(correct);
	const correctCount = correct.filter(Boolean).length;
	return { correct, locked, correctCount, costLife: locked === 0 };
}

/* -------------------------------------------------------------------------- */
/* Moves                                                                       */
/* -------------------------------------------------------------------------- */

/** Swap two tiles. One move, wherever they are. */
export function swapTiles(rows: Row[], a: Position, b: Position): Row[] {
	const next = rows.map((r) => r.slice());
	const tmp = next[a.row][a.col];
	next[a.row][a.col] = next[b.row][b.col];
	next[b.row][b.col] = tmp;
	return next;
}

/** Swap two whole rows. Also one move — reordering is the mechanic, not a tax. */
export function swapRows(rows: Row[], a: number, b: number): Row[] {
	const next = rows.slice();
	[next[a], next[b]] = [next[b], next[a]];
	return next;
}
