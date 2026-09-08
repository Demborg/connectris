import { localeOf } from '$lib/i18n';
import { gameData } from '$lib/server/board';
import type { PageServerLoad } from './$types';

/**
 * Today's board.
 *
 * Loading here rather than fetching from the browser is what keeps a cold start cheap:
 * the board ships inside the first response, so a scaled-to-zero instance costs the
 * player one wait instead of a wait and then a round trip.
 */
// Always an object, with the game inside it: a load may not answer with null, and a
// language that has published nothing yet has to be a state the page can render rather
// than an error it has to raise.
export const load: PageServerLoad = async ({ params }) => ({
	game: await gameData(localeOf(params.lang))
});
