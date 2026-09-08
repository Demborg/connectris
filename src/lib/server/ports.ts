/**
 * What the game needs from the outside world, and nothing about who provides it.
 *
 * Every one of these has at least three implementations — memory, files, Firestore — and
 * the rule that keeps them honest is that this file never mentions any of them. If a type
 * here starts describing how a store works rather than what it is for, the seam has
 * leaked.
 */

import type { Best, Run } from '$lib/game/log';
import type { Difficulty, Puzzle } from '$lib/game/types';

/**
 * Someone who has registered.
 *
 * Not an account: there is no password and nothing is proved. What registering buys is a
 * name attached to a browser, held server-side, so a run, an opinion and a place on the
 * standings all belong to the same someone and that someone is legible in a list.
 *
 * `alias` is what they typed and what is shown. `handle` is the same thing folded to a
 * comparison key, and is the field uniqueness is enforced on — two players called "Ada"
 * and "ada" are one name in a top list, so the store refuses the second.
 */
export type Player = {
	id: string;
	alias: string;
	handle: string;
	registeredAt: number;
};

/** A finished run, as recorded. The local play log plus who played it. */
export type RunRecord = Run & {
	id: string;
	userId: string;
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

/**
 * One player's history with one board.
 *
 * The projection that makes both questions this app now asks cheap: which boards have I
 * played, and who is ahead. Derived from runs, but kept rather than recomputed — a run
 * log is append-only and unbounded, and "did this player solve this board" should not
 * cost a scan of it. One document per player per board, so replaying a board revises the
 * record instead of adding to it, and a retried post lands on the same key.
 *
 * `best` is only ever written by a win, so `solved` is `best !== null` — kept as one
 * field rather than two, because two could disagree.
 */
export type Progress = {
	userId: string;
	puzzleId: string;
	/** Wins and losses both. A board that was played is no longer a board you have not. */
	plays: number;
	best: Best | null;
	updatedAt: number;
};

export type PlayerStore = {
	/**
	 * Claim an alias. Answers `taken` rather than throwing, because a name already in use
	 * is an ordinary thing for a registration form to say back to someone.
	 *
	 * Claiming has to be atomic against another registration of the same handle: this is
	 * the one write in the app where two requests racing produce a wrong answer rather
	 * than a repeated one.
	 */
	register(player: Player): Promise<'ok' | 'taken'>;
	byId(id: string): Promise<Player | null>;
	/** Everyone, for putting names on the standings. Small by construction. */
	all(limit: number): Promise<Player[]>;
};

export type RunStore = {
	record(run: RunRecord): Promise<void>;
};

/** Keyed by run, so a partial answer survives and a retry is not a second opinion. */
export type FeedbackStore = {
	record(feedback: Feedback): Promise<void>;
};

export type ProgressStore = {
	/**
	 * Fold a finished run into this player's record of that board, and answer with the
	 * record as it now stands — which is how the end card learns whether the run just
	 * played is a personal best.
	 *
	 * Read-modify-write, so it must be atomic per key: two runs finishing at once must
	 * not lose a play between them.
	 */
	record(userId: string, run: Run): Promise<Progress>;
	/** One player's boards. Bounded by how many boards they have played. */
	forUser(userId: string): Promise<Progress[]>;
	/** Everything, for the standings. `rank` carries why reading it all is affordable. */
	all(limit: number): Promise<Progress[]>;
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

export type Stores = {
	players: PlayerStore;
	puzzles: PuzzleStore;
	progress: ProgressStore;
	runs: RunStore;
	feedback: FeedbackStore;
};
