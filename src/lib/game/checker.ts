import { CHECKS, check, deal } from './engine';
import type { Checker, Group, Puzzle, Row } from './types';

/**
 * Grade against a puzzle held in this process.
 *
 * The offline half of the seam. The tests use it, and so does a dev machine with no
 * backend — the game has to stay playable without one, or the port is decoration.
 *
 * Stateless, deliberately, because the remote half has to be: the rows handed in are the
 * rows still in play, so both what cleared and what is still unfound are derivable from
 * the arrangement and the key. Nothing has to remember a game between presses, which is
 * what keeps a check cheap enough to pay for on every one.
 */
export function localChecker(puzzle: Puzzle): Checker {
	const { answer } = deal(puzzle);
	const groupOf = (row: Row): Group => puzzle.groups.find((g) => g.id === answer.get(row[0].id))!;

	return async (rows, checksUsed) => {
		const { locked, correctCount } = check(rows, answer);
		const cleared = rows.slice(0, locked).map(groupOf);

		const unfound = new Set(rows.flat().map((t) => answer.get(t.id)));
		for (const g of cleared) unfound.delete(g.id);

		// A category is only named once the run can no longer be won. Pin 4 pays for the
		// count feedback by never saying *where* — revealing a missed row while there are
		// checks left would say exactly that.
		const solved = locked === rows.length;
		const over = solved || checksUsed >= CHECKS;
		const missed = over && !solved ? puzzle.groups.filter((g) => unfound.has(g.id)) : [];

		return { locked, correctCount, cleared, missed };
	};
}
