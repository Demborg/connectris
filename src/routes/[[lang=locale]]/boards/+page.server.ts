import { localeOf } from '$lib/i18n';
import { boardList } from '$lib/server/board';
import { requirePlayer } from '$lib/server/identity';
import type { PageServerLoad } from './$types';

/**
 * Every board still in the window, marked with what this player has done with it.
 *
 * Both halves ship in the first response now. They used to arrive separately — the list
 * from here, the marks from localStorage on hydration — which was the right shape while
 * the server had nothing to say about who was asking, and is the wrong one now that it
 * does.
 *
 * `requirePlayer` cannot actually fire here: the layout gate has already sent an
 * unregistered visitor to register. It is here so the load does not have to guess, and so
 * this route would fail loudly rather than anonymously if that gate ever moved.
 */
export const load: PageServerLoad = async ({ locals, params }) =>
	boardList(requirePlayer(locals).id, localeOf(params.lang));
