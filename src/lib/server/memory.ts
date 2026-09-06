import type { Puzzle } from '$lib/game/types';
import type { Feedback, FeedbackStore, PuzzleStore, RunRecord, RunStore } from './ports';

/**
 * Puzzles from a list held in memory.
 *
 * This is what a dev machine with no cloud project plays against, so it is not a stub —
 * it is the reference reading of what the port means, and the shared contract suite holds
 * every other adapter to whatever this does.
 *
 * There is no calendar here and there does not need to be one. The port asks for published
 * boards newest first, so a list in publication order answers it: the last board written
 * down is today's, and anything past `published` is scheduled but not yet due. Dates are
 * how Firestore answers that question, not what the question is.
 *
 * @param schedule Boards in publication order, oldest first.
 * @param published How many of them are live. The rest are dated ahead and unreachable.
 */
export function memoryPuzzles(schedule: Puzzle[], published = schedule.length): PuzzleStore {
	const newestFirst = schedule.slice(0, published).reverse();
	return { live: async (limit) => newestFirst.slice(0, limit) };
}

/** Runs kept for the life of the process. Readable, so a test can assert what landed. */
export function memoryRuns(): RunStore & { all(): RunRecord[] } {
	const runs = new Map<string, RunRecord>();
	return {
		record: async (run) => void runs.set(run.id, run),
		all: () => [...runs.values()]
	};
}

export function memoryFeedback(): FeedbackStore & { all(): Feedback[] } {
	const feedback = new Map<string, Feedback>();
	return {
		record: async (f) => void feedback.set(f.runId, f),
		all: () => [...feedback.values()]
	};
}
