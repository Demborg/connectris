import { describe, expect, it } from 'vitest';
import puzzles from '../data/puzzles.json';
import { COLS, ROWS, check, deal, isComplete, leadingRun, swapTiles } from './engine';
import type { Answer, Puzzle, Row } from './types';

const all = puzzles as Puzzle[];
const puzzle = all[1];

/** Build rows straight from the solution, then apply an optional row order. */
function solvedRows(p: Puzzle, order = [0, 1, 2, 3, 4]): { rows: Row[]; answer: Answer } {
	const answer: Answer = new Map();
	let id = 0;
	const byGroup = p.groups.map((g) =>
		g.words.map((word) => {
			const tile = { id: id++, word };
			answer.set(tile.id, g.id);
			return tile;
		})
	);
	return { rows: order.map((i) => byGroup[i]), answer };
}

describe('puzzle data', () => {
	it.each(all.map((p) => [p.id, p] as const))('%s is well formed', (_id, p) => {
		expect(p.groups).toHaveLength(ROWS);
		for (const g of p.groups) expect(g.words).toHaveLength(COLS);

		const words = p.groups.flatMap((g) => g.words);
		expect(new Set(words).size).toBe(words.length);
	});

	it.each(all.map((p) => [p.id, p] as const))('%s fits four columns on a phone', (_id, p) => {
		// 4 columns on a 375px screen is roughly 80px a tile; anything longer than this
		// stops being readable even with the font autoscaling. See DESIGN.md.
		for (const g of p.groups) for (const w of g.words) expect(w.length).toBeLessThanOrEqual(12);
	});

	it.each(all.map((p) => [p.id, p] as const))('%s explains all of a row or none', (_id, p) => {
		// Notes arrived after the first boards did, so a board without them is legal and
		// its rows just do not open. A board with *some* of them is not: five bars where
		// three open reads as three that are broken, so the gloss stage writes all five
		// or leaves the board alone.
		const explained = p.groups.filter((g) => g.notes).length;
		expect([0, ROWS]).toContain(explained);

		for (const g of p.groups) {
			if (!g.notes) continue;
			expect(g.notes.summary).not.toBe('');
			// Paired by word rather than by position, so this is the check that the pairing
			// is possible at all: every word in the row has a line, and no line names a
			// word that is not in it.
			expect(g.notes.words.map((w) => w.word).sort()).toEqual([...g.words].sort());
			for (const w of g.notes.words) expect(w.note).not.toBe('');
		}
	});
});

describe('deal', () => {
	it('is deterministic, so move counts are comparable between players', () => {
		const a = deal(puzzle).rows.map((r) => r.map((t) => t.word));
		const b = deal(puzzle).rows.map((r) => r.map((t) => t.word));
		expect(a).toEqual(b);
	});

	it('lays out the whole puzzle exactly once', () => {
		const words = deal(puzzle)
			.rows.flat()
			.map((t) => t.word);
		expect(words).toHaveLength(ROWS * COLS);
		expect(new Set(words)).toEqual(new Set(puzzle.groups.flatMap((g) => g.words)));
	});

	it.each(all.map((p) => [p.id, p] as const))('%s never opens with a free row', (_id, p) => {
		const { rows, answer } = deal(p);
		expect(rows.some((row) => isComplete(row, answer))).toBe(false);
	});

	it('keeps the answer beside the board and never on it', () => {
		// The property the whole server-side check rests on: a dealt row is words and
		// nothing else, so handing one to a player gives away no part of the solution.
		const { rows, answer } = deal(puzzle);
		for (const tile of rows.flat()) {
			expect(Object.keys(tile).sort()).toEqual(['id', 'word']);
			expect(answer.get(tile.id)).toBeTypeOf('string');
		}
	});
});

describe('leadingRun', () => {
	it('counts only from the top', () => {
		expect(leadingRun([true, true, false, true, true])).toBe(2);
		expect(leadingRun([false, true, true, true, true])).toBe(0);
		expect(leadingRun([true, true, true, true, true])).toBe(5);
		expect(leadingRun([])).toBe(0);
	});
});

describe('check', () => {
	it('clears everything when the board is solved', () => {
		const { rows, answer } = solvedRows(puzzle);
		const r = check(rows, answer);
		expect(r).toMatchObject({ locked: 5, correctCount: 5, costLife: false });
	});

	it('clears only the leading run, not correct rows further down', () => {
		// rows 0 and 1 correct, row 2 broken, rows 3 and 4 correct.
		const { rows, answer } = solvedRows(puzzle);
		const broken = swapTiles(rows, { row: 2, col: 0 }, { row: 3, col: 0 });
		const r = check(broken, answer);
		expect(r.correct).toEqual([true, true, false, false, true]);
		expect(r.locked).toBe(2);
		expect(r.correctCount).toBe(3);
		expect(r.costLife).toBe(false);
	});

	it('reports a count without revealing position, and still charges a life', () => {
		// Correct rows exist, but none of them is at the top.
		const { rows, answer } = solvedRows(puzzle);
		const broken = swapTiles(rows, { row: 0, col: 0 }, { row: 1, col: 0 });
		const r = check(broken, answer);
		expect(r.locked).toBe(0);
		expect(r.correctCount).toBe(3);
		expect(r.costLife).toBe(true);
	});

	it('never reports exactly one row short of a full board', () => {
		// With n rows, n-1 correct forces the nth. 4 is therefore unreachable.
		const { rows, answer } = solvedRows(puzzle);
		for (let a = 0; a < ROWS; a++) {
			for (let b = a + 1; b < ROWS; b++) {
				const r = check(swapTiles(rows, { row: a, col: 0 }, { row: b, col: 0 }), answer);
				expect(r.correctCount).not.toBe(ROWS - 1);
			}
		}
	});
});

describe('moves', () => {
	it('swapTiles exchanges two tiles and leaves the rest alone', () => {
		const { rows } = deal(puzzle);
		const next = swapTiles(rows, { row: 0, col: 0 }, { row: 4, col: 3 });
		expect(next[0][0]).toBe(rows[4][3]);
		expect(next[4][3]).toBe(rows[0][0]);
		expect(next[2]).toEqual(rows[2]);
		expect(rows[0][0]).not.toBe(next[0][0]); // original untouched
	});

	it('can reach any row order through tile swaps alone', () => {
		// There is no row-level move any more, so the confidence ordering has to be
		// reachable by moving tiles. Swapping four pairs exchanges two whole rows.
		const { rows: dealt, answer } = solvedRows(puzzle);
		let rows = dealt;
		for (let col = 0; col < COLS; col++) {
			rows = swapTiles(rows, { row: 0, col }, { row: 3, col });
		}
		expect(rows[0].map((t) => t.word)).toEqual(puzzle.groups[3].words);
		expect(rows[3].map((t) => t.word)).toEqual(puzzle.groups[0].words);
		// And the reordering costs nothing: rows are sets, so a board of complete rows in a
		// different order is still complete.
		expect(check(rows, answer).locked).toBe(ROWS);
	});
});
