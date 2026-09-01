import { describe, expect, it } from 'vitest';
import puzzles from '../data/puzzles.json';
import { COLS, ROWS, check, deal, isComplete, leadingRun, swapTiles } from './engine';
import type { Puzzle, Row } from './types';

const all = puzzles as Puzzle[];
const puzzle = all[1];

/** Build rows straight from the solution, then apply an optional row order. */
function solvedRows(p: Puzzle, order = [0, 1, 2, 3, 4]): Row[] {
	let id = 0;
	const byGroup = p.groups.map((g) => g.words.map((word) => ({ id: id++, word, group: g.id })));
	return order.map((i) => byGroup[i]);
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
});

describe('deal', () => {
	it('is deterministic, so move counts are comparable between players', () => {
		const a = deal(puzzle).map((r) => r.map((t) => t.word));
		const b = deal(puzzle).map((r) => r.map((t) => t.word));
		expect(a).toEqual(b);
	});

	it('lays out the whole puzzle exactly once', () => {
		const words = deal(puzzle)
			.flat()
			.map((t) => t.word);
		expect(words).toHaveLength(ROWS * COLS);
		expect(new Set(words)).toEqual(new Set(puzzle.groups.flatMap((g) => g.words)));
	});

	it.each(all.map((p) => [p.id, p] as const))('%s never opens with a free row', (_id, p) => {
		expect(deal(p).some(isComplete)).toBe(false);
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
		const r = check(solvedRows(puzzle));
		expect(r).toMatchObject({ locked: 5, correctCount: 5, costLife: false });
	});

	it('clears only the leading run, not correct rows further down', () => {
		// rows 0 and 1 correct, row 2 broken, rows 3 and 4 correct.
		const rows = solvedRows(puzzle);
		const broken = swapTiles(rows, { row: 2, col: 0 }, { row: 3, col: 0 });
		const r = check(broken);
		expect(r.correct).toEqual([true, true, false, false, true]);
		expect(r.locked).toBe(2);
		expect(r.correctCount).toBe(3);
		expect(r.costLife).toBe(false);
	});

	it('reports a count without revealing position, and still charges a life', () => {
		// Correct rows exist, but none of them is at the top.
		const rows = solvedRows(puzzle);
		const broken = swapTiles(rows, { row: 0, col: 0 }, { row: 1, col: 0 });
		const r = check(broken);
		expect(r.locked).toBe(0);
		expect(r.correctCount).toBe(3);
		expect(r.costLife).toBe(true);
	});

	it('never reports exactly one row short of a full board', () => {
		// With n rows, n-1 correct forces the nth. 4 is therefore unreachable.
		const rows = solvedRows(puzzle);
		for (let a = 0; a < ROWS; a++) {
			for (let b = a + 1; b < ROWS; b++) {
				const r = check(swapTiles(rows, { row: a, col: 0 }, { row: b, col: 0 }));
				expect(r.correctCount).not.toBe(ROWS - 1);
			}
		}
	});
});

describe('moves', () => {
	it('swapTiles exchanges two tiles and leaves the rest alone', () => {
		const rows = deal(puzzle);
		const next = swapTiles(rows, { row: 0, col: 0 }, { row: 4, col: 3 });
		expect(next[0][0]).toBe(rows[4][3]);
		expect(next[4][3]).toBe(rows[0][0]);
		expect(next[2]).toEqual(rows[2]);
		expect(rows[0][0]).not.toBe(next[0][0]); // original untouched
	});

	it('can reach any row order through tile swaps alone', () => {
		// There is no row-level move any more, so the confidence ordering has to be
		// reachable by moving tiles. Swapping four pairs exchanges two whole rows.
		let rows = solvedRows(puzzle);
		for (let col = 0; col < COLS; col++) {
			rows = swapTiles(rows, { row: 0, col }, { row: 3, col });
		}
		expect(rows[0].map((t) => t.word)).toEqual(puzzle.groups[3].words);
		expect(rows[3].map((t) => t.word)).toEqual(puzzle.groups[0].words);
		// And the reordering costs nothing: rows are sets, so a board of complete rows in a
		// different order is still complete.
		expect(check(rows).locked).toBe(ROWS);
	});
});
