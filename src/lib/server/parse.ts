import { error } from '@sveltejs/kit';
import type { GameEvent, Run } from '$lib/game/log';
import type { Difficulty } from '$lib/game/types';
import type { Feedback, Player, RunRecord } from './ports';

/**
 * Turn a browser's word for what happened into a record worth keeping.
 *
 * Most of this arrives from a browser and none of it is checked against a game the server
 * watched, because there was no such game — checks are stateless. That is fine for what
 * this data is for: finding out how real people play. It is not fine for a leaderboard,
 * and a leaderboard is what would pay for the game documents that would make it fine —
 * see the standings note in DESIGN.md, which says plainly what a place on that list does
 * and does not prove.
 *
 * The one thing that is *not* taken on trust any more is who played. `userId` used to be
 * a field in the body; it is now the player the request's cookie resolved to, passed in
 * here so a body cannot name someone else. A payload claiming a `userId` is not rejected,
 * merely ignored — there is nothing to gain by telling a stale client it is wrong about a
 * field the server no longer reads.
 *
 * So the validation here is about keeping the store sane rather than keeping players
 * honest: right shapes, bounded sizes, an id that can safely become a key.
 */

/** Ids become storage keys, so they get the narrow character set that implies. */
export const ID = /^[A-Za-z0-9_-]{1,64}$/;

/** A long run is a few hundred events. Far past that is a mistake or an attack. */
const MAX_EVENTS = 4000;

function str(value: unknown, field: string, max: number): string {
	if (typeof value !== 'string' || value.length > max) error(400, `${field} is not a string`);
	return value;
}

function int(value: unknown, field: string, min: number, max: number): number {
	if (!Number.isInteger(value) || (value as number) < min || (value as number) > max) {
		error(400, `${field} is out of range`);
	}
	return value as number;
}

function id(value: unknown, field: string): string {
	if (typeof value !== 'string' || !ID.test(value)) error(400, `${field} is not an id`);
	return value;
}

/** The run itself, as the browser played it. Who played it is not in here. */
export function parseRun(body: unknown): Run & { id: string } {
	if (typeof body !== 'object' || body === null) error(400, 'Expected an object');
	const b = body as Record<string, unknown>;

	if (b.outcome !== 'won' && b.outcome !== 'lost') error(400, 'outcome must be won or lost');
	if (!Array.isArray(b.events) || b.events.length > MAX_EVENTS) error(400, 'events is not a log');

	return {
		id: id(b.id, 'id'),
		puzzle: str(b.puzzle, 'puzzle', 64),
		outcome: b.outcome,
		startedAt: int(b.startedAt, 'startedAt', 0, Number.MAX_SAFE_INTEGER),
		timeMs: int(b.timeMs, 'timeMs', 0, 86_400_000),
		checksLeft: int(b.checksLeft, 'checksLeft', 0, 99),
		moves: int(b.moves, 'moves', 0, 100_000),
		checks: int(b.checks, 'checks', 0, 99),
		// Kept as sent. Pin 10 is that a run can be replayed and retro-scored against
		// metrics we have not committed to, which means not filtering it down to the ones
		// we have.
		events: b.events as GameEvent[]
	};
}

/** The same run, filed under whoever the cookie says is playing. */
export function runRecord(run: Run & { id: string }, player: Player): RunRecord {
	return { ...run, userId: player.id };
}

/** Long enough for a real thought, short enough not to be a payload. */
const MAX_COMMENT = 2000;

const DIFFICULTIES: Difficulty[] = ['easy', 'right', 'hard'];

/**
 * What a player said about a board.
 *
 * Every answer is allowed to be missing, because the screen is skippable and arrives one
 * tap at a time. Only the two ids are required — without them there is nothing to file
 * the opinion against, which is the one thing that would make it worthless. The third,
 * whose opinion it is, comes from the cookie.
 */
export function parseFeedback(body: unknown, player: Player): Feedback {
	if (typeof body !== 'object' || body === null) error(400, 'Expected an object');
	const b = body as Record<string, unknown>;

	if (b.difficulty != null && !DIFFICULTIES.includes(b.difficulty as Difficulty)) {
		error(400, 'difficulty is not one of the three');
	}
	if (b.fair != null && typeof b.fair !== 'boolean') error(400, 'fair is not a yes or a no');

	return {
		runId: id(b.runId, 'runId'),
		userId: player.id,
		puzzleId: str(b.puzzleId, 'puzzleId', 64),
		difficulty: (b.difficulty ?? null) as Difficulty | null,
		fair: (b.fair ?? null) as boolean | null,
		comment: str(b.comment ?? '', 'comment', MAX_COMMENT)
	};
}
