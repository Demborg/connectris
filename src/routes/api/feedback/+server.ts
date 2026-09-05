import { error } from '@sveltejs/kit';
import { parseFeedback } from '$lib/server/parse';
import { stores } from '$lib/server/stores';
import type { RequestHandler } from './$types';

/**
 * Take what a player said about a board.
 *
 * Upserted by run, so the end screen can post on every tap and a half-answered form is
 * kept rather than lost. Answering twice is a player changing their mind, not two people.
 */
export const POST: RequestHandler = async ({ request }) => {
	const body = await request.json().catch(() => error(400, 'Expected JSON'));
	await stores().feedback.record(parseFeedback(body));
	return new Response(null, { status: 204 });
};
