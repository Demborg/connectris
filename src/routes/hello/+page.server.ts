import { fail, redirect } from '@sveltejs/kit';
import { aliasProblem, normalizeAlias } from '$lib/alias';
import { register, setPlayerCookie } from '$lib/server/identity';
import { nextFrom } from './next';
import type { Actions, PageServerLoad } from './$types';

/**
 * Where a name is claimed.
 *
 * A form action rather than a `fetch`, so registration works before any JavaScript has
 * run — which matters more here than anywhere else in the app, because this page stands
 * in front of every other one. If it needed hydration to submit, a slow first load would
 * be a game nobody could get into.
 */

/** Already registered? Then this page has nothing to ask. */
export const load: PageServerLoad = async ({ locals, url }) => {
	if (locals.player) redirect(303, nextFrom(url));
	return {};
};

export const actions: Actions = {
	default: async ({ request, cookies, url, locals }) => {
		// A second tab that registered while this form sat open. Nothing to do but let
		// them through — failing here would tell someone their name is wrong when what
		// actually happened is that it worked.
		if (locals.player) redirect(303, nextFrom(url));

		const form = await request.formData();
		const typed = form.get('alias');
		const alias = typeof typed === 'string' ? normalizeAlias(typed) : '';

		const problem = aliasProblem(typed);
		// `alias` goes back with the failure so the field is not cleared under someone who
		// has just been told to change one character of it.
		if (problem) return fail(400, { alias, problem });

		// The id this browser played under before registration existed, offered back by the
		// page so its history comes with the name. Absent without JavaScript, and absent
		// for anyone who has never played, in which case a fresh id is minted.
		const adopt = form.get('adopt');
		const claimed = await register(alias, typeof adopt === 'string' ? adopt : null);

		if ('taken' in claimed) {
			return fail(409, { alias, problem: 'Someone already has that one. Try another.' });
		}

		setPlayerCookie(cookies, claimed.player.id);
		redirect(303, nextFrom(url));
	}
};
