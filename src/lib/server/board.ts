import { error } from '@sveltejs/kit';
import { boardOf } from '$lib/game/engine';
import { BACKLOG, stores } from './stores';

/**
 * What both game routes need: a dealt board with nothing attached that grades it, and the
 * list of boards reachable from it.
 *
 * One query answers both questions, and the same list is the only thing the picker may
 * reach into — so whatever the pipeline is still arguing with itself about cannot be
 * navigated to, because it is not in here. Nor can tomorrow's board, which by then is
 * written and waiting in the same collection: the store only ever answers with days that
 * have arrived, so `live[0]` is today's and everything after it is a day already played.
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

/**
 * Every board reachable right now, newest first — so the head of the list is today's.
 *
 * Separate from `gameData` because the boards page wants the list and nothing else, and
 * dealing a board it will never show is work a cold start pays for. Same window and same
 * rule about what is reachable: this cannot name a board the game would refuse to load.
 *
 * No dates. When a board is due is a fact about the schedule rather than about the board,
 * and it is kept off `Puzzle` for that reason — so the list carries its own order and the
 * page says "today" by position.
 */
export async function boardList() {
	const live = await stores().puzzles.live(BACKLOG);
	if (!live.length) error(503, 'No puzzles yet');

	return { boards: live.map(({ id, name }) => ({ id, name })) };
}
