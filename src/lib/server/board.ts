import { error } from '@sveltejs/kit';
import { boardOf } from '$lib/game/engine';
import { BACKLOG, stores } from './stores';

/**
 * What both game routes need: a dealt board with nothing attached that grades it, and the
 * list of boards reachable from it.
 *
 * One query answers both questions. The newest published board is today's when there is
 * one, and the same list is the only thing the picker may reach into — a board scheduled
 * for tomorrow is in neither, whoever wrote it there.
 */
export async function gameData(wanted?: string) {
	const { puzzles, clock } = stores();
	const published = await puzzles.published(clock.today(), BACKLOG);

	const puzzle = wanted ? published.find((p) => p.id === wanted) : published[0];
	if (wanted && !puzzle) error(404, 'No such puzzle');
	if (!puzzle) error(503, 'No puzzle has been published yet');

	return {
		board: boardOf(puzzle),
		backlog: published.map(({ id, name }) => ({ id, name }))
	};
}
