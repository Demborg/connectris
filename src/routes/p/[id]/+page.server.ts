import { gameData } from '$lib/server/board';
import type { PageServerLoad } from './$types';

/** One board from the backlog, by id. Unpublished ids are 404, not previews. */
export const load: PageServerLoad = async ({ params }) => gameData(params.id);
