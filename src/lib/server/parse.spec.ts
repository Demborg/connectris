import { isHttpError } from '@sveltejs/kit';
import { describe, expect, it } from 'vitest';
import { feedbackOf, runOf } from './contract';
import { parseFeedback, parseRun } from './parse';

/** A run as it arrives on the wire, before anything has vouched for it. */
const sent = (over: Record<string, unknown> = {}) => ({ ...runOf(), ...over });

function rejects(body: unknown, parse = parseRun as (b: unknown) => unknown): number {
	try {
		parse(body);
		return 200;
	} catch (e) {
		if (isHttpError(e)) return e.status;
		throw e;
	}
}

describe('parseRun', () => {
	it('accepts a run and hands back exactly the fields it knows', async () => {
		expect(parseRun(sent())).toEqual(runOf());
	});

	it('drops anything it was not asked for', async () => {
		// The body is a browser's word for what happened, so what gets stored is the set
		// of fields named here rather than whatever turned up.
		const parsed = parseRun(sent({ isCheater: false, score: 9001 }));
		expect(Object.keys(parsed)).not.toContain('score');
	});

	it('keeps the event log as sent', async () => {
		// Pin 10: runs are kept so they can be retro-scored against metrics we have not
		// committed to, which means not filtering the log down to the ones we have.
		const events = [
			{ t: 0, type: 'start', puzzle: 'p' },
			{ t: 9, type: 'swapTiles', a: [0, 0], b: [1, 1] }
		];
		expect(parseRun(sent({ events })).events).toEqual(events);
	});

	it('refuses an id that could not safely become a filename', async () => {
		expect(rejects(sent({ id: '../../etc/passwd' }))).toBe(400);
	});

	it('refuses an outcome that is not one of the two', async () => {
		expect(rejects(sent({ outcome: 'drew' }))).toBe(400);
	});

	it('refuses counts that are not counts', async () => {
		expect(rejects(sent({ moves: -1 }))).toBe(400);
		expect(rejects(sent({ checks: 1.5 }))).toBe(400);
	});

	it('refuses a log too long to be a game', async () => {
		expect(rejects(sent({ events: Array(5000).fill({ t: 0, type: 'start', puzzle: 'p' }) }))).toBe(
			400
		);
	});

	it('refuses a body that is not an object', async () => {
		expect(rejects('a run, honestly')).toBe(400);
		expect(rejects(null)).toBe(400);
	});
});

/** Answers as they arrive on the wire, one tap at a time. */
const said = (over: Record<string, unknown> = {}) => ({ ...feedbackOf(), ...over });
const rejectsAnswer = (body: unknown) => rejects(body, parseFeedback);

describe('parseFeedback', () => {
	it('accepts a full answer', async () => {
		expect(parseFeedback(said())).toEqual(feedbackOf());
	});

	it('accepts an answer to only the first question', async () => {
		// The screen posts on every tap and is skippable, so this is the common shape, not
		// a degraded one. Difficulty alone is the answer most worth having.
		const partial = parseFeedback({
			runId: 'run-1',
			userId: 'user-1',
			puzzleId: 'p',
			difficulty: 'hard'
		});
		expect(partial).toMatchObject({ difficulty: 'hard', fair: null, comment: '' });
	});

	it('refuses a difficulty outside the three', async () => {
		expect(rejectsAnswer(said({ difficulty: 'brutal' }))).toBe(400);
	});

	it('refuses a fairness that is not a yes or a no', async () => {
		expect(rejectsAnswer(said({ fair: 'sort of' }))).toBe(400);
	});

	it('refuses an essay', async () => {
		expect(rejectsAnswer(said({ comment: 'x'.repeat(2001) }))).toBe(400);
	});

	it('insists on something to file the opinion against', async () => {
		// An opinion with no run is not evidence about anything.
		expect(rejectsAnswer(said({ runId: undefined }))).toBe(400);
		expect(rejectsAnswer(said({ puzzleId: undefined }))).toBe(400);
	});
});
