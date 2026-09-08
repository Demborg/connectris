/**
 * What a run means afterwards: one player's record of one board, and the standings that
 * fall out of everyone's.
 *
 * Both are folds, and both live here rather than in an adapter. `foldRun` is performed by
 * three stores that must not disagree about what a personal best is, and `rank` is a
 * reduction the request path does in process — so neither is allowed to be a detail of
 * where the documents happen to be kept.
 */

import { better, bestOf, type Run } from '$lib/game/log';
import type { Player, Progress } from './ports';

/** One document per player per board, keyed the way every adapter keys it. */
export function progressKey(userId: string, puzzleId: string): string {
	return `${userId}__${puzzleId}`;
}

/**
 * Fold a finished run into a board record.
 *
 * A loss still counts as a play — that is what makes a board read as attempted rather
 * than untouched — and only a win can move the best.
 */
export function foldRun(prev: Progress | null, userId: string, run: Run, now: number): Progress {
	const best = run.outcome === 'won' ? bestOf(run) : null;

	return {
		userId,
		puzzleId: run.puzzle,
		plays: (prev?.plays ?? 0) + 1,
		best: best && better(best, prev?.best) ? best : (prev?.best ?? null),
		updatedAt: now
	};
}

export type Standing = {
	userId: string;
	alias: string;
	/** Boards won at least once. The first axis, and the one people actually feel. */
	solved: number;
	played: number;
	/** Across best runs only: checks still in hand, and how long they took. */
	checksLeft: number;
	timeMs: number;
};

/**
 * How much of the standings a page shows. Long enough that a family is all on it, short
 * enough that it stays a top list rather than a census.
 */
export const TOP = 20;

/**
 * The same two axes a personal best is judged on, applied to a whole player: more boards
 * solved, then more checks left across those solves, then less time. Ties break on the
 * name, so the order is stable between requests rather than reshuffling under whoever
 * happened to play last.
 */
function compare(a: Standing, b: Standing): number {
	return (
		b.solved - a.solved ||
		b.checksLeft - a.checksLeft ||
		a.timeMs - b.timeMs ||
		a.alias.localeCompare(b.alias)
	);
}

/**
 * Every registered player, ranked.
 *
 * Computed from the progress documents every time it is asked for, rather than kept as a
 * running total on each player. A counter would have to be incremented inside the same
 * transaction that records a solve, and on the night it drifted there would be no way to
 * tell — whereas a fold over the source of truth is wrong only if the source is.
 *
 * That it can be a fold at all is the scale bet DESIGN.md already made about this
 * database: ten players is a surprising day and thirty boards is the whole window, so
 * this reduces hundreds of documents, not millions.
 *
 * Registered-but-unplayed players are on the list at the bottom rather than absent: a
 * standings page you registered for and cannot find yourself on reads as broken, and
 * "0 solved" is the honest answer to where you are. Progress belonging to no registered
 * player — a browser that played before registration existed and never claimed a name —
 * is skipped rather than shown as an anonymous row. It is not lost: registering adopts
 * that id, and its boards come with it.
 */
export function rank(players: Player[], progress: Progress[]): Standing[] {
	const standings = new Map<string, Standing>(
		players.map((p) => [
			p.id,
			{ userId: p.id, alias: p.alias, solved: 0, played: 0, checksLeft: 0, timeMs: 0 }
		])
	);

	for (const board of progress) {
		const standing = standings.get(board.userId);
		if (!standing) continue;

		standing.played += board.plays;
		if (!board.best) continue;
		standing.solved += 1;
		standing.checksLeft += board.best.checksLeft;
		standing.timeMs += board.best.timeMs;
	}

	return [...standings.values()].sort(compare);
}

/** Where one player sits in a ranked list, counting from one. Zero if they are not on it. */
export function placeOf(standings: Standing[], userId: string): number {
	return standings.findIndex((s) => s.userId === userId) + 1;
}
