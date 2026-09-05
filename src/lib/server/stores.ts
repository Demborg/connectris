import { join } from 'node:path';
import puzzles from '$lib/data/puzzles.json';
import type { Puzzle } from '$lib/game/types';
import { cachePuzzles } from './cache';
import { systemClock } from './day';
import { connect, firestoreFeedback, firestorePuzzles, firestoreRuns } from './firestore';
import { jsonFeedback, jsonRuns } from './json';
import { memoryPuzzles } from './memory';
import type { Day, PuzzleStore, Stores } from './ports';

/**
 * The one place that decides which adapter answers a port.
 *
 * Nothing else in the request path can see this file, which is what lets the same routes
 * run against memory in a test, against files on a laptop, and against Firestore in
 * production. Keep the choosing here and the `if` count at one.
 */

/** How far back the picker reaches, and the window a check is allowed to grade in. */
export const BACKLOG = 30;

/** Where play data lands when there is no database. Real sessions, not fixtures. */
export const DATA_DIR = process.env.CONNECTRIS_DATA_DIR ?? '.data';

/**
 * Firestore when there is a project to talk to, files when there is not.
 *
 * Inferred rather than configured, deliberately. A laptop with no cloud project has to be
 * able to play — that is what the seam is for — and Cloud Run always sets this, so both
 * places do the right thing without anyone remembering a flag.
 */
const project = process.env.GOOGLE_CLOUD_PROJECT ?? '';

const clock = systemClock;
const boards = puzzles as Puzzle[];

/** The bundled boards, rescheduled when the day turns over rather than at boot. */
const bundled: PuzzleStore = (() => {
	let held: { day: Day; store: PuzzleStore } | undefined;

	const forToday = () => {
		const day = clock.today();
		if (held?.day !== day) held = { day, store: memoryPuzzles(boards, day) };
		return held.store;
	};

	return {
		scheduledFor: (day) => forToday().scheduledFor(day),
		published: (day, limit) => forToday().published(day, limit),
		byId: (id) => forToday().byId(id)
	};
})();

let built: Stores | undefined;

function build(): Stores {
	if (!project) {
		return {
			clock,
			puzzles: bundled,
			runs: jsonRuns(join(DATA_DIR, 'runs')),
			feedback: jsonFeedback(join(DATA_DIR, 'feedback'))
		};
	}

	const db = connect({ projectId: project });
	return {
		clock,
		puzzles: cachePuzzles(firestorePuzzles(db)),
		runs: firestoreRuns(db),
		feedback: firestoreFeedback(db)
	};
}

export function stores(): Stores {
	built ??= build();
	return built;
}
