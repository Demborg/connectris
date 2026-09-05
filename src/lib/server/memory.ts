import type { Puzzle } from '$lib/game/types';
import { daysBefore } from './day';
import type { Day, Feedback, FeedbackStore, PuzzleStore, RunRecord, RunStore } from './ports';

/**
 * Give a list of boards consecutive days ending on `today`, newest last.
 *
 * Newest last is the order the pipeline appends in, so "export a board" reads as
 * "schedule it next" without anything having to renumber.
 */
export function scheduleEndingToday(puzzles: Puzzle[], today: Day): Map<Day, Puzzle> {
	const last = puzzles.length - 1;
	return new Map(puzzles.map((p, i) => [daysBefore(today, last - i), p]));
}

/**
 * Puzzles from a list held in memory.
 *
 * This is what a dev machine with no cloud project plays against, so it is not a stub —
 * it is the reference implementation of what the port means, and the shared contract
 * suite holds the real adapter to whatever this does.
 */
export function memoryPuzzles(puzzles: Puzzle[], today: Day): PuzzleStore {
	const byDay = scheduleEndingToday(puzzles, today);
	const byId = new Map(puzzles.map((p) => [p.id, p]));

	return {
		scheduledFor: async (day) => byDay.get(day) ?? null,
		byId: async (id) => byId.get(id) ?? null,
		published: async (day, limit) =>
			[...byDay.entries()]
				.filter(([d]) => d <= day)
				.sort(([a], [b]) => b.localeCompare(a))
				.slice(0, limit)
				.map(([, p]) => p)
	};
}

/** Runs kept for the life of the process. Readable, so a test can assert on what landed. */
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
