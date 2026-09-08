import { expect, it } from 'vitest';
import puzzles from '$lib/data/puzzles.json';
import type { Run } from '$lib/game/log';
import type { Puzzle } from '$lib/game/types';
import type { Locale } from '$lib/i18n';
import { handleOf } from '$lib/alias';
import type {
	Feedback,
	FeedbackStore,
	Player,
	PlayerStore,
	ProgressStore,
	PuzzleStore,
	RunRecord,
	RunStore
} from './ports';

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

/** A finished game with nobody's name on it — what the progress port is given. */
export function playOf(over: Partial<Run> = {}): Run {
	const named = runOf();
	delete (named as Partial<RunRecord>).id;
	delete (named as Partial<RunRecord>).userId;
	return { ...named, ...over };
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

export function playerOf(over: Partial<Player> = {}): Player {
	const alias = over.alias ?? 'Ada';
	return {
		id: 'user-1',
		registeredAt: 1_700_000_000_000,
		...over,
		alias,
		handle: over.handle ?? handleOf(alias)
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

	// The fixture is the shipped file and the shipped file is bilingual, so every
	// expectation below has to name a language rather than assume there is only one. That
	// this suite broke the day a Swedish board shipped is the suite working.
	const of = (language: Locale) => boards.filter((p) => p.language === language);
	const newest = boards[boards.length - 1];

	it('lists published boards newest first, so the head of the list is today', async () => {
		// The nightly job adds a board a day. A store that answered oldest-first would put
		// every new board at the far end of a windowed query, where nothing reads it.
		const listed = await (await store()).live(boards.length, 'en');
		expect(listed.map((p) => p.id)).toEqual([...of('en')].reverse().map((p) => p.id));
	});

	it('hands back whole boards, answer key included', async () => {
		// A store is the one place that holds the solution. Stripping it is the request
		// path's job, and it cannot strip what it was never given.
		const latest = of(newest.language as Locale).at(-1);
		expect((await (await store()).live(1, newest.language as Locale))[0]).toEqual(latest);
	});

	it('honours a limit', async () => {
		expect(await (await store()).live(1, 'en')).toHaveLength(1);
	});

	it('never lists a board that is not due yet', async () => {
		// The generator writes tomorrow's board tonight, so at any moment there is a board
		// in the collection that no player may see. There is no lookup beside this one, so
		// a board being absent from here is a board that cannot be reached at all.
		const language = newest.language as Locale;
		const listed = await (await store([newest])).live(boards.length, language);
		expect(listed.map((p) => p.id)).not.toContain(newest.id);
		expect(listed).toHaveLength(of(language).length - 1);
	});

	it('answers with one language and never the other', async () => {
		// Two languages share one schedule, so this is a filter rather than a second
		// collection — and it is the whole reason a Swedish player is not handed English
		// boards. The Firestore adapter narrows in memory to avoid a composite index, which
		// is exactly the sort of difference this suite exists to catch.
		const english = of('en');
		const swedish: Puzzle = { ...english[0], id: 'sv-board', name: 'Ett bräde', language: 'sv' };
		const mixed = await make([...english, swedish], []);

		expect((await mixed.live(50, 'sv')).map((p) => p.id)).toEqual(['sv-board']);
		expect((await mixed.live(50, 'en')).map((p) => p.id)).not.toContain('sv-board');
		expect(await mixed.live(50, 'en')).toHaveLength(english.length);
	});

	it('says a language is empty rather than falling back to another', async () => {
		// A language the game speaks but has published nothing in. The picker has to be
		// able to say so, which it cannot do if an empty language quietly answers with
		// another one's boards.
		const onlyEnglish = await make(of('en'), []);
		expect(await onlyEnglish.live(50, 'sv')).toEqual([]);
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

export function playerStoreContract(make: () => Promise<PlayerStore>) {
	it('registers a player and finds them again by id', async () => {
		const store = await make();
		expect(await store.register(playerOf())).toBe('ok');
		expect(await store.byId('user-1')).toEqual(playerOf());
	});

	it('says nothing about an id nobody registered', async () => {
		// The cookie outlives the database it was minted against, so this is an ordinary
		// answer rather than an error: it means "go and register", not "something broke".
		expect(await (await make()).byId('never-seen')).toBeNull();
	});

	it('refuses a name someone already has', async () => {
		const store = await make();
		await store.register(playerOf({ id: 'first', alias: 'Ada' }));

		expect(await store.register(playerOf({ id: 'second', alias: 'Ada' }))).toBe('taken');
		expect(await store.byId('second')).toBeNull();
	});

	it('refuses a name that differs only in case, because a top list cannot show both', async () => {
		const store = await make();
		await store.register(playerOf({ id: 'first', alias: 'Ada' }));

		expect(await store.register(playerOf({ id: 'second', alias: 'ADA' }))).toBe('taken');
	});

	it('keeps names apart when they only look alike in a stripped-down key', async () => {
		// A store that reduced a handle to its letters — which the filesystem one would do
		// on its own, since a name is not a safe filename — would file these as one.
		const store = await make();
		await store.register(playerOf({ id: 'first', alias: 'ada-lovelace' }));

		expect(await store.register(playerOf({ id: 'second', alias: 'ada lovelace' }))).toBe('ok');
		expect(await store.register(playerOf({ id: 'third', alias: 'Åke' }))).toBe('ok');
	});

	it('lists everyone, so the standings can put names to ids', async () => {
		const store = await make();
		await store.register(playerOf({ id: 'a', alias: 'Ada' }));
		await store.register(playerOf({ id: 'b', alias: 'Bo' }));

		const listed = await store.all(10);
		expect(listed.map((p) => p.id).sort()).toEqual(['a', 'b']);
	});
}

export function progressStoreContract(make: () => Promise<ProgressStore>) {
	const board = boards[0].id;
	const other = boards[boards.length - 1].id;

	it('records a win as a best', async () => {
		const store = await make();
		const kept = await store.record('ada', playOf({ puzzle: board, timeMs: 90_000 }));

		expect(kept).toMatchObject({ userId: 'ada', puzzleId: board, plays: 1 });
		expect(kept.best).toMatchObject({ timeMs: 90_000, checksLeft: 1 });
	});

	it('records a loss as a play with nothing to show for it', async () => {
		// The distinction the boards page draws: attempted is not solved, and a board you
		// lost should not come back looking untouched.
		const store = await make();
		const kept = await store.record('ada', playOf({ outcome: 'lost', checksLeft: 0 }));

		expect(kept.plays).toBe(1);
		expect(kept.best).toBeNull();
	});

	it('counts every play of a board on one record', async () => {
		const store = await make();
		await store.record('ada', playOf({ outcome: 'lost' }));
		const kept = await store.record('ada', playOf({ outcome: 'lost' }));

		expect(kept.plays).toBe(2);
		expect(await store.forUser('ada')).toHaveLength(1);
	});

	it('keeps the better win and ignores the worse one', async () => {
		const store = await make();
		await store.record('ada', playOf({ checksLeft: 2, timeMs: 100_000 }));
		const kept = await store.record('ada', playOf({ checksLeft: 1, timeMs: 10_000 }));

		// More checks in hand beats a faster time — the same rule the end card and the
		// standings apply, because there is only one.
		expect(kept.best).toMatchObject({ checksLeft: 2, timeMs: 100_000 });
	});

	it('takes a faster win at the same number of checks', async () => {
		const store = await make();
		await store.record('ada', playOf({ checksLeft: 2, timeMs: 100_000 }));
		const kept = await store.record('ada', playOf({ checksLeft: 2, timeMs: 40_000 }));

		expect(kept.best).toMatchObject({ checksLeft: 2, timeMs: 40_000 });
	});

	it('never loses a solve to a later loss on the same board', async () => {
		const store = await make();
		await store.record('ada', playOf({ checksLeft: 2 }));
		const kept = await store.record('ada', playOf({ outcome: 'lost', checksLeft: 0 }));

		expect(kept.best).toMatchObject({ checksLeft: 2 });
		expect(kept.plays).toBe(2);
	});

	it('keeps one player’s boards apart from another’s', async () => {
		const store = await make();
		await store.record('ada', playOf({ puzzle: board }));
		await store.record('bo', playOf({ puzzle: board }));
		await store.record('ada', playOf({ puzzle: other }));

		expect((await store.forUser('ada')).map((p) => p.puzzleId).sort()).toEqual(
			[board, other].sort()
		);
		expect(await store.forUser('bo')).toHaveLength(1);
	});

	it('hands back everything, which is what the standings fold over', async () => {
		const store = await make();
		await store.record('ada', playOf({ puzzle: board }));
		await store.record('bo', playOf({ puzzle: other }));

		expect(await store.all(100)).toHaveLength(2);
		expect(await store.all(1)).toHaveLength(1);
	});
}
