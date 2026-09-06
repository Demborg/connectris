import { expect, it } from 'vitest';
import puzzles from '$lib/data/puzzles.json';
import type { Puzzle } from '$lib/game/types';
import type { Feedback, FeedbackStore, PuzzleStore, RunRecord, RunStore } from './ports';

/**
 * One suite per port, run against every adapter.
 *
 * The point of a port is that callers cannot tell its implementations apart, and the only
 * way to keep that true is to describe the behaviour once and make each adapter answer to
 * it. A behaviour only one adapter has is a bug in the port, not a feature of the adapter.
 */

export const boards = puzzles as Puzzle[];

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

/**
 * @param make Publishes `published` one per day ending today, and dates `upcoming` after
 *   it. Both are in publication order, oldest first.
 */
export function puzzleStoreContract(
	make: (published: Puzzle[], upcoming: Puzzle[]) => Promise<PuzzleStore>
) {
	const store = (upcoming: Puzzle[] = []) =>
		make(boards.slice(0, boards.length - upcoming.length), upcoming);

	const newest = boards[boards.length - 1];

	it('lists published boards newest first, so the head of the list is today', async () => {
		// The nightly job adds a board a day. A store that answered oldest-first would put
		// every new board at the far end of a windowed query, where nothing reads it.
		const listed = await (await store()).live(boards.length);
		expect(listed.map((p) => p.id)).toEqual([...boards].reverse().map((p) => p.id));
	});

	it('hands back whole boards, answer key included', async () => {
		// A store is the one place that holds the solution. Stripping it is the request
		// path's job, and it cannot strip what it was never given.
		expect((await (await store()).live(1))[0]).toEqual(newest);
	});

	it('honours a limit', async () => {
		expect(await (await store()).live(1)).toHaveLength(1);
	});

	it('never lists a board that is not due yet', async () => {
		// The generator writes tomorrow's board tonight, so at any moment there is a board
		// in the collection that no player may see. There is no lookup beside this one, so
		// a board being absent from here is a board that cannot be reached at all.
		const listed = await (await store([newest])).live(boards.length);
		expect(listed.map((p) => p.id)).not.toContain(newest.id);
		expect(listed).toHaveLength(boards.length - 1);
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
