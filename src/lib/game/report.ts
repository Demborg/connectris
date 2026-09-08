import type { Best, Run } from './log';
import type { Difficulty } from './types';

/**
 * What the server says back about a finished run: this player's best on that board now
 * that this run is in it, and where they stand once it counted.
 *
 * `place` is null when the run was a loss — nothing moved, so nothing was recomputed —
 * and `of` is how many players there are to be one of.
 */
export type Recorded = {
	best: Best | null;
	place: number | null;
	of: number | null;
	top?: number;
};

/**
 * Where a finished run goes.
 *
 * Best-effort in the direction that matters: a run that fails to send is still a run that
 * was played, and the local log already has it. It is no longer *silent*, though — the
 * answer carries the two facts only the server can know, and the end card shows them if
 * they arrive. Nothing waits for them.
 */
export type Reporter = (id: string, run: Run) => Promise<Recorded | null>;

/** Sends nothing. What a session gets when nobody asked for the run to go anywhere. */
export const noReporter: Reporter = async () => null;

export function httpReporter(send: typeof fetch = fetch): Reporter {
	return async (id, run) => {
		try {
			// Who played is the cookie's answer, not the body's — see lib/server/identity.
			// `credentials` is same-origin by default and this is a same-origin path, so
			// the cookie rides along without being asked for.
			const res = await send('/api/runs', {
				method: 'POST',
				headers: { 'content-type': 'application/json' },
				body: JSON.stringify({ ...run, id })
			});
			return res.ok ? ((await res.json()) as Recorded) : null;
		} catch {
			// A lost run is a lost data point, not a lost game. Pin 10 keeps the local copy
			// precisely so this can be allowed to fail quietly.
			return null;
		}
	};
}

/** What the end screen can be told. Every field optional: the screen is skippable. */
export type Answers = {
	difficulty: Difficulty | null;
	fair: boolean | null;
	comment: string;
};

export type AnswerReporter = (answers: Answers) => void;

export const noAnswers: AnswerReporter = () => {};

/**
 * Send what a player said about a board.
 *
 * Called on every tap rather than on a submit, so a completed form arrives as a series of
 * partial ones. The store keys by run, so the last one wins and someone who answers the
 * first question and leaves has still told us the thing most worth knowing.
 */
export function httpAnswers(
	runId: string,
	puzzleId: string,
	send: typeof fetch = fetch
): AnswerReporter {
	return (answers) => {
		void send('/api/feedback', {
			method: 'POST',
			headers: { 'content-type': 'application/json' },
			body: JSON.stringify({ ...answers, runId, puzzleId })
		}).catch(() => {
			// An opinion that did not arrive is not worth interrupting a game over.
		});
	};
}
