import { beforeEach, describe, expect, it } from 'vitest';
import { better, bestOf, loadRuns, saveRun, type Run } from './log';

/** The log talks to `localStorage` directly; node has none, so lend it one. */
function lendStorage(): void {
	const store = new Map<string, string>();
	Object.defineProperty(globalThis, 'localStorage', {
		configurable: true,
		value: {
			getItem: (k: string) => store.get(k) ?? null,
			setItem: (k: string, v: string) => void store.set(k, v),
			removeItem: (k: string) => void store.delete(k),
			clear: () => store.clear()
		}
	});
}

const run = (puzzle: string, outcome: 'won' | 'lost' = 'lost'): Run => ({
	puzzle,
	startedAt: 0,
	outcome,
	timeMs: 90_000,
	checksLeft: outcome === 'won' ? 2 : 0,
	moves: 12,
	checks: outcome === 'won' ? 2 : 4,
	events: []
});

describe('the local log', () => {
	beforeEach(lendStorage);

	it('keeps a run, newest first', () => {
		saveRun(run('alpha'));
		saveRun(run('beta'));

		expect(loadRuns().map((r) => r.puzzle)).toEqual(['beta', 'alpha']);
	});

	/**
	 * The reason this is still only a log. Runs are capped, so what a browser remembers
	 * having played fades — which is fine now that it is nobody's answer to anything. What
	 * boards you have solved comes from the server, where it is not capped and not tied to
	 * one browser. This kept a second, uncapped store of bests for exactly that job, and
	 * that store was the thing that disagreed with the standings.
	 */
	it('forgets the oldest runs rather than growing without bound', () => {
		saveRun(run('ancient', 'won'));
		for (let i = 0; i < 60; i++) saveRun(run(`later-${i}`));

		expect(loadRuns()).toHaveLength(50);
		expect(loadRuns().some((r) => r.puzzle === 'ancient')).toBe(false);
	});

	it('treats an unreachable store as an empty one', () => {
		Object.defineProperty(globalThis, 'localStorage', {
			configurable: true,
			get() {
				throw new Error('private mode');
			}
		});

		expect(loadRuns()).toEqual([]);
		expect(() => saveRun(run('alpha'))).not.toThrow();
	});
});

describe('better', () => {
	const best = (checksLeft: number, timeMs: number) => ({
		checksLeft,
		timeMs,
		moves: 0,
		checks: 0
	});

	it('takes anything over nothing', () => {
		expect(better(best(0, 999_000), null)).toBe(true);
	});

	it('ranks checks in hand above time', () => {
		// The whole bet of the game is spending checks well, so a win that spent fewer is
		// the better win even if it took longer to think about.
		expect(better(best(2, 300_000), best(1, 10_000))).toBe(true);
		expect(better(best(1, 10_000), best(2, 300_000))).toBe(false);
	});

	it('breaks a tie on time', () => {
		expect(better(best(2, 40_000), best(2, 41_000))).toBe(true);
		expect(better(best(2, 41_000), best(2, 40_000))).toBe(false);
	});

	it('does not beat an equal result, so a replay does not churn the record', () => {
		expect(better(best(2, 40_000), best(2, 40_000))).toBe(false);
	});
});

describe('bestOf', () => {
	it('keeps only what a best is judged on', () => {
		expect(bestOf(run('alpha', 'won'))).toEqual({
			timeMs: 90_000,
			checksLeft: 2,
			moves: 12,
			checks: 2
		});
	});
});
