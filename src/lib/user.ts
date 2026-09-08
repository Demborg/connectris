/**
 * What is left of identity in the browser.
 *
 * Who is playing is the server's answer now: registering mints an id, sets it as an
 * httpOnly cookie, and every run and every opinion is filed under whoever that cookie
 * resolves to. The browser is not told the id and does not need it — see
 * `lib/server/identity.ts` for why that moved.
 *
 * Two things stay here. Run ids, because a run is named before it is finished so that
 * feedback can be filed against it. And the id this browser used to play under, kept only
 * so registration can offer it back and carry an existing history into a name.
 *
 * Lossy on failure, like the play log. A private window or a full store costs a data
 * point; it must never cost a game.
 */

const ID_KEY = 'connectris:user:v1';

/**
 * An opaque id. `randomUUID` needs a secure context, and this is called at the end of a
 * run — somewhere it could throw is somewhere a finished game disappears.
 */
export function randomId(): string {
	try {
		return crypto.randomUUID();
	} catch {
		return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
	}
}

/**
 * The id this browser played under before it had a name, if it ever did.
 *
 * Written by every version of this game up to now and never removed, because it is the
 * only thread back to the runs, opinions and solves recorded against it. The registration
 * page offers it to the server, which adopts it if nobody has registered it yet.
 *
 * Nothing writes this key any more. When the last browser holding one has registered it
 * will simply stop returning anything, and this can go.
 */
export function playedAs(): string | null {
	try {
		return localStorage.getItem(ID_KEY);
	} catch {
		return null;
	}
}
