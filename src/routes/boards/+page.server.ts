import { boardList } from '$lib/server/board';
import type { PageServerLoad } from './$types';

/**
 * Every board still in the window.
 *
 * Which of them you have played is not here and cannot be: it lives in your browser, so
 * the server has nothing to say about it. The list ships in the first response and the
 * marks arrive on hydration.
 */
export const load: PageServerLoad = async () => boardList();
