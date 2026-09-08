import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterAll, describe, expect, it } from 'vitest';

/**
 * Registration, against the store the app actually builds.
 *
 * The data directory is set before `stores` is imported, because that module reads it
 * once when it loads — which is the same reason this file imports everything
 * dynamically. A test that wrote into the repo's own `.data` would be a test that
 * remembered yesterday's names.
 */
const dir = await mkdtemp(join(tmpdir(), 'connectris-identity-'));
process.env.CONNECTRIS_DATA_DIR = dir;

const { register } = await import('./identity');
const { stores } = await import('./stores');

afterAll(async () => {
	await rm(dir, { recursive: true, force: true });
});

describe('register', () => {
	it('mints an id for a name nobody has', async () => {
		const claimed = await register('Ada');

		expect(claimed).toHaveProperty('player');
		if (!('player' in claimed)) return;
		expect(claimed.player).toMatchObject({ alias: 'Ada', handle: 'ada' });
		expect(await stores().players.byId(claimed.player.id)).toMatchObject({ alias: 'Ada' });
	});

	it('refuses a name already taken, however it is cased', async () => {
		await register('Bo');
		expect(await register('BO')).toEqual({ taken: true });
	});

	it('adopts the id a browser was already playing under', async () => {
		// The migration path. Everything recorded against that id — runs, opinions, solved
		// boards — belongs to the name being claimed, so it has to keep the id.
		const played = 'e6bd1d0e-a2b0-4d21-8a2f-9f5ac0a20d11';
		const claimed = await register('Cy', played);

		expect(claimed).toEqual({ player: expect.objectContaining({ id: played }) });
	});

	it('will not adopt an id somebody has already registered', async () => {
		// The one thing adoption must not become: a way to walk into an existing player.
		const taken = 'a3c0e5b2-5f13-4a52-9d61-1a2b3c4d5e6f';
		await register('Dee', taken);

		const claimed = await register('Eve', taken);
		expect(claimed).toEqual({ player: expect.objectContaining({ alias: 'Eve' }) });
		if (!('player' in claimed)) return;
		expect(claimed.player.id).not.toBe(taken);
		expect(await stores().players.byId(taken)).toMatchObject({ alias: 'Dee' });
	});

	it('mints rather than adopting an id a document key could not hold', async () => {
		// `ID` allows underscores, and a value wrapped in double underscores is the one
		// shape Firestore refuses as a document id — which would be a 500 on the one page
		// nobody can get past.
		const claimed = await register('Gus', '__proto__');

		expect(claimed).toHaveProperty('player');
		if (!('player' in claimed)) return;
		expect(claimed.player.id).not.toBe('__proto__');
	});

	it('ignores an offered id that is not shaped like one of ours', async () => {
		// It becomes a storage key. A mangled localStorage entry should cost a history,
		// not a registration.
		const claimed = await register('Fay', '../../etc/passwd');

		expect(claimed).toHaveProperty('player');
		if (!('player' in claimed)) return;
		expect(claimed.player.id).not.toContain('/');
	});
});
