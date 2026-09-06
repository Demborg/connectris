import { describe, expect, it } from 'vitest';
import puzzles from '../data/puzzles.json';
import { localChecker } from './checker';
import { CHECKS, ROWS, boardOf, swapTiles } from './engine';
import type { Puzzle, Row } from './types';

const all = puzzles as Puzzle[];
const puzzle = all[1];

/**
 * The solution, built out of a real deal so the tile ids are the ones a grader will see.
 * Going through `boardOf` rather than minting ids by hand is the point: it is the same
 * board a player would be handed.
 */
function solvedRows(p: Puzzle): Row[] {
	const byWord = new Map(
		boardOf(p)
			.rows.flat()
			.map((t) => [t.word, t])
	);
	return p.groups.map((g) => g.words.map((w) => byWord.get(w)!));
}

const ids = (groups: { id: string }[]) => groups.map((g) => g.id);

describe('localChecker', () => {
	it('names every category, top first, when the board is solved', async () => {
		const r = await localChecker(puzzle)(solvedRows(puzzle), 1);
		expect(r.locked).toBe(ROWS);
		expect(ids(r.cleared)).toEqual(ids(puzzle.groups));
		expect(r.missed).toEqual([]);
	});

	it('names only the rows that cleared, never the correct ones below them', async () => {
		const broken = swapTiles(solvedRows(puzzle), { row: 2, col: 0 }, { row: 3, col: 0 });
		const r = await localChecker(puzzle)(broken, 1);
		expect(r.locked).toBe(2);
		expect(r.correctCount).toBe(3);
		expect(ids(r.cleared)).toEqual(ids(puzzle.groups.slice(0, 2)));
	});

	it('says nothing about what was missed while checks remain', async () => {
		// An unfound category is the answer. Pin 4 buys the count feedback by never saying
		// where, and naming a row the player has not cleared says exactly that.
		const broken = swapTiles(solvedRows(puzzle), { row: 0, col: 0 }, { row: 1, col: 0 });
		const r = await localChecker(puzzle)(broken, CHECKS - 1);
		expect(r.locked).toBe(0);
		expect(r.missed).toEqual([]);
	});

	it('works out what was never found from the board alone', async () => {
		// Two rows cleared by an earlier check are simply no longer on the board. A grader
		// that remembers nothing between presses has to read that off what it was handed,
		// which is what lets a check cost no stored state.
		const rows = solvedRows(puzzle).slice(2);
		const broken = swapTiles(rows, { row: 0, col: 0 }, { row: 1, col: 0 });
		const r = await localChecker(puzzle)(broken, CHECKS);
		expect(ids(r.missed)).toEqual(ids(puzzle.groups.slice(2)));
	});

	it('reveals nothing when the last check is the one that wins', async () => {
		const r = await localChecker(puzzle)(solvedRows(puzzle), CHECKS);
		expect(r.locked).toBe(ROWS);
		expect(r.missed).toEqual([]);
	});
});
