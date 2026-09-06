import { gameData } from '$lib/server/board';
import type { PageServerLoad } from './$types';

/**
 * Today's board.
 *
 * Loading here rather than fetching from the browser is what keeps a cold start cheap:
 * the board ships inside the first response, so a scaled-to-zero instance costs the
 * player one wait instead of a wait and then a round trip.
 */
export const load: PageServerLoad = async () => gameData();
