/**
 * Put the boards in `src/lib/data/puzzles.json` into Firestore.
 *
 * The hand-written back catalogue, dated one board a day ending today, so the newest of
 * them is the board being played when the generator takes over. Adding a board a night is
 * the nightly job's business (`connectris-pipeline nightly`); this puts a history under it.
 *
 * Deliberately plain JS with one dependency so it needs no build step.
 *
 *   GOOGLE_CLOUD_PROJECT=connectris-507519 node scripts/seed.mjs [--dry-run]
 *
 * Keyed by puzzle id, so running it twice re-dates rather than duplicates — which also
 * means running it after the generator has been going will shove every generated board
 * into the past. Seed once.
 */

import { readFile } from 'node:fs/promises';
import { Firestore } from '@google-cloud/firestore';

const dryRun = process.argv.includes('--dry-run');

const project = process.env.GOOGLE_CLOUD_PROJECT;
if (!project) {
	console.error('GOOGLE_CLOUD_PROJECT is not set');
	process.exit(1);
}

const boards = JSON.parse(await readFile('src/lib/data/puzzles.json', 'utf8'));

/** `days` before today, as `YYYY-MM-DD`. Mirrors `shift`/`today` in src/lib/server/day.ts. */
function daysAgo(days) {
	const at = new Date();
	at.setUTCDate(at.getUTCDate() - days);
	return at.toISOString().slice(0, 10);
}

// File order is roughly easiest first, and it is read here as the order they were
// published in — so the last board written down is today's and the first is furthest back.
const schedule = boards.map((puzzle, i) => [puzzle, daysAgo(boards.length - 1 - i)]);

for (const [puzzle, liveOn] of schedule) {
	console.log(`${liveOn}  ${puzzle.id}  ${puzzle.name}`);
}

if (dryRun) {
	console.log('\n--dry-run, nothing written');
	process.exit(0);
}

const db = new Firestore({ projectId: project, preferRest: true });
const batch = db.batch();

for (const [puzzle, liveOn] of schedule) {
	// Mirrors `puzzleDoc` in src/lib/server/firestore.ts. The id lives in the path.
	batch.set(db.collection('puzzles').doc(puzzle.id), {
		name: puzzle.name,
		language: puzzle.language,
		groups: puzzle.groups,
		liveOn,
		source: 'seed'
	});
}

await batch.commit();
console.log(`\nwrote ${boards.length} boards to ${project}`);
