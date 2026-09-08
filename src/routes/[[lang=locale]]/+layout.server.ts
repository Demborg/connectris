import { redirect } from '@sveltejs/kit';
import { resolve } from '$app/paths';
import { DEFAULT_LOCALE, LOCALES, LOCALE_COOKIE, isLocale, localeOf, segment } from '$lib/i18n';
import type { LayoutServerLoad } from './$types';

/**
 * Which language this visitor most likely wants, when the URL has not said.
 *
 * Their own choice first, then what the browser asks for, then English. Deliberately
 * consulted on the bare root and nowhere else: every other URL states its language, and a
 * page that second-guessed an explicit `/boards` would make English unreachable for anyone
 * whose browser prefers Swedish.
 */
function preferred(cookie: string | undefined, header: string | null) {
	if (isLocale(cookie)) return cookie;
	for (const tag of (header ?? '').split(',')) {
		const code = tag.split(';')[0].trim().slice(0, 2).toLowerCase();
		if (isLocale(code) && LOCALES.includes(code)) return code;
	}
	return DEFAULT_LOCALE;
}

/**
 * The gate, and the language.
 *
 * One check in front of every page, because registration is now the first thing that
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
export const load: LayoutServerLoad = async ({ locals, url, route, params, cookies, request }) => {
	const locale = localeOf(params.lang);

	// Only the *unprefixed* root, and only before the gate: a link sent to somebody whose
	// browser is Swedish should open in Swedish, and every other path has already said
	// which language it is. Testing the route id alone was not enough — `/sv` matches that
	// route too, and a visitor who asked for Swedish by name was bounced back to English.
	if (route.id === '/[[lang=locale]]' && params.lang === undefined) {
		const wanted = preferred(cookies.get(LOCALE_COOKIE), request.headers.get('accept-language'));
		if (wanted !== locale) redirect(303, resolve('/[[lang=locale]]', { lang: segment(wanted) }));
	}

	// The route id, not the pathname against `resolve('/hello')`. `resolve` answers with a
	// path relative to the page being rendered — "./hello" here, "../hello" from a board —
	// which is exactly right for a link and never equal to a pathname. Comparing the two
	// had this redirecting the registration page to itself, forever.
	if (!locals.player && route.id !== '/[[lang=locale]]/hello') {
		// Where they were going, so registering resumes it rather than dropping everyone on
		// today's board. Only the path and query travel: an absolute URL here would be an
		// open redirect, and there is nowhere off this site worth being sent.
		const next = `${url.pathname}${url.search}`;
		const hello = resolve('/[[lang=locale]]/hello', { lang: segment(locale) });
		redirect(303, `${hello}?next=${encodeURIComponent(next)}`);
	}

	// Being on a language is the preference. No form and no endpoint behind the switcher:
	// it is a plain link, and arriving is what records the choice — which also means that
	// following a Swedish link somebody sent you sets Swedish, exactly as picking it would.
	if (cookies.get(LOCALE_COOKIE) !== locale) {
		cookies.set(LOCALE_COOKIE, locale, {
			path: '/',
			httpOnly: false,
			sameSite: 'lax',
			maxAge: 60 * 60 * 24 * 365
		});
	}

	// The alias, for every page that says who you are. The id stays on the server — the
	// browser has never needed to know it and, now that it is what a cookie protects,
	// should not be handed it.
	return { locale, player: locals.player ? { alias: locals.player.alias } : null };
};
