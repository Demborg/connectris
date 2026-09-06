/**
 * Days, as the schedule counts them.
 *
 * UTC, and deliberately not the player's timezone. A board is served by being the most
 * recent one dated on or before today, so it stays up until the next one is due — which
 * means the only thing the timezone decides is what hour the swap happens, not whether
 * there is a board. Picking UTC keeps that hour the same for everyone, keeps it the same
 * as the one Cloud Scheduler and Firestore count in, and leaves nothing to get wrong
 * twice a year.
 *
 * A date is a `YYYY-MM-DD` string rather than a `Date` because that is what it is: the
 * name of a day, with no instant inside it. It also sorts and compares as a string, which
 * is what lets Firestore answer `liveOn <= today` from a single-field index.
 */

/** The day now falls on. */
export function today(now: Date = new Date()): string {
	return now.toISOString().slice(0, 10);
}

/** `days` after `day` — negative to go back. */
export function shift(day: string, days: number): string {
	const at = new Date(`${day}T00:00:00Z`);
	at.setUTCDate(at.getUTCDate() + days);
	return today(at);
}
