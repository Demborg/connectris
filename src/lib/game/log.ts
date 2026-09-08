/**
 * Local play log.
 *
 * Phase 0 had no backend, and the whole point of the prototype was to find out whether
 * the mechanics are fun — which means capturing enough to replay a run afterwards and to
 * retro-score it against metrics we have not committed to yet (moves in particular).
 * Everything here is deliberately cheap and lossy-on-failure: a full localStorage or a
 * private window must never break the game.
 *
 * What this browser has *achieved* no longer lives here. Bests and which boards are
 * solved are the server's answer now, because they are the same facts the standings are
 * built from and one of them being local was one of them being a second opinion. What is
 * left is the raw log, kept locally for the reason pin 10 gives: a run that failed to
 * post is still a run that was played.
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

/** Personal best per puzzle. Written by wins only — a loss has nothing to be best at. */
export type Best = Pick<Run, 'timeMs' | 'checksLeft' | 'moves' | 'checks'>;

/**
 * Which of two results is better, and the only ranking rule this game has.
 *
 * The axes are kept separate on purpose — there is no combined score — so "better" means
 * finishing with more checks in hand, or the same number of checks in less time. The
 * standings sort players by the same two axes in the same order, because a rule that
 * differed between "your best" and "who is ahead" would be two games.
 */
export function better(run: Best, than: Best | null | undefined): boolean {
	if (!than) return true;
	if (run.checksLeft !== than.checksLeft) return run.checksLeft > than.checksLeft;
	return run.timeMs < than.timeMs;
}

/** A run reduced to what a best is made of. */
export function bestOf(run: Run): Best {
	const { timeMs, checksLeft, moves, checks } = run;
	return { timeMs, checksLeft, moves, checks };
}

// v3: the budget tightened from six checks to four, so the most a win can now leave in hand
// is three. A v2 best holding four or five is unreachable and would sit on the end card as a
// target nobody can beat. Same reason v2 replaced v1, where runs recorded lives rather than
// checksLeft: a budget change invalidates the comparison, so it invalidates the key.
const RUNS_KEY = 'connectris:runs:v3';
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
