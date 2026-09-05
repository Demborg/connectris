import type { Clock, Day } from './ports';

/**
 * The game rolls over at midnight where its players are, not at midnight UTC.
 *
 * One zone rather than the visitor's own: a daily puzzle everyone gets at a different
 * moment is not the same puzzle, and comparing runs across a rollover boundary would be
 * comparing different days.
 */
export const ZONE = 'Europe/Stockholm';

/** `en-CA` is the locale whose short date format is already `YYYY-MM-DD`. */
const formatter = new Intl.DateTimeFormat('en-CA', { timeZone: ZONE });

export const systemClock: Clock = {
	today: () => formatter.format(new Date())
};

/** A clock that never moves, for tests and for seeding a schedule. */
export const fixedClock = (day: Day): Clock => ({ today: () => day });

/**
 * `n` days earlier. Date-only arithmetic in UTC, which has no hours to lose to a DST
 * change — the zone has already been applied by the time a `Day` exists.
 */
export function daysBefore(day: Day, n: number): Day {
	const d = new Date(`${day}T00:00:00Z`);
	d.setUTCDate(d.getUTCDate() - n);
	return d.toISOString().slice(0, 10);
}
