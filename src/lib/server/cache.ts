import type { PlayerStore, PuzzleStore } from './ports';

/**
 * Remember what a store said, briefly.
 *
 * The board list is read on every page load and again on every check, to recover the
 * answer key. Without this a busy game costs a database read per press; with it a warm
 * instance serves boards and grades checks without touching the database at all. That is
 * what makes a check free, and a free check is what makes scaling to zero something to do
 * without thinking about it.
 *
 * The window is short because the set changes when a board is added, and waiting a minute
 * to see it is fine while waiting for an instance to recycle is not. It is also what
 * bounds how late a warm instance is to the day rolling over: the answer holds `liveOn <=
 * today` from when it was asked, so a new board is at most one window behind midnight.
 *
 * Promises are cached rather than values, so a burst of first requests makes one query
 * instead of racing. A failed lookup is dropped rather than remembered — a store that is
 * briefly unreachable must not become permanently empty.
 */

export const TTL_MS = 60_000;

type Window = {
	fresh<T>(key: string, ask: () => Promise<T>): Promise<T>;
	forget(): void;
};

function window(ttlMs: number, now: () => number): Window {
	let held: { at: number; answers: Map<string, Promise<unknown>> } | null = null;

	return {
		fresh<T>(key: string, ask: () => Promise<T>): Promise<T> {
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
		},
		forget() {
			held = null;
		}
	};
}

export function cachePuzzles(inner: PuzzleStore, ttlMs = TTL_MS, now = Date.now): PuzzleStore {
	const held = window(ttlMs, now);
	return { live: (limit) => held.fresh(`live:${limit}`, () => inner.live(limit)) };
}

/**
 * Players, cached the same way and for a sharper reason: every request now resolves who
 * is asking, so an uncached `byId` would put a database read in front of every page load
 * and every check — undoing exactly what the puzzle cache buys.
 *
 * A successful registration drops the whole window rather than patching an entry into it.
 * The player who just registered is redirected straight into the game, so their own next
 * request must find them; and the standings, which read `all`, would otherwise be up to a
 * minute late in noticing a new name. Registration happens once per player, so throwing
 * the window away costs one re-read of a small collection.
 *
 * A miss is cached like anything else — a cookie left over from a wiped database would
 * otherwise re-ask on every request — and dropping the window on registration is what
 * makes that safe: the id a miss was recorded for is the id registration then claims.
 */
export function cachePlayers(inner: PlayerStore, ttlMs = TTL_MS, now = Date.now): PlayerStore {
	const held = window(ttlMs, now);

	return {
		async register(player) {
			const outcome = await inner.register(player);
			if (outcome === 'ok') held.forget();
			return outcome;
		},
		byId: (id) => held.fresh(`id:${id}`, () => inner.byId(id)),
		all: (limit) => held.fresh(`all:${limit}`, () => inner.all(limit))
	};
}
