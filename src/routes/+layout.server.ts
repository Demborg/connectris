import { redirect } from '@sveltejs/kit';
import { resolve } from '$app/paths';
import type { LayoutServerLoad } from './$types';

/**
 * The gate.
 *
 * One check, in front of every page, because registration is now the first thing that
 * happens: a run belongs to somebody, and a run played before there was a somebody to
 * belong to is a run that can never appear on a boards page or in the standings.
 *
 * Here rather than in each page's load for the reason gates are usually put in one place —
 * a page that forgot it would not fail, it would quietly work for nobody. The one route
 * this cannot cover is the registration page itself, which is exempt by name.
 *
 * API routes are not covered by layout loads and do not want to be: a `fetch` that lands
 * on a redirect to an HTML page has been given something it cannot read. Those check for
 * themselves and answer 401 — see `requirePlayer`.
 */
export const load: LayoutServerLoad = async ({ locals, url, route }) => {
	// The route id, not the pathname against `resolve('/hello')`. `resolve` answers with a
	// path relative to the page being rendered — "./hello" here, "../hello" from a board —
	// which is exactly right for a link and never equal to a pathname. Comparing the two
	// had this redirecting the registration page to itself, forever.
	if (!locals.player && route.id !== '/hello') {
		// Where they were going, so registering resumes it rather than dropping everyone on
		// today's board. Only the path and query travel: an absolute URL here would be an
		// open redirect, and there is nowhere off this site worth being sent.
		const next = `${url.pathname}${url.search}`;
		redirect(303, `${resolve('/hello')}?next=${encodeURIComponent(next)}`);
	}

	// The alias, for every page that says who you are. The id stays on the server — the
	// browser has never needed to know it and, now that it is what a cookie protects,
	// should not be handed it.
	return { player: locals.player ? { alias: locals.player.alias } : null };
};
