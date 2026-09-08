import { isRedirect } from '@sveltejs/kit';
import { describe, expect, it } from 'vitest';
import { LOCALE_COOKIE } from '$lib/i18n';
import type { Player } from '$lib/server/ports';
import { load } from './+layout.server';

/**
 * The gate, and the language.
 *
 * One rule in front of every page, so it is worth a test of its own: what it lets past,
 * where it sends what it does not, and that it cannot be talked into forwarding someone
 * off the site. Since the app speaks two languages it also settles which one a page is in,
 * and every redirect it issues has to stay inside that language — a gate that sent a
 * Swedish player to an English registration page would lose them at the door.
 */

const ada: Player = { id: 'u1', alias: 'Ada', handle: 'ada', registeredAt: 0 };

type Options = { url?: string; lang?: string; cookie?: string; accept?: string };

function event(route: string, player: Player | null, o: Options = {}) {
	const set: Record<string, string> = {};
	return {
		locals: { player },
		route: { id: route },
		params: { lang: o.lang },
		url: new URL(`http://localhost${o.url ?? route}`),
		cookies: {
			get: (n: string) => (n === LOCALE_COOKIE ? o.cookie : undefined),
			set: (n: string, v: string) => (set[n] = v)
		},
		request: { headers: { get: () => o.accept ?? null } },
		set
	};
}

/** Where the gate sent this request, or null if it let it through. */
async function gate(route: string, player: Player | null, o: Options = {}) {
	try {
		await load(event(route, player, o) as unknown as Parameters<typeof load>[0]);
		return null;
	} catch (e) {
		if (isRedirect(e)) return e.location;
		throw e;
	}
}

const ROOT = '/[[lang=locale]]';

describe('the registration gate', () => {
	it('sends an unregistered visitor to pick a name', async () => {
		expect(await gate(ROOT, null, { url: '/' })).toBe('/hello?next=%2F');
	});

	it('remembers where they were going', async () => {
		// A shared link to a board is the whole point of boards having URLs. Registering
		// has to resume it rather than dropping everyone on today's board.
		expect(await gate(`${ROOT}/p/[id]`, null, { url: '/p/gen-1' })).toBe(
			'/hello?next=%2Fp%2Fgen-1'
		);
		expect(await gate(`${ROOT}/boards`, null, { url: '/boards?x=1' })).toBe(
			'/hello?next=%2Fboards%3Fx%3D1'
		);
	});

	it('keeps a Swedish visitor in Swedish on the way to registering', async () => {
		expect(await gate(`${ROOT}/boards`, null, { url: '/sv/boards', lang: 'sv' })).toBe(
			'/sv/hello?next=%2Fsv%2Fboards'
		);
	});

	it('lets the registration page render rather than redirecting it to itself', async () => {
		expect(await gate(`${ROOT}/hello`, null, { url: '/hello' })).toBeNull();
		expect(await gate(`${ROOT}/hello`, null, { url: '/sv/hello', lang: 'sv' })).toBeNull();
	});

	it('lets a registered player through', async () => {
		expect(await gate(ROOT, ada, { url: '/' })).toBeNull();
	});

	it('tells the page who is playing, which language, and nothing else', async () => {
		// The alias is for showing. The id is what the cookie protects, and the browser
		// has never needed it.
		const data = await load(
			event(ROOT, ada, { url: '/' }) as unknown as Parameters<typeof load>[0]
		);
		expect(data).toEqual({ locale: 'en', player: { alias: 'Ada' } });
	});

	it('says nobody is playing when nobody is', async () => {
		const data = await load(
			event(`${ROOT}/hello`, null, { url: '/hello' }) as unknown as Parameters<typeof load>[0]
		);
		expect(data).toEqual({ locale: 'en', player: null });
	});
});

describe('which language a page is in', () => {
	it('reads it off the URL, not off anything else', async () => {
		const data = await load(
			event(`${ROOT}/boards`, ada, { url: '/sv/boards', lang: 'sv', cookie: 'en' }) as never
		);
		// The cookie says English and the URL says Swedish. The URL wins, or a shared link
		// would open in whatever language the recipient last used.
		expect(data).toMatchObject({ locale: 'sv' });
	});

	it('sends the bare root to the language the visitor last chose', async () => {
		expect(await gate(ROOT, ada, { url: '/', cookie: 'sv' })).toBe('/sv');
	});

	it('falls back to what the browser asks for', async () => {
		expect(await gate(ROOT, ada, { url: '/', accept: 'sv-SE,sv;q=0.9,en;q=0.8' })).toBe('/sv');
		expect(await gate(ROOT, ada, { url: '/', accept: 'en-GB,en;q=0.9' })).toBeNull();
		// A language the game does not speak is not an error, it is English.
		expect(await gate(ROOT, ada, { url: '/', accept: 'de-DE,de;q=0.9' })).toBeNull();
	});

	it('never second-guesses a URL that names its language', async () => {
		// `/sv` matches the same route as `/`, so a gate that tested the route id alone
		// bounced a visitor who had asked for Swedish by name straight back to English.
		expect(await gate(ROOT, ada, { url: '/sv', lang: 'sv' })).toBeNull();
		expect(await gate(ROOT, ada, { url: '/sv', lang: 'sv', accept: 'en-GB' })).toBeNull();
	});

	it('second-guesses the root and nothing else', async () => {
		// `/boards` states its language. A page that redirected it on a header would make
		// English unreachable for anyone whose browser prefers Swedish.
		expect(await gate(`${ROOT}/boards`, ada, { url: '/boards', accept: 'sv' })).toBeNull();
	});

	it('remembers the language of the page being read', async () => {
		const e = event(`${ROOT}/boards`, ada, { url: '/sv/boards', lang: 'sv' });
		await load(e as unknown as Parameters<typeof load>[0]);
		expect(e.set[LOCALE_COOKIE]).toBe('sv');
	});
});
