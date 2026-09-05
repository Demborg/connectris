import type { Day, PuzzleStore } from './ports';

/**
 * Remember what a puzzle store said, for as long as the answer cannot have changed.
 *
 * Today's board is one document that changes once a day, and every check re-reads it to
 * recover the answer key. Without this, a busy game costs a database read per press; with
 * it, a warm instance serves boards and grades checks without touching the database at
 * all. That is what makes a check free, and a free check is what makes scaling to zero
 * something to do fearlessly rather than to dread.
 *
 * Promises are cached rather than values, so a burst of first requests makes one query
 * instead of racing. A failed lookup is dropped rather than remembered — a store that is
 * briefly unreachable must not become permanently empty.
 */
export function cachePuzzles(inner: PuzzleStore): PuzzleStore {
	// One day's answers at a time. Rolling over drops yesterday's rather than growing.
	let cachedDay: Day | null = null;
	let answers = new Map<string, Promise<unknown>>();

	function forDay<T>(day: Day, key: string, ask: () => Promise<T>): Promise<T> {
		if (cachedDay !== day) {
			cachedDay = day;
			answers = new Map();
		}

		const known = answers.get(key) as Promise<T> | undefined;
		if (known) return known;

		const asked = ask().catch((reason: unknown) => {
			answers.delete(key);
			throw reason;
		});
		answers.set(key, asked);
		return asked;
	}

	return {
		scheduledFor: (day) => forDay(day, `on:${day}`, () => inner.scheduledFor(day)),
		published: (day, limit) => forDay(day, `to:${day}:${limit}`, () => inner.published(day, limit)),
		// Not cached: nothing in the request path asks by id, and an id carries no day to
		// expire against. Seeding and tooling use it, and they want the truth.
		byId: (id) => inner.byId(id)
	};
}
