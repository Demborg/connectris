import { error, json } from '@sveltejs/kit';
import { requirePlayer } from '$lib/server/identity';
import { parseRun, runRecord } from '$lib/server/parse';
import { placeOf, rank, TOP } from '$lib/server/progress';
import { HISTORY, ROSTER, stores } from '$lib/server/stores';
import type { RequestHandler } from './$types';

/**
 * Record a finished run.
 *
 * Two writes, not one: the run itself, kept whole so it can be replayed and retro-scored,
 * and the fold of it into this player's record of that board, which is what the boards
 * page and the standings are read from. Both are keyed rather than appended, so the
 * client's best-effort retry lands on the same two documents.
 *
 * It answers with something now, where it used to answer 204. The end card has two things
 * to say that only the server knows — whether this run is a personal best, and where the
 * player now stands — and both are already in hand here. Sending them back saves the card
 * two round trips at the exact moment the player is looking at it.
 */
export const POST: RequestHandler = async ({ request, locals }) => {
	const player = requirePlayer(locals);
	const body = await request.json().catch(() => error(400, 'Expected JSON'));
	const run = parseRun(body);

	const { runs, progress, players } = stores();
	const [, board] = await Promise.all([
		runs.record(runRecord(run, player)),
		progress.record(player.id, run)
	]);

	// The standings, for the one line the end card shows. A losing run cannot have changed
	// anyone's place, so it does not pay for the fold.
	if (run.outcome !== 'won') return json({ best: board.best, place: null, of: null });

	const [roster, history] = await Promise.all([players.all(ROSTER), progress.all(HISTORY)]);
	const standings = rank(roster, history);

	return json({
		best: board.best,
		// Only worth saying when it is a position rather than a participation. Below the
		// cut the card says nothing and the standings page is a tap away.
		place: placeOf(standings, player.id) || null,
		of: standings.length,
		top: TOP
	});
};
