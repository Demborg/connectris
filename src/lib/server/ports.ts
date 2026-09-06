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
	 * The boards in play, in the order they should be met — which is roughly easiest
	 * first, the order they are written down in.
	 *
	 * This is the only way the request path learns a board exists. Whatever the pipeline
	 * is proposing lives somewhere else entirely, so there is no way for an unfinished
	 * board to reach a player by accident.
	 */
	live(limit: number): Promise<Puzzle[]>;
	byId(id: string): Promise<Puzzle | null>;
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
