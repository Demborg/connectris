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
