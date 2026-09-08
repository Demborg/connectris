import { isHttpError } from '@sveltejs/kit';
import { describe, expect, it } from 'vitest';
import puzzles from '$lib/data/puzzles.json';
import { ROWS, boardOf } from '$lib/game/engine';
import type { CheckOutcome, Puzzle } from '$lib/game/types';
import { POST } from './+server';

const boards = puzzles as Puzzle[];
const board = boards[0];

/** The solution to a board, as the tile ids a client would post. */
function solution(p: Puzzle): number[][] {
	const byWord = new Map(
		boardOf(p)
			.rows.flat()
			.map((t) => [t.word, t])
	);
	return p.groups.map((g) => g.words.map((w) => byWord.get(w)!.id));
}

function post(body: unknown) {
	const request = new Request('http://localhost/api/checks', {
		method: 'POST',
		headers: { 'content-type': 'application/json' },
		body: typeof body === 'string' ? body : JSON.stringify(body)
	});
	return POST({ request } as unknown as Parameters<typeof POST>[0]);
}

/** The status a request comes back with, however it comes back. */
async function status(body: unknown): Promise<number> {
	try {
		return (await post(body)).status;
	} catch (e) {
		if (isHttpError(e)) return e.status;
		throw e;
	}
}

const check = (over: Record<string, unknown> = {}) => ({
	puzzleId: board.id,
	rows: solution(board),
	checksUsed: 1,
	...over
});

describe('POST /api/checks', () => {
	it('grades a solved board and names the categories in clearing order', async () => {
		const res = await post(check());
		expect(res.status).toBe(200);

		const outcome = (await res.json()) as CheckOutcome;
		expect(outcome.locked).toBe(ROWS);
		expect(outcome.cleared.map((g) => g.id)).toEqual(board.groups.map((g) => g.id));
	});

	it('answers with counts and categories, never with the board it graded', async () => {
		// The response is the whole surface the answer key could escape through, so what
		// it may contain is worth pinning rather than assuming.
		const outcome = (await (await post(check({ rows: solution(board).slice(1) }))).json()) as
			CheckOutcome | Record<string, unknown>;
		expect(Object.keys(outcome).sort()).toEqual(['cleared', 'correctCount', 'locked', 'missed']);
	});

	it('refuses a tile sent twice', async () => {
		const rows = solution(board);
		rows[1][0] = rows[0][0];
		expect(await status(check({ rows }))).toBe(400);
	});

	it('refuses a tile that is not on this board', async () => {
		const rows = solution(board);
		rows[0][0] = 9999;
		expect(await status(check({ rows }))).toBe(400);
	});

	it('refuses a row that is not four tiles', async () => {
		const rows = solution(board);
		rows[0] = rows[0].slice(1);
		expect(await status(check({ rows }))).toBe(400);
	});

	it('refuses a check that has not been paid for', async () => {
		expect(await status(check({ checksUsed: 0 }))).toBe(400);
	});

	it('refuses a body that is not JSON', async () => {
		expect(await status('not json at all')).toBe(400);
	});

	it('will not grade a board it has not published', async () => {
		// Which boards count as published is the store's job, and its contract already
		// pins that a board dated later than today is not among them.
		expect(await status(check({ puzzleId: 'no-such-board' }))).toBe(404);
	});
});

describe('a board in either language', () => {
	it('grades a Swedish board without being told which language it is', async () => {
		// The endpoint looks the board up across every language on purpose: the id names one
		// board, and asking the client which language it belongs to would be trusting the
		// client to describe its own board. Narrowing to one language here would have made
		// every check a Swedish player pressed answer 404.
		const swedish = boards.find((p) => p.language === 'sv');
		expect(swedish, 'no Swedish board shipped to grade').toBeDefined();

		const answered = await post({
			puzzleId: swedish!.id,
			rows: solution(swedish!),
			checksUsed: 1
		});
		expect(answered.status).toBe(200);
		const outcome = (await answered.json()) as CheckOutcome;
		expect(outcome.locked).toBe(ROWS);
		expect(outcome.cleared.map((g) => g.id)).toEqual(swedish!.groups.map((g) => g.id));
	});
});
