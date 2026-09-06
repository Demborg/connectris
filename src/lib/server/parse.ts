import { error } from '@sveltejs/kit';
import type { GameEvent } from '$lib/game/log';
import type { Difficulty } from '$lib/game/types';
import type { Feedback, RunRecord } from './ports';

/**
 * Turn a browser's word for what happened into a record worth keeping.
 *
 * Everything here arrives from a browser and none of it is checked against a game the
 * server watched, because there was no such game — checks are stateless. That is fine for
 * what this data is for: finding out how real people play, from people with no reason to
 * lie. It is not fine for a leaderboard, and a leaderboard is what would pay for the game
 * documents that would make it fine.
 *
 * So the validation here is about keeping the store sane rather than keeping players
 * honest: right shapes, bounded sizes, an id that can safely become a key.
 */

/** Ids become storage keys, so they get the narrow character set that implies. */
const ID = /^[A-Za-z0-9_-]{1,64}$/;

/** A long run is a few hundred events. Far past that is a mistake or an attack. */
const MAX_EVENTS = 4000;
const MAX_NAME = 60;

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

export function parseRun(body: unknown): RunRecord {
	if (typeof body !== 'object' || body === null) error(400, 'Expected an object');
	const b = body as Record<string, unknown>;

	if (b.outcome !== 'won' && b.outcome !== 'lost') error(400, 'outcome must be won or lost');
	if (!Array.isArray(b.events) || b.events.length > MAX_EVENTS) error(400, 'events is not a log');

	return {
		id: id(b.id, 'id'),
		userId: id(b.userId, 'userId'),
		displayName: b.displayName == null ? null : str(b.displayName, 'displayName', MAX_NAME),
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

/** Long enough for a real thought, short enough not to be a payload. */
const MAX_COMMENT = 2000;

const DIFFICULTIES: Difficulty[] = ['easy', 'right', 'hard'];

/**
 * What a player said about a board.
 *
 * Every answer is allowed to be missing, because the screen is skippable and arrives one
 * tap at a time. Only the three ids are required — without them there is nothing to file
 * the opinion against, which is the one thing that would make it worthless.
 */
export function parseFeedback(body: unknown): Feedback {
	if (typeof body !== 'object' || body === null) error(400, 'Expected an object');
	const b = body as Record<string, unknown>;

	if (b.difficulty != null && !DIFFICULTIES.includes(b.difficulty as Difficulty)) {
		error(400, 'difficulty is not one of the three');
	}
	if (b.fair != null && typeof b.fair !== 'boolean') error(400, 'fair is not a yes or a no');

	return {
		runId: id(b.runId, 'runId'),
		userId: id(b.userId, 'userId'),
		puzzleId: str(b.puzzleId, 'puzzleId', 64),
		difficulty: (b.difficulty ?? null) as Difficulty | null,
		fair: (b.fair ?? null) as boolean | null,
		comment: str(b.comment ?? '', 'comment', MAX_COMMENT)
	};
}
