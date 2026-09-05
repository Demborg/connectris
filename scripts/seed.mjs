/**
 * Put the boards in `src/lib/data/puzzles.json` into Firestore.
 *
 * A stopgap. Deciding which boards are in play is the pipeline's job — it is what
 * `cli export` becomes once it writes to the database instead of appending to a JSON file
 * — and this exists only so there is something to play before that lands. Deliberately
 * plain JS with one dependency so it needs no build step.
 *
 *   GOOGLE_CLOUD_PROJECT=connectris-507519 node scripts/seed.mjs [--dry-run]
 *
 * Keyed by puzzle id, so running it twice reorders rather than duplicates.
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

for (const [i, puzzle] of boards.entries()) {
	console.log(`${i}  ${puzzle.id}  ${puzzle.name}`);
}

if (dryRun) {
	console.log('\n--dry-run, nothing written');
	process.exit(0);
}

const db = new Firestore({ projectId: project, preferRest: true });
const batch = db.batch();

for (const [i, puzzle] of boards.entries()) {
	// Mirrors `puzzleDoc` in src/lib/server/firestore.ts. The id lives in the path, and
	// `order` is the file order, which is roughly easiest first.
	batch.set(db.collection('puzzles').doc(puzzle.id), {
		name: puzzle.name,
		language: puzzle.language,
		groups: puzzle.groups,
		order: i,
		source: 'seed'
	});
}

await batch.commit();
console.log(`\nwrote ${boards.length} boards to ${project}`);
