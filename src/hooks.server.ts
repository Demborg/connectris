import type { Handle } from '@sveltejs/kit';
import { playerOf } from '$lib/server/identity';
import { BACKLOG, stores } from '$lib/server/stores';

/**
 * Ask for the boards before anyone asks for a board.
 *
 * Hooks load while the server is starting, so this query overlaps with the rest of boot
 * and with the first request being routed. Measured cold, the query and its auth handshake
 * are most of the wait — everything else, Node and the SvelteKit handler together, is a
 * fraction of it. Starting it here does not make it faster; it makes it happen while the
 * player is still knocking.
 *
 * Not awaited, deliberately. The server has to start listening either way, and a warm-up
 * that blocks that has made the thing it was meant to fix worse.
 */
void stores()
	.puzzles.live(BACKLOG)
	.catch(() => {
		// A warm-up that fails is still a warm-up. The cache drops a failed lookup, so the
		// first real request asks again and reports properly if it is still broken.
	});

/**
 * Resolve who is asking, once, before anything else does.
 *
 * Here rather than in each load because every route now needs it: the pages to know
 * whether to show the game or the registration gate, the write endpoints to know whose
 * run this is. Doing it per route would be the same lookup two or three times in a
 * request and a route that forgot it would be a route that silently accepts anyone.
 *
 * The lookup is cached (see `cachePlayers`), so on a warm instance this is a map read and
 * costs a request nothing. On a cold one it is a single document fetch, which happens
 * alongside the board query already in flight above.
 *
 * A store that cannot be reached leaves the player null rather than failing the request.
 * That degrades to the registration page, which is wrong but legible, and is far better
 * than a 500 on every route because one lookup timed out.
 */
export const handle: Handle = async ({ event, resolve }) => {
	event.locals.player = await playerOf(event.cookies).catch(() => null);
	return resolve(event);
};
