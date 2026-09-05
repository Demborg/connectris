/**
 * Put the boards in `src/lib/data/puzzles.json` into Firestore, on consecutive days
 * ending today.
 *
 * A stopgap. Scheduling belongs to the pipeline — it is what `cli export` becomes once it
 * writes to the database instead of appending to a JSON file — and this exists only so
 * there is something to play before that lands. Deliberately plain JS with one dependency
 * so it needs no build step.
 *
 *   GOOGLE_CLOUD_PROJECT=connectris-507519 node scripts/seed.mjs [--dry-run]
 *
 * Writes are keyed by puzzle id, so running it twice reschedules rather than duplicates.
 */

import { readFile } from 'node:fs/promises';
import { Firestore } from '@google-cloud/firestore';

const ZONE = 'Europe/Stockholm';
const dryRun = process.argv.includes('--dry-run');

const project = process.env.GOOGLE_CLOUD_PROJECT;
if (!project) {
	console.error('GOOGLE_CLOUD_PROJECT is not set');
	process.exit(1);
}

/** Mirrors `systemClock` in src/lib/server/day.ts — `en-CA` is already YYYY-MM-DD. */
const today = new Intl.DateTimeFormat('en-CA', { timeZone: ZONE }).format(new Date());

/** Mirrors `daysBefore` in src/lib/server/day.ts. */
function daysBefore(day, n) {
	const d = new Date(`${day}T00:00:00Z`);
	d.setUTCDate(d.getUTCDate() - n);
	return d.toISOString().slice(0, 10);
}

const boards = JSON.parse(await readFile('src/lib/data/puzzles.json', 'utf8'));

// Newest last, matching `scheduleEndingToday`: the order the pipeline appends in, so
// "export a board" reads as "schedule it next".
const scheduled = boards.map((puzzle, i) => ({
	puzzle,
	day: daysBefore(today, boards.length - 1 - i)
}));

for (const { puzzle, day } of scheduled) {
	console.log(`${day}  ${puzzle.id}  ${puzzle.name}`);
}

if (dryRun) {
	console.log('\n--dry-run, nothing written');
	process.exit(0);
}

const db = new Firestore({ projectId: project, preferRest: true });
const batch = db.batch();

for (const { puzzle, day } of scheduled) {
	// Mirrors `puzzleDoc` in src/lib/server/firestore.ts. The id lives in the path.
	batch.set(db.collection('puzzles').doc(puzzle.id), {
		name: puzzle.name,
		language: puzzle.language,
		groups: puzzle.groups,
		scheduledFor: day,
		source: 'seed'
	});
}

await batch.commit();
console.log(`\nwrote ${scheduled.length} boards to ${project}`);
