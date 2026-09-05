/**
 * Local play log.
 *
 * Phase 0 has no backend, but the whole point of the prototype is to find out whether
 * the mechanics are fun — which means capturing enough to replay a run afterwards and
 * to retro-score it against metrics we have not committed to yet (moves in particular).
 * Everything here is deliberately cheap and lossy-on-failure: a full localStorage or a
 * private window must never break the game.
 */

export type GameEvent =
	| { t: number; type: 'start'; puzzle: string }
	| { t: number; type: 'swapTiles'; a: [number, number]; b: [number, number] }
	| { t: number; type: 'swapRows'; a: number; b: number }
	| { t: number; type: 'check'; locked: number; correctCount: number; left: number }
	| { t: number; type: 'end'; outcome: 'won' | 'lost' };

/** An event minus its timestamp. Distributes over the union, unlike a bare `Omit`. */
export type EventInput = GameEvent extends infer E
	? E extends GameEvent
		? Omit<E, 't'>
		: never
	: never;

export type Run = {
	puzzle: string;
	startedAt: number;
	outcome: 'won' | 'lost';
	timeMs: number;
	checksLeft: number;
	moves: number;
	checks: number;
	events: GameEvent[];
};

/** Personal best per puzzle — the local stand-in for the leaderboard. */
export type Best = Pick<Run, 'timeMs' | 'checksLeft' | 'moves' | 'checks'>;

// v3: the budget tightened from six checks to four, so the most a win can now leave in hand
// is three. A v2 best holding four or five is unreachable and would sit on the end card as a
// target nobody can beat. Same reason v2 replaced v1, where runs recorded lives rather than
// checksLeft: a budget change invalidates the comparison, so it invalidates the key.
const RUNS_KEY = 'connectris:runs:v3';
const BEST_KEY = 'connectris:best:v3';
const MAX_RUNS = 50;

function read<T>(key: string, fallback: T): T {
	try {
		const raw = localStorage.getItem(key);
		return raw ? (JSON.parse(raw) as T) : fallback;
	} catch {
		return fallback;
	}
}

function write(key: string, value: unknown): void {
	try {
		localStorage.setItem(key, JSON.stringify(value));
	} catch {
		// Full, blocked, or private mode. Losing the log is not worth breaking a game over.
	}
}

export function saveRun(run: Run): void {
	write(RUNS_KEY, [run, ...read<Run[]>(RUNS_KEY, [])].slice(0, MAX_RUNS));
}

export function loadRuns(): Run[] {
	return read<Run[]>(RUNS_KEY, []);
}

export function loadBests(): Record<string, Best> {
	return read<Record<string, Best>>(BEST_KEY, {});
}

/**
 * Records a personal best. The axes are kept separate on purpose — there is no combined
 * score, so "better" here means finishing with more checks in hand, or the same number
 * of checks in less time.
 */
export function recordBest(puzzle: string, run: Best): Best {
	const bests = loadBests();
	const prev = bests[puzzle];
	const better =
		!prev ||
		run.checksLeft > prev.checksLeft ||
		(run.checksLeft === prev.checksLeft && run.timeMs < prev.timeMs);
	if (better) {
		bests[puzzle] = run;
		write(BEST_KEY, bests);
	}
	return bests[puzzle];
}
