import { join } from 'node:path';
import puzzles from '$lib/data/puzzles.json';
import type { Puzzle } from '$lib/game/types';
import { cachePlayers, cachePuzzles } from './cache';
import {
	connect,
	firestoreFeedback,
	firestorePlayers,
	firestoreProgress,
	firestorePuzzles,
	firestoreRuns
} from './firestore';
import { jsonFeedback, jsonPlayers, jsonProgress, jsonRuns } from './json';
import { memoryPuzzles } from './memory';
import type { Stores } from './ports';

/**
 * The one place that decides which adapter answers a port.
 *
 * Nothing else in the request path can see this file, which is what lets the same routes
 * run against memory in a test, against files on a laptop, and against Firestore in
 * production. Keep the choosing here and the `if` count at one.
 */

/**
 * How far back the picker reaches, and the window a check is allowed to grade in.
 *
 * Counted from today backwards, so a board leaves the window by ageing out rather than by
 * being pushed out — thirty days of archive, whatever the collection has grown to.
 */
export const BACKLOG = 30;

/**
 * How much of the player and progress collections the standings will read.
 *
 * A ceiling rather than a page: there is no "next page" of a top list, and a bound is
 * what stops one runaway night turning a page load into a full-collection scan. If this
 * is ever actually reached, the fold in `progress.ts` has stopped being the right shape
 * and its own note says what to do about it.
 */
export const ROSTER = 500;
export const HISTORY = 5000;

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

let built: Stores | undefined;

function build(): Stores {
	if (!project) {
		return {
			// The boards compiled into the bundle, in the order they are written down.
			puzzles: memoryPuzzles(puzzles as Puzzle[]),
			// Players on disk rather than in memory even here: registration is a gate, and
			// a gate that forgot everyone on every restart would make a dev server
			// unusable within a day.
			players: jsonPlayers(DATA_DIR),
			progress: jsonProgress(join(DATA_DIR, 'progress')),
			runs: jsonRuns(join(DATA_DIR, 'runs')),
			feedback: jsonFeedback(join(DATA_DIR, 'feedback'))
		};
	}

	const db = connect({ projectId: project });
	return {
		puzzles: cachePuzzles(firestorePuzzles(db)),
		players: cachePlayers(firestorePlayers(db)),
		progress: firestoreProgress(db),
		runs: firestoreRuns(db),
		feedback: firestoreFeedback(db)
	};
}

export function stores(): Stores {
	built ??= build();
	return built;
}
