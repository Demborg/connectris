import { error } from '@sveltejs/kit';
import { localeOf } from '$lib/i18n';
import { gameData } from '$lib/server/board';
import type { PageServerLoad } from './$types';

/** One board from the backlog, by id. Unpublished ids are 404, not previews. */
export const load: PageServerLoad = async ({ params }) => {
	const game = await gameData(localeOf(params.lang), params.id);
	// Unreachable: `gameData` already refuses a named board it cannot find. Here so this
	// route never renders the empty-language state, which belongs to today's board alone.
	if (!game) error(404, 'No such puzzle');
	return game;
};
