import { mkdtemp, readdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterAll, describe, expect, it } from 'vitest';
import { feedbackStoreContract, runOf, runStoreContract } from './contract';
import { jsonFeedback, jsonRuns } from './json';

const made: string[] = [];

async function dir(): Promise<string> {
	const made_ = await mkdtemp(join(tmpdir(), 'connectris-'));
	made.push(made_);
	return made_;
}

afterAll(async () => {
	await Promise.all(made.map((d) => rm(d, { recursive: true, force: true })));
});

describe('json run store', () => {
	runStoreContract(async () => {
		const store = jsonRuns(await dir());
		return { store, recorded: () => store.all() };
	});
});

describe('json feedback store', () => {
	feedbackStoreContract(async () => {
		const store = jsonFeedback(await dir());
		return { store, recorded: () => store.all() };
	});
});

describe('record keys become filenames', () => {
	it('keeps a key that tries to climb out inside the directory', async () => {
		// Ids arrive from a browser and a key becomes a path, so this is the one place a
		// bad id could reach past the store it was written to.
		const d = await dir();
		await jsonRuns(d).record(runOf({ id: '../../escaped' }));
		expect(await readdir(d)).toEqual(['escaped.json']);
	});

	it('refuses a key with nothing usable left in it', async () => {
		const store = jsonRuns(await dir());
		await expect(store.record(runOf({ id: '../..' }))).rejects.toThrow(/unusable/);
	});
});
