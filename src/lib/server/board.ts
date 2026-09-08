import { error } from '@sveltejs/kit';
import { boardOf } from '$lib/game/engine';
import type { Best } from '$lib/game/log';
import type { Locale } from '$lib/i18n';
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
 *
 * Null means this language has nothing published yet, which is an ordinary state and not a
 * failure: Swedish starts empty and fills up a board a night. It used to be a 503, so the
 * first thing anyone following a Swedish link saw was an error page. A named board that
 * does not exist is still a 404 — that is a wrong URL, not an empty language.
 */
export async function gameData(locale: Locale, wanted?: string) {
	const live = await stores().puzzles.live(BACKLOG, locale);

	const puzzle = wanted ? live.find((p) => p.id === wanted) : live[0];
	if (wanted && !puzzle) error(404, 'No such puzzle');
	if (!puzzle) return null;

	return {
		board: boardOf(puzzle),
		backlog: live.map(({ id, name }) => ({ id, name }))
	};
}

/** A board on the picker, and what this player has done with it. */
export type ListedBoard = {
	id: string;
	name: string;
	played: boolean;
	best: Best | null;
};

/**
 * Every board reachable right now, newest first — so the head of the list is today's,
 * each carrying what the player asking has done with it.
 *
 * Separate from `gameData` because the boards page wants the list and nothing else, and
 * dealing a board it will never show is work a cold start pays for. Same window and same
 * rule about what is reachable: this cannot name a board the game would refuse to load.
 *
 * The marks used to be read from localStorage on hydration, which made them a second
 * opinion: the standings counted a board solved from one store while the picker decided
 * from another, and a browser that had been cleared disagreed with both. They are joined
 * here instead, so the page ships complete in the first response and says the same thing
 * the standings do — including on a phone that has never seen this board before.
 *
 * No dates. When a board is due is a fact about the schedule rather than about the board,
 * and it is kept off `Puzzle` for that reason — so the list carries its own order and the
 * page says "today" by position.
 */
export async function boardList(
	userId: string,
	locale: Locale
): Promise<{ boards: ListedBoard[] }> {
	const { puzzles, progress } = stores();
	const [live, played] = await Promise.all([
		puzzles.live(BACKLOG, locale),
		progress.forUser(userId)
	]);

	// No 503 when a language is simply empty. Swedish starts with nothing published, and a
	// picker that fails outright would make the language look broken rather than new; the
	// page says so in words instead. `gameData` still refuses, because a game route with no
	// board has nothing to render.
	const mine = new Map(played.map((p) => [p.puzzleId, p]));

	return {
		boards: live.map(({ id, name }) => {
			const record = mine.get(id);
			return { id, name, played: Boolean(record), best: record?.best ?? null };
		})
	};
}
