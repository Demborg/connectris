import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { isHttpError } from '@sveltejs/kit';
import { afterAll, describe, expect, it } from 'vitest';
import puzzles from '$lib/data/puzzles.json';
import type { Run } from '$lib/game/log';
import type { Puzzle } from '$lib/game/types';
import type { Player } from '$lib/server/ports';

/**
 * The run endpoint, end to end against the file-backed stores.
 *
 * Same trick as `identity.spec.ts`: the data directory is chosen before the module that
 * reads it is imported. What is being checked here is the seam this phase moved — who a
 * run is filed under, and what the end card is told back — rather than the arithmetic,
 * which `progress.spec.ts` covers on its own.
 */
const dir = await mkdtemp(join(tmpdir(), 'connectris-runs-'));
process.env.CONNECTRIS_DATA_DIR = dir;

const { POST } = await import('./+server');
const { register } = await import('$lib/server/identity');

afterAll(async () => {
	await rm(dir, { recursive: true, force: true });
});

const board = (puzzles as Puzzle[])[0].id;

async function player(alias: string): Promise<Player> {
	const claimed = await register(alias);
	if (!('player' in claimed)) throw new Error(`${alias} was taken`);
	return claimed.player;
}

const run = (over: Partial<Run> & { id: string }) => ({
	puzzle: board,
	startedAt: 1_700_000_000_000,
	outcome: 'won',
	timeMs: 90_000,
	checksLeft: 2,
	moves: 12,
	checks: 2,
	events: [],
	...over
});

function post(body: unknown, who: Player | null) {
	const request = new Request('http://localhost/api/runs', {
		method: 'POST',
		headers: { 'content-type': 'application/json' },
		body: JSON.stringify(body)
	});
	return POST({ request, locals: { player: who } } as unknown as Parameters<typeof POST>[0]);
}

/** The status a request comes back with, however it comes back. */
async function status(body: unknown, who: Player | null): Promise<number> {
	try {
		return (await post(body, who)).status;
	} catch (e) {
		if (isHttpError(e)) return e.status;
		throw e;
	}
}

describe('POST /api/runs', () => {
	it('refuses a run from nobody', async () => {
		// Reached by fetch rather than by navigation, so the registration gate never sees
		// it. A run filed under nobody could never appear anywhere, which makes accepting
		// it worse than refusing it.
		expect(await status(run({ id: 'anon-1' }), null)).toBe(401);
	});

	it('answers a win with the best it now stands at and where that puts them', async () => {
		const ada = await player('Ada');
		const res = await post(run({ id: 'ada-1', timeMs: 90_000, checksLeft: 2 }), ada);

		expect(res.status).toBe(200);
		const said = await res.json();
		expect(said.best).toMatchObject({ timeMs: 90_000, checksLeft: 2 });
		expect(said.place).toBe(1);
		expect(said.of).toBeGreaterThanOrEqual(1);
	});

	it('does not move a best on a worse run, and says so', async () => {
		const bo = await player('Bo');
		await post(run({ id: 'bo-1', timeMs: 40_000, checksLeft: 3 }), bo);
		const res = await post(run({ id: 'bo-2', timeMs: 10_000, checksLeft: 1 }), bo);

		expect((await res.json()).best).toMatchObject({ timeMs: 40_000, checksLeft: 3 });
	});

	it('ranks a better player above a worse one', async () => {
		// Bo is already ahead of Ada on the same board — three checks left against two.
		const ada = await player('Ada the second');
		const res = await post(run({ id: 'ada2-1', timeMs: 90_000, checksLeft: 1 }), ada);

		expect((await res.json()).place).toBeGreaterThan(1);
	});

	it('takes a loss without computing a standing for it', async () => {
		// Nothing moved, so nothing is folded. It is also what keeps the loss card the
		// height it was designed to be: no place means no line.
		const cy = await player('Cy');
		const res = await post(run({ id: 'cy-1', outcome: 'lost', checksLeft: 0 }), cy);

		const said = await res.json();
		expect(said.best).toBeNull();
		expect(said.place).toBeNull();
	});

	it('still refuses a body that is not a run', async () => {
		const dee = await player('Dee');
		expect(await status(run({ id: '../../escaped' }), dee)).toBe(400);
		expect(await status({ nothing: true }, dee)).toBe(400);
	});
});
