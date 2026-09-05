/**
 * What the game needs from the outside world, and nothing about who provides it.
 *
 * Every one of these has at least two implementations — an in-memory one the tests and a
 * backendless dev machine use, and a real one — and the rule that keeps them honest is
 * that this file never mentions either. If a type here starts describing how a store
 * works rather than what it is for, the seam has leaked.
 */

import type { Run } from '$lib/game/log';
import type { Puzzle } from '$lib/game/types';

/** A calendar day in the game's own timezone, as `YYYY-MM-DD`. */
export type Day = string;

/** A finished run, as recorded. The local play log plus who played it. */
export type RunRecord = Run & {
	id: string;
	userId: string;
	/** Set only for an invited tester; everyone else is an anonymous id. */
	displayName: string | null;
};

/** How the board landed. Three answers, because a fourth would cost more than it earns. */
export type Difficulty = 'easy' | 'right' | 'hard';

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
	/** The board scheduled for a day, if one is. */
	scheduledFor(day: Day): Promise<Puzzle | null>;
	/** Boards already published on or before `day`, newest first. */
	published(day: Day, limit: number): Promise<Puzzle[]>;
	byId(id: string): Promise<Puzzle | null>;
};

export type RunStore = {
	record(run: RunRecord): Promise<void>;
};

/** Keyed by run, so a partial answer survives and a retry is not a second opinion. */
export type FeedbackStore = {
	record(feedback: Feedback): Promise<void>;
};

/** Injected rather than read off the system, so a test can decide what day it is. */
export type Clock = {
	today(): Day;
};

export type Stores = {
	puzzles: PuzzleStore;
	runs: RunStore;
	feedback: FeedbackStore;
	clock: Clock;
};
