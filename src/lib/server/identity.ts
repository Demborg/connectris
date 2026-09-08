import { randomUUID } from 'node:crypto';
import { error, type Cookies } from '@sveltejs/kit';
import { handleOf } from '$lib/alias';
import { ID } from './parse';
import type { Player } from './ports';
import { stores } from './stores';

/**
 * Who is asking.
 *
 * DESIGN.md deferred auth and asked only that the payload be shaped so a real user id
 * could be attached later. This is not that later — there is still no password and
 * nothing is proved — but it moves the id from the browser's word to the server's.
 *
 * The difference matters because of what the id now carries. When it only tagged runs for
 * analysis, a client that could name its own id cost nothing: the people playing had no
 * reason to lie, and the only person a forged id misled was whoever forged it. A top list
 * changes who benefits. An id posted in a request body is an id anyone can type, so
 * registering mints one server-side and hands it back as an httpOnly cookie — which the
 * browser cannot read and a form cannot forge — and every write reads the player from
 * there and ignores whatever the body claims.
 *
 * What this still does not buy, and should not be described as buying: anyone can clear
 * the cookie and register again under a new name, and nothing witnessed the run whose
 * time is being reported. The stateless-checks note in DESIGN.md is unchanged and still
 * the honest limit — the standings are a family scoreboard, not a ranked ladder.
 */

export const COOKIE = 'connectris_player';

/** What Firestore will not accept as a document id, of the shapes `ID` would let through. */
const RESERVED = /^__.*__$/;

/** A year. The cookie is the account, so losing it is losing the account. */
const MAX_AGE = 60 * 60 * 24 * 365;

/**
 * Opaque and unguessable, which is the one property it has to have: the cookie is the
 * only thing standing between a player and someone else's record, so an id that could be
 * enumerated would be an account that could be walked into.
 */
export function mintId(): string {
	return randomUUID();
}

export function setPlayerCookie(cookies: Cookies, id: string): void {
	cookies.set(COOKIE, id, {
		path: '/',
		httpOnly: true,
		sameSite: 'lax',
		// Off over plain HTTP, or a phone on the LAN testing against `pnpm dev --host`
		// would never keep it. Cloud Run is HTTPS, so this is on wherever it matters.
		secure: process.env.NODE_ENV === 'production',
		maxAge: MAX_AGE
	});
}

export function clearPlayerCookie(cookies: Cookies): void {
	cookies.delete(COOKIE, { path: '/' });
}

/** The player this request belongs to, or null when nobody has registered on this browser. */
export async function playerOf(cookies: Cookies): Promise<Player | null> {
	const id = cookies.get(COOKIE);
	return id ? await stores().players.byId(id) : null;
}

/**
 * The player, or a 401.
 *
 * For the write endpoints, which are reached by `fetch` rather than by navigation and so
 * are never sent through the registration gate. A run posted by nobody is a run that can
 * never appear on the standings or on a boards page, which makes accepting it worse than
 * refusing it: it would be silently dropped data wearing a 204.
 */
export function requirePlayer(locals: App.Locals): Player {
	if (!locals.player) error(401, 'Register before playing');
	return locals.player;
}

/**
 * Register a name, minting or adopting an id for it.
 *
 * **Adoption** is the migration path. Every browser that played before this existed has a
 * random id in localStorage, and runs, feedback and a board history filed under it. The
 * registration page offers that id back and this claims it, so a player who registers
 * keeps everything they have already done instead of starting at zero beside a pile of
 * orphaned records.
 *
 * It is a hole, and a small one: knowing an unregistered id lets you claim it. The ids
 * are uuids, so knowing one means having been that browser — and the moment an id is
 * registered it stops being adoptable, because the player document under it already
 * exists. The alternative was throwing away every existing player's history, which is a
 * worse trade for a game whose whole point this month is that people keep playing it.
 */
export async function register(
	alias: string,
	adopt?: string | null
): Promise<{ player: Player } | { taken: true }> {
	const players = stores().players;
	// An adopted id arrives from a browser and becomes a storage key, so it has to look
	// like one of ours before it is allowed to be one. Anything else is quietly ignored
	// rather than refused: a mangled localStorage entry should cost a history, not a
	// registration.
	//
	// `ID` allows underscores, and a name wrapped in double underscores is the one string
	// Firestore refuses as a document id — so a crafted localStorage value would be a 500
	// on the one page nobody can get past. Minting instead is the same answer this gives
	// to every other id it does not recognise.
	const claimable = adopt && ID.test(adopt) && !RESERVED.test(adopt) ? adopt : null;
	const id = claimable && !(await players.byId(claimable)) ? claimable : mintId();

	const player: Player = {
		id,
		alias,
		handle: handleOf(alias),
		registeredAt: Date.now()
	};

	return (await players.register(player)) === 'taken' ? { taken: true } : { player };
}
