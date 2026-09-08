import { mkdir, readFile, readdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import type { Run } from '$lib/game/log';
import type {
	Feedback,
	FeedbackStore,
	Player,
	PlayerStore,
	Progress,
	ProgressStore,
	RunRecord,
	RunStore
} from './ports';
import { foldRun, progressKey } from './progress';

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
	// Long enough for a progress key, which is two validated ids and a separator. It was
	// 64 — one character over the longest key this store is actually given — and a cap
	// that truncates is a cap that makes two distinct keys one file.
	return join(dir, `${safe.slice(0, 200)}.json`);
}

async function put(dir: string, key: string, value: unknown): Promise<void> {
	const file = fileFor(dir, key);
	await mkdir(dir, { recursive: true });
	await writeFile(file, `${JSON.stringify(value, null, '\t')}\n`, 'utf8');
}

async function get<T>(dir: string, key: string): Promise<T | null> {
	const raw = await readFile(fileFor(dir, key), 'utf8').catch(() => null);
	return raw === null ? null : (JSON.parse(raw) as T);
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

/**
 * Players as files, one per id.
 *
 * The handle index is a second directory of one-line files rather than a scan of the
 * first, so claiming a name is a single stat rather than a read of every player. Nothing
 * here is atomic against a second process — two `pnpm dev`s racing to claim "ada" could
 * both win — and that is the honest limit of a filesystem store. It is the same shape the
 * Firestore adapter makes safe with a transaction, which is where it matters.
 */
export function jsonPlayers(dir: string): PlayerStore {
	const handles = join(dir, 'handles');
	const players = join(dir, 'players');

	// A handle is a name, so it is the one key here that is not already a safe id: it can
	// hold spaces and any script's letters, both of which `fileFor` strips — which would
	// file "ada-lovelace" and "ada lovelace" as one name, and "Åke" as "ke". Encoded, the
	// filename is a faithful key; the readable copy is inside the file it points at.
	const keyOf = (handle: string) => Buffer.from(handle, 'utf8').toString('base64url');

	return {
		async register(player) {
			if (await get<{ id: string }>(handles, keyOf(player.handle))) return 'taken';
			// The handle first: a claim that lands and then fails to write the player leaves
			// a name reserved by nobody, which is recoverable. The other order leaves a
			// player whose name anyone else can take, which is not.
			await put(handles, keyOf(player.handle), { handle: player.handle, id: player.id });
			await put(players, player.id, player);
			return 'ok';
		},
		byId: (id) => get<Player>(players, id),
		async all(limit) {
			return (await all<Player>(players)).slice(0, limit);
		}
	};
}

export function jsonProgress(dir: string, now: () => number = Date.now): ProgressStore {
	return {
		async record(userId, run: Run) {
			const key = progressKey(userId, run.puzzle);
			const folded = foldRun(await get<Progress>(dir, key), userId, run, now());
			await put(dir, key, folded);
			return folded;
		},
		async forUser(userId) {
			return (await all<Progress>(dir)).filter((p) => p.userId === userId);
		},
		async all(limit) {
			return (await all<Progress>(dir)).slice(0, limit);
		}
	};
}
