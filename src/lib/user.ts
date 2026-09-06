/**
 * Who is playing, as far as this phase needs to know.
 *
 * A random id minted on first play and kept in localStorage. There is no account and no
 * login: the point is to tell one player's runs from another's, not to know who they are.
 * DESIGN.md defers auth and asks only that the payload be shaped so a real user id can be
 * attached later — this is that shape, filled with something anonymous.
 *
 * Lossy on failure, like the play log. A private window or a full store costs us a data
 * point; it must never cost a game.
 */

const ID_KEY = 'connectris:user:v1';
const NAME_KEY = 'connectris:name:v1';

function read(key: string): string | null {
	try {
		return localStorage.getItem(key);
	} catch {
		return null;
	}
}

function write(key: string, value: string): void {
	try {
		localStorage.setItem(key, value);
	} catch {
		// Full, blocked, or private mode. Not worth breaking a game over.
	}
}

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

/** A stable id for this browser, minted on first use. */
export function userId(): string {
	const known = read(ID_KEY);
	if (known) return known;

	const minted = randomId();
	write(ID_KEY, minted);
	return minted;
}

/** Set by an invite link, so an invited tester's runs are legible rather than a uuid. */
export function displayName(): string | null {
	return read(NAME_KEY);
}

export function setDisplayName(name: string): void {
	write(NAME_KEY, name);
}
