import puzzles from '$lib/data/puzzles.json';
import type { Puzzle } from '$lib/game/types';
import { systemClock } from './day';
import { memoryFeedback, memoryPuzzles, memoryRuns } from './memory';
import type { Day, PuzzleStore, Stores } from './ports';

/**
 * The one place that decides which adapter answers a port.
 *
 * Nothing else in the request path can see this file, which is what lets the same routes
 * run against memory in a test, against files on a laptop, and against a real database in
 * production. Keep the choosing here and the `if` count at one.
 */

/** How far back the picker reaches, and the window a check is allowed to grade in. */
export const BACKLOG = 30;

const boards = puzzles as Puzzle[];
const clock = systemClock;

// Runs and feedback outlive a day; the schedule does not. Rebuilding the whole set at
// midnight would throw away everything recorded before it.
const runs = memoryRuns();
const feedback = memoryFeedback();

let scheduled: { day: Day; store: PuzzleStore } | undefined;

/**
 * Boards are still the ones compiled into the bundle, and their schedule is derived from
 * today rather than stored — so the daily shape is real and testable before anything is
 * writing dates down.
 */
function puzzleStore(): PuzzleStore {
	const day = clock.today();
	if (scheduled?.day !== day) scheduled = { day, store: memoryPuzzles(boards, day) };
	return scheduled.store;
}

export function stores(): Stores {
	return { clock, puzzles: puzzleStore(), runs, feedback };
}
