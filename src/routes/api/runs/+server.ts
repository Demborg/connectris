import { error } from '@sveltejs/kit';
import { parseRun } from '$lib/server/parse';
import { stores } from '$lib/server/stores';
import type { RequestHandler } from './$types';

/**
 * Record a finished run. Best-effort from the client's side, so the only answer worth
 * giving is whether it landed.
 */
export const POST: RequestHandler = async ({ request }) => {
	const body = await request.json().catch(() => error(400, 'Expected JSON'));
	await stores().runs.record(parseRun(body));
	return new Response(null, { status: 204 });
};
