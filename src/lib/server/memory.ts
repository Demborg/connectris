import type { Puzzle } from '$lib/game/types';
import type { Feedback, FeedbackStore, PuzzleStore, RunRecord, RunStore } from './ports';

/**
 * Puzzles from a list held in memory.
 *
 * This is what a dev machine with no cloud project plays against, so it is not a stub —
 * it is the reference reading of what the port means, and the shared contract suite holds
 * every other adapter to whatever this does.
 */
export function memoryPuzzles(puzzles: Puzzle[]): PuzzleStore {
	const byId = new Map(puzzles.map((p) => [p.id, p]));

	return {
		live: async (limit) => puzzles.slice(0, limit),
		byId: async (id) => byId.get(id) ?? null
	};
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
