import { Firestore, type Settings } from '@google-cloud/firestore';
import type { Puzzle } from '$lib/game/types';
import type { Feedback, FeedbackStore, PuzzleStore, RunRecord, RunStore } from './ports';

/**
 * Firestore, over REST.
 *
 * `preferRest` is the whole reason a cold start is affordable: the default transport
 * drags in gRPC and its protobuf loading, which is seconds of startup this service would
 * pay on every scale-from-zero. Over REST it is an HTTP client and a token.
 *
 * Chosen over Postgres despite DESIGN.md's window-function argument, because that
 * argument is about a scale this game will not reach and the standing cost of a Cloud SQL
 * instance is real every month regardless. There is no pool to warm, no secret to hold —
 * ADC in the same project — and a permanent free quota this app will not come near.
 */

export const collections = {
	puzzles: 'puzzles',
	runs: 'runs',
	feedback: 'feedback'
} as const;

export function connect(settings: Settings = {}): Firestore {
	return new Firestore({ preferRest: true, ...settings });
}

/** Documents carry their id in the path; a puzzle wants it in the object as well. */
function puzzleOf(id: string, data: FirebaseFirestore.DocumentData): Puzzle {
	return {
		id,
		name: data.name as string,
		language: (data.language as string) ?? 'en',
		groups: data.groups as Puzzle['groups']
	};
}

export function firestorePuzzles(db: Firestore): PuzzleStore {
	const puzzles = db.collection(collections.puzzles);

	return {
		async live(limit) {
			// Ordered by a single field, which Firestore indexes automatically — no
			// composite index to declare and none to forget when deploying.
			const found = await puzzles.orderBy('order').limit(limit).get();
			return found.docs.map((d) => puzzleOf(d.id, d.data()));
		},

		async byId(id) {
			const doc = await puzzles.doc(id).get();
			return doc.exists ? puzzleOf(doc.id, doc.data()!) : null;
		}
	};
}

export function firestoreRuns(db: Firestore): RunStore {
	const runs = db.collection(collections.runs);
	// Keyed by the run's own id rather than auto-generated, so a client that retries a
	// best-effort post records one run instead of two.
	return { record: async (run: RunRecord) => void (await runs.doc(run.id).set(run)) };
}

export function firestoreFeedback(db: Firestore): FeedbackStore {
	const feedback = db.collection(collections.feedback);
	// Keyed by run, so answering in stages is one opinion revised rather than several.
	return { record: async (f: Feedback) => void (await feedback.doc(f.runId).set(f)) };
}

/** Boards, as the pipeline and the seeding tool write them. The id lives in the path. */
export type PuzzleDoc = Omit<Puzzle, 'id'> & { order: number; source: string };

export function puzzleDoc(puzzle: Puzzle, order: number, source: string): PuzzleDoc {
	return {
		name: puzzle.name,
		language: puzzle.language,
		groups: puzzle.groups,
		order,
		source
	};
}
