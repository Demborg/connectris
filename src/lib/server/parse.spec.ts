import { isHttpError } from '@sveltejs/kit';
import { describe, expect, it } from 'vitest';
import { runOf } from './contract';
import { parseRun } from './parse';

/** A run as it arrives on the wire, before anything has vouched for it. */
const sent = (over: Record<string, unknown> = {}) => ({ ...runOf(), ...over });

function rejects(body: unknown): number {
	try {
		parseRun(body);
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
