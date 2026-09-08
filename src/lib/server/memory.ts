import type { Run } from '$lib/game/log';
import type { Puzzle } from '$lib/game/types';
import type {
	Feedback,
	FeedbackStore,
	Player,
	PlayerStore,
	Progress,
	ProgressStore,
	PuzzleStore,
	RunRecord,
	RunStore
} from './ports';
import { foldRun, progressKey } from './progress';

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
	return {
		live: async (limit, language) =>
			newestFirst.filter((p) => p.language === language).slice(0, limit)
	};
}

/**
 * Registered players, for the life of the process.
 *
 * The claim is atomic for free here — JavaScript does not interleave the check and the
 * write — which is exactly the property the other two adapters have to work for.
 */
export function memoryPlayers(): PlayerStore {
	const byId = new Map<string, Player>();
	const byHandle = new Map<string, string>();

	return {
		async register(player) {
			if (byHandle.has(player.handle)) return 'taken';
			byHandle.set(player.handle, player.id);
			byId.set(player.id, player);
			return 'ok';
		},
		async byId(id) {
			return byId.get(id) ?? null;
		},
		async all(limit) {
			return [...byId.values()].slice(0, limit);
		}
	};
}

export function memoryProgress(now: () => number = Date.now): ProgressStore {
	const boards = new Map<string, Progress>();

	return {
		async record(userId: string, run: Run) {
			const key = progressKey(userId, run.puzzle);
			const folded = foldRun(boards.get(key) ?? null, userId, run, now());
			boards.set(key, folded);
			return folded;
		},
		async forUser(userId) {
			return [...boards.values()].filter((p) => p.userId === userId);
		},
		async all(limit) {
			return [...boards.values()].slice(0, limit);
		}
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
