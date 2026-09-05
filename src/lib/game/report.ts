import { displayName, userId } from '$lib/user';
import type { Run } from './log';

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
