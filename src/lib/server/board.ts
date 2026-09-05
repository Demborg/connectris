import { error } from '@sveltejs/kit';
import { boardOf } from '$lib/game/engine';
import { BACKLOG, stores } from './stores';

/**
 * What both game routes need: a dealt board with nothing attached that grades it, and the
 * list of boards reachable from it.
 *
 * One query answers both questions, and the same list is the only thing the picker may
 * reach into — so whatever the pipeline is still arguing with itself about cannot be
 * navigated to, because it is not in here.
 */
export async function gameData(wanted?: string) {
	const live = await stores().puzzles.live(BACKLOG);

	const puzzle = wanted ? live.find((p) => p.id === wanted) : live[0];
	if (wanted && !puzzle) error(404, 'No such puzzle');
	if (!puzzle) error(503, 'No puzzles yet');

	return {
		board: boardOf(puzzle),
		backlog: live.map(({ id, name }) => ({ id, name }))
	};
}
