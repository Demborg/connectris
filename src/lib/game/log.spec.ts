import { beforeEach, describe, expect, it } from 'vitest';
import { loadProgress, loadRuns, recordBest, saveRun, type Run } from './log';

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

describe('loadProgress', () => {
	beforeEach(lendStorage);

	it('says nothing about a browser that has not played', () => {
		expect(loadProgress()).toEqual({});
	});

	it('marks a board played without claiming it was solved', () => {
		saveRun(run('alpha'));

		expect(loadProgress()).toEqual({ alpha: { played: true } });
	});

	it('carries the best of a solved board, so the page can show what it cost', () => {
		saveRun(run('alpha', 'won'));
		recordBest('alpha', { timeMs: 90_000, checksLeft: 2, moves: 12, checks: 2 });

		const progress = loadProgress();
		expect(progress.alpha.best).toMatchObject({ timeMs: 90_000, checksLeft: 2 });
	});

	/**
	 * The reason `loadProgress` reads both stores rather than just the runs. Runs are
	 * capped; bests are not — so solving a board outlives the record of having played it.
	 */
	it('keeps a solved board solved after its run has aged out of the log', () => {
		saveRun(run('ancient', 'won'));
		recordBest('ancient', { timeMs: 60_000, checksLeft: 3, moves: 9, checks: 1 });
		for (let i = 0; i < 60; i++) saveRun(run(`later-${i}`));

		expect(loadRuns().some((r) => r.puzzle === 'ancient')).toBe(false);
		expect(loadProgress().ancient).toMatchObject({ played: true });
		expect(loadProgress().ancient.best?.checksLeft).toBe(3);
	});

	/** The matching honesty: a board only ever lost does fall off, and should. */
	it('forgets a board that was only ever lost once its run ages out', () => {
		saveRun(run('faded'));
		for (let i = 0; i < 60; i++) saveRun(run(`later-${i}`));

		expect(loadProgress().faded).toBeUndefined();
	});
});
