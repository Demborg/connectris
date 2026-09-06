import { displayName, userId } from '$lib/user';
import type { Run } from './log';
import type { Difficulty } from './types';

/**
 * Where a finished run goes. Best-effort by design: a run that fails to send is still a
 * run that was played, and the local log already has it.
 */
export type Reporter = (id: string, run: Run) => void;

/** Sends nothing. What a session gets when nobody asked for the run to go anywhere. */
export const noReporter: Reporter = () => {};

export function httpReporter(send: typeof fetch = fetch): Reporter {
	return (id, run) => {
		void send('/api/runs', {
			method: 'POST',
			headers: { 'content-type': 'application/json' },
			body: JSON.stringify({ ...run, id, userId: userId(), displayName: displayName() })
		}).catch(() => {
			// A lost run is a lost data point, not a lost game. Pin 10 keeps the local copy
			// precisely so this can be allowed to fail quietly.
		});
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
			body: JSON.stringify({ ...answers, runId, puzzleId, userId: userId() })
		}).catch(() => {
			// An opinion that did not arrive is not worth interrupting a game over.
		});
	};
}
