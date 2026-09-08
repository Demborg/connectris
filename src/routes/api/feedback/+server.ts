import { error } from '@sveltejs/kit';
import { requirePlayer } from '$lib/server/identity';
import { parseFeedback } from '$lib/server/parse';
import { stores } from '$lib/server/stores';
import type { RequestHandler } from './$types';

/**
 * Take what a player said about a board.
 *
 * Upserted by run, so the end screen can post on every tap and a half-answered form is
 * kept rather than lost. Answering twice is a player changing their mind, not two people.
 *
 * Whose opinion it is comes from the cookie rather than the body. That is the point of
 * this phase: an opinion filed against a uuid could only ever be counted, and one filed
 * against a name can be asked about.
 */
export const POST: RequestHandler = async ({ request, locals }) => {
	const player = requirePlayer(locals);
	const body = await request.json().catch(() => error(400, 'Expected JSON'));
	await stores().feedback.record(parseFeedback(body, player));
	return new Response(null, { status: 204 });
};
