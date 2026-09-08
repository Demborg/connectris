import { isRedirect } from '@sveltejs/kit';
import { describe, expect, it } from 'vitest';
import type { Player } from '$lib/server/ports';
import { load } from './+layout.server';

/**
 * The gate.
 *
 * One rule in front of every page, so it is worth a test of its own: what it lets past,
 * where it sends what it does not, and that it cannot be talked into forwarding someone
 * off the site.
 */

const ada: Player = { id: 'u1', alias: 'Ada', handle: 'ada', registeredAt: 0 };

/**
 * Where the gate sent this request, or null if it let it through.
 *
 * `route.id` is what the gate reads, and it is the route *pattern* rather than the path —
 * which is the whole point of it reading that rather than comparing pathnames.
 */
async function gate(route: string, player: Player | null, url = route): Promise<string | null> {
	const event = {
		locals: { player },
		route: { id: route },
		url: new URL(`http://localhost${url}`)
	};
	try {
		await load(event as unknown as Parameters<typeof load>[0]);
		return null;
	} catch (e) {
		if (isRedirect(e)) return e.location;
		throw e;
	}
}

describe('the registration gate', () => {
	it('sends an unregistered visitor to pick a name', async () => {
		expect(await gate('/', null)).toBe('/hello?next=%2F');
	});

	it('remembers where they were going', async () => {
		// A shared link to a board is the whole point of boards having URLs. Registering
		// has to resume it rather than dropping everyone on today's board.
		expect(await gate('/p/[id]', null, '/p/gen-1')).toBe('/hello?next=%2Fp%2Fgen-1');
		expect(await gate('/boards', null, '/boards?x=1')).toBe('/hello?next=%2Fboards%3Fx%3D1');
	});

	it('lets the registration page render rather than redirecting it to itself', async () => {
		// The loop this had: `resolve('/hello')` answers with a path relative to the page
		// being rendered, so it never equals `url.pathname` and the exemption never fired.
		expect(await gate('/hello', null)).toBeNull();
	});

	it('lets a registered player through', async () => {
		expect(await gate('/', ada)).toBeNull();
	});

	it('tells the page who is playing, and nothing else about them', async () => {
		// The alias is for showing. The id is what the cookie protects, and the browser
		// has never needed it.
		const data = await load({
			locals: { player: ada },
			route: { id: '/' },
			url: new URL('http://localhost/')
		} as unknown as Parameters<typeof load>[0]);

		expect(data).toEqual({ player: { alias: 'Ada' } });
	});

	it('says nobody is playing when nobody is', async () => {
		const data = await load({
			locals: { player: null },
			route: { id: '/hello' },
			url: new URL('http://localhost/hello')
		} as unknown as Parameters<typeof load>[0]);

		expect(data).toEqual({ player: null });
	});
});
