import { expect, it } from 'vitest';
import puzzles from '$lib/data/puzzles.json';
import type { Puzzle } from '$lib/game/types';
import type { Day, Feedback, FeedbackStore, PuzzleStore, RunRecord, RunStore } from './ports';

/**
 * One suite per port, run against every adapter.
 *
 * The point of a port is that callers cannot tell its implementations apart, and the only
 * way to keep that true is to describe the behaviour once and make each adapter answer to
 * it. A behaviour only one adapter has is a bug in the port, not a feature of the adapter.
 */

export const boards = puzzles as Puzzle[];

const TODAY: Day = '2026-09-05';

export function runOf(over: Partial<RunRecord> = {}): RunRecord {
	return {
		id: 'run-1',
		userId: 'user-1',
		displayName: null,
		puzzle: boards[0].id,
		startedAt: 1_700_000_000_000,
		outcome: 'won',
		timeMs: 252_000,
		checksLeft: 1,
		moves: 34,
		checks: 3,
		events: [{ t: 0, type: 'start', puzzle: boards[0].id }],
		...over
	};
}

export function feedbackOf(over: Partial<Feedback> = {}): Feedback {
	return {
		runId: 'run-1',
		userId: 'user-1',
		puzzleId: boards[0].id,
		difficulty: 'right',
		fair: true,
		comment: '',
		...over
	};
}

export function puzzleStoreContract(make: (boards: Puzzle[], today: Day) => Promise<PuzzleStore>) {
	const store = () => make(boards, TODAY);

	it('serves the board scheduled for a day', async () => {
		// Newest last, so the final board in the list is the one for today.
		expect(await (await store()).scheduledFor(TODAY)).toEqual(boards.at(-1));
	});

	it('has nothing to serve for a day with no board', async () => {
		expect(await (await store()).scheduledFor('2030-01-01')).toBeNull();
	});

	it('finds a board by id, and admits when it cannot', async () => {
		const s = await store();
		expect(await s.byId(boards[0].id)).toEqual(boards[0]);
		expect(await s.byId('no-such-board')).toBeNull();
	});

	it('lists the backlog newest first', async () => {
		const listed = await (await store()).published(TODAY, boards.length);
		expect(listed.map((p) => p.id)).toEqual([...boards].reverse().map((p) => p.id));
	});

	it('never lists a board scheduled after the day asked for', async () => {
		// The whole isolation between a batch job that schedules ahead and a request path
		// that serves: a board with tomorrow's date is not published yet, whoever wrote it.
		const yesterday = await (await store()).published('2026-09-04', boards.length);
		expect(yesterday.map((p) => p.id)).not.toContain(boards.at(-1)!.id);
	});

	it('honours a limit', async () => {
		expect(await (await store()).published(TODAY, 1)).toHaveLength(1);
	});
}

export type RunHarness = { store: RunStore; recorded(): Promise<RunRecord[]> };

export function runStoreContract(make: () => Promise<RunHarness>) {
	it('keeps a run it was given', async () => {
		const { store, recorded } = await make();
		await store.record(runOf());
		expect(await recorded()).toEqual([runOf()]);
	});

	it('counts one run once, however many times it is sent', async () => {
		// The client posts best-effort and may retry. A retried run is the same run.
		const { store, recorded } = await make();
		await store.record(runOf());
		await store.record(runOf());
		expect(await recorded()).toHaveLength(1);
	});
}

export type FeedbackHarness = { store: FeedbackStore; recorded(): Promise<Feedback[]> };

export function feedbackStoreContract(make: () => Promise<FeedbackHarness>) {
	it('keeps an answer', async () => {
		const { store, recorded } = await make();
		await store.record(feedbackOf());
		expect(await recorded()).toEqual([feedbackOf()]);
	});

	it('lets a player finish answering without becoming two opinions', async () => {
		// The screen posts on every tap, so a completed form arrives as a series of partial
		// ones. Keyed by run, the last one wins and the count of opinions stays at one.
		const { store, recorded } = await make();
		await store.record(feedbackOf({ difficulty: 'hard', fair: null }));
		await store.record(feedbackOf({ difficulty: 'hard', fair: false, comment: 'row 3' }));

		const kept = await recorded();
		expect(kept).toHaveLength(1);
		expect(kept[0]).toMatchObject({ difficulty: 'hard', fair: false, comment: 'row 3' });
	});
}
