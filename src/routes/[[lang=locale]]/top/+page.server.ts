import { placeOf, rank, TOP } from '$lib/server/progress';
import { HISTORY, ROSTER, stores } from '$lib/server/stores';
import type { PageServerLoad } from './$types';

/**
 * The standings.
 *
 * Two reads and a fold in process, which DESIGN.md's database note says is the right
 * shape at this size — "ranking at that size is fetch-a-puzzle's-runs-and-sort-in-process"
 * was written about exactly this page.
 *
 * Cut to the top of the list, plus your own row if you are below the cut. A top list that
 * showed everyone would stop being one, and a top list you cannot find yourself on is a
 * page that only serves whoever is already winning.
 */
export const load: PageServerLoad = async ({ locals }) => {
	const { players, progress } = stores();
	const [roster, history] = await Promise.all([players.all(ROSTER), progress.all(HISTORY)]);

	const standings = rank(roster, history);
	const me = locals.player ? placeOf(standings, locals.player.id) : 0;

	// The id never leaves the server — which row is yours is decided here and travels as a
	// flag, so the page can highlight it without the browser ever holding the id its
	// cookie protects.
	const listed = standings.slice(0, TOP).map((s, i) => ({
		place: i + 1,
		alias: s.alias,
		solved: s.solved,
		checksLeft: s.checksLeft,
		timeMs: s.timeMs,
		you: i + 1 === me
	}));

	return {
		listed,
		/** Your row, when it did not make the cut. Null when it did, or when it is empty. */
		mine: me > TOP ? { ...standings[me - 1], place: me, you: true } : null,
		of: standings.length
	};
};
