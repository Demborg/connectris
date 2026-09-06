/**
 * What the game needs from the outside world, and nothing about who provides it.
 *
 * Every one of these has at least three implementations — memory, files, Firestore — and
 * the rule that keeps them honest is that this file never mentions any of them. If a type
 * here starts describing how a store works rather than what it is for, the seam has
 * leaked.
 */

import type { Run } from '$lib/game/log';
import type { Difficulty, Puzzle } from '$lib/game/types';

/** A finished run, as recorded. The local play log plus who played it. */
export type RunRecord = Run & {
	id: string;
	userId: string;
	/** Set only for an invited tester; everyone else is an anonymous id. */
	displayName: string | null;
};

/**
 * What a player said about a board once it was over. Every field is optional because the
 * screen it comes from is skippable: someone who answers the first question and leaves
 * has still told us the thing worth knowing.
 */
export type Feedback = {
	runId: string;
	userId: string;
	puzzleId: string;
	difficulty: Difficulty | null;
	fair: boolean | null;
	comment: string;
};

export type PuzzleStore = {
	/**
	 * The boards in play, **most recently published first** — so `live(n)[0]` is today's
	 * board and the rest are the days behind it.
	 *
	 * Newest-first rather than the old easiest-first file order, because the nightly job
	 * adds a board a day and a list that grows at the far end from the one being read is
	 * a list whose new entries fall out of the window before anyone sees them.
	 *
	 * "Published" means dated on or before today, which is also why a board is never
	 * missing: one stays live until a later one is due, so a night that generates nothing
	 * leaves yesterday's board up rather than leaving a hole.
	 *
	 * This is the only way the request path learns a board exists — there is no lookup by
	 * id beside it, deliberately, so a board scheduled for next week cannot be reached by
	 * guessing its URL.
	 */
	live(limit: number): Promise<Puzzle[]>;
};

export type RunStore = {
	record(run: RunRecord): Promise<void>;
};

/** Keyed by run, so a partial answer survives and a retry is not a second opinion. */
export type FeedbackStore = {
	record(feedback: Feedback): Promise<void>;
};

export type Stores = {
	puzzles: PuzzleStore;
	runs: RunStore;
	feedback: FeedbackStore;
};
