import { error, json } from '@sveltejs/kit';
import { localChecker } from '$lib/game/checker';
import { COLS, ROWS, boardOf } from '$lib/game/engine';
import type { Row, Tile } from '$lib/game/types';
import { BACKLOG, stores } from '$lib/server/stores';
import type { RequestHandler } from './$types';

/**
 * Grade an arrangement.
 *
 * Nothing about a game is stored between presses. The board is re-dealt from the puzzle
 * id — `deal` is deterministic, so the tiles come back identical to the ones the player
 * was handed — and the answer falls out of that. A check therefore costs one puzzle read,
 * which a warm instance already has cached, and no writes at all.
 *
 * The budget is still counted by the client. There is nothing to protect yet: with no
 * leaderboard, the only person a miscounted run misleads is the person who miscounted it.
 * A game document is what phase 3 buys, and it buys it for the leaderboard, not for this.
 */

type CheckRequest = { puzzleId: string; rows: number[][]; checksUsed: number };

function parse(body: unknown): CheckRequest {
	if (typeof body !== 'object' || body === null) error(400, 'Expected an object');
	const { puzzleId, rows, checksUsed } = body as Record<string, unknown>;

	if (typeof puzzleId !== 'string') error(400, 'puzzleId must be a string');
	if (!Number.isInteger(checksUsed) || (checksUsed as number) < 1) {
		error(400, 'checksUsed must be a positive integer');
	}
	if (!Array.isArray(rows) || rows.length < 1 || rows.length > ROWS) {
		error(400, `rows must hold between 1 and ${ROWS} rows`);
	}
	for (const row of rows) {
		if (!Array.isArray(row) || row.length !== COLS) error(400, `every row holds ${COLS} tiles`);
		for (const id of row) if (!Number.isInteger(id)) error(400, 'tile ids must be integers');
	}

	return { puzzleId, rows: rows as number[][], checksUsed: checksUsed as number };
}

/**
 * Turn tile ids back into the tiles they name.
 *
 * Rows the player has already cleared are simply absent, which is how a stateless grader
 * learns what is still in play — so a short board is expected. A repeated or invented
 * tile is not: both would let someone ask about a board that cannot exist.
 */
function arrangement(tiles: Tile[], rows: number[][]): Row[] {
	const byId = new Map(tiles.map((t) => [t.id, t]));
	const seen = new Set<number>();

	return rows.map((row) =>
		row.map((id) => {
			const tile = byId.get(id);
			if (!tile) error(400, `No tile ${id} on this board`);
			if (seen.has(id)) error(400, `Tile ${id} sent twice`);
			seen.add(id);
			return tile;
		})
	);
}

export const POST: RequestHandler = async ({ request }) => {
	const body = await request.json().catch(() => error(400, 'Expected JSON'));
	const { puzzleId, rows, checksUsed } = parse(body);

	// Only a board that is in play can be graded — the same list the page offers, so a
	// board nobody can navigate to is also a board nobody can probe.
	const live = await stores().puzzles.live(BACKLOG);
	const puzzle = live.find((p) => p.id === puzzleId);
	if (!puzzle) error(404, 'No such puzzle');

	const tiles = boardOf(puzzle).rows.flat();
	return json(await localChecker(puzzle)(arrangement(tiles, rows), checksUsed));
};
