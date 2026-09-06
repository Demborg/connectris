import type { PuzzleStore } from './ports';

/**
 * Remember what a puzzle store said, briefly.
 *
 * The board list is read on every page load and again on every check, to recover the
 * answer key. Without this a busy game costs a database read per press; with it a warm
 * instance serves boards and grades checks without touching the database at all. That is
 * what makes a check free, and a free check is what makes scaling to zero something to do
 * without thinking about it.
 *
 * The window is short because the set changes when a board is added, and waiting a minute
 * to see it is fine while waiting for an instance to recycle is not.
 *
 * Promises are cached rather than values, so a burst of first requests makes one query
 * instead of racing. A failed lookup is dropped rather than remembered — a store that is
 * briefly unreachable must not become permanently empty.
 */
export function cachePuzzles(inner: PuzzleStore, ttlMs = 60_000, now = Date.now): PuzzleStore {
	let held: { at: number; answers: Map<string, Promise<unknown>> } | null = null;

	function fresh<T>(key: string, ask: () => Promise<T>): Promise<T> {
		const at = now();
		if (!held || at - held.at > ttlMs) held = { at, answers: new Map() };

		const known = held.answers.get(key) as Promise<T> | undefined;
		if (known) return known;

		const answers = held.answers;
		const asked = ask().catch((reason: unknown) => {
			answers.delete(key);
			throw reason;
		});
		answers.set(key, asked);
		return asked;
	}

	return {
		live: (limit) => fresh(`live:${limit}`, () => inner.live(limit)),
		byId: (id) => fresh(`id:${id}`, () => inner.byId(id))
	};
}
