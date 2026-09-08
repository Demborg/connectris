import { resolve } from '$app/paths';

/**
 * Where to go once registered.
 *
 * Only a path from this site. `next` arrives in a query string, which anyone can write,
 * and a redirect that accepted an absolute URL would send players off to whatever someone
 * put in a link — the standard open-redirect shape. A leading `//` is the case that looks
 * relative and is not: browsers read it as a protocol-relative absolute URL.
 *
 * Beside the page rather than in it because a `+page.server.ts` may only export the names
 * SvelteKit knows, and this is worth testing on its own.
 */
export function nextFrom(url: URL): string {
	const wanted = url.searchParams.get('next') ?? '';
	return wanted.startsWith('/') && !wanted.startsWith('//') ? wanted : resolve('/');
}
