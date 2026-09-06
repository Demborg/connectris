import { mkdir, readFile, readdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import type { Feedback, FeedbackStore, RunRecord, RunStore } from './ports';

/**
 * Stores that keep records as JSON files under a directory.
 *
 * This is the socket a real database will go into, filled with the filesystem. It is here
 * for two reasons: a laptop can capture real play data before there is a cloud project to
 * put it in, and the fastest way to find out whether a port is the right shape is to give
 * it a second implementation and see what it makes awkward.
 *
 * One file per record, named by its key. An upsert is an overwrite, a read is a directory
 * listing, and the whole corpus is `cat`-able and `jq`-able with no tool to install:
 *
 *   cat .data/runs/*.json | jq -s 'group_by(.puzzle) | map({puzzle: .[0].puzzle, n: length})'
 */

/**
 * Keys reach here from a browser, and a key becomes a path. Anything that could climb out
 * of the directory is not a key. Ids are generated as uuids, so this only ever fires on
 * something that was not one.
 */
function fileFor(dir: string, key: string): string {
	const safe = key.replace(/[^A-Za-z0-9_-]/g, '');
	if (!safe) throw new Error(`unusable record key: ${key}`);
	return join(dir, `${safe.slice(0, 64)}.json`);
}

async function put(dir: string, key: string, value: unknown): Promise<void> {
	const file = fileFor(dir, key);
	await mkdir(dir, { recursive: true });
	await writeFile(file, `${JSON.stringify(value, null, '\t')}\n`, 'utf8');
}

/** Everything in the directory. A missing directory is an empty store, not an error. */
async function all<T>(dir: string): Promise<T[]> {
	const names = await readdir(dir).catch(() => [] as string[]);
	return Promise.all(
		names
			.filter((n) => n.endsWith('.json'))
			.sort()
			.map(async (n) => JSON.parse(await readFile(join(dir, n), 'utf8')) as T)
	);
}

export function jsonRuns(dir: string): RunStore & { all(): Promise<RunRecord[]> } {
	return {
		record: (run) => put(dir, run.id, run),
		all: () => all<RunRecord>(dir)
	};
}

export function jsonFeedback(dir: string): FeedbackStore & { all(): Promise<Feedback[]> } {
	return {
		record: (f) => put(dir, f.runId, f),
		all: () => all<Feedback>(dir)
	};
}
