import { Firestore, type Settings } from '@google-cloud/firestore';
import type { Puzzle } from '$lib/game/types';
import { today } from './day';
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

export function firestorePuzzles(db: Firestore, now: () => string = () => today()): PuzzleStore {
	const puzzles = db.collection(collections.puzzles);

	return {
		async live(limit) {
			// Filtered and ordered on the same single field, which Firestore indexes
			// automatically — no composite index to declare and none to forget when
			// deploying. It is also why `liveOn` is a `YYYY-MM-DD` string: it compares as a
			// date because it sorts as one.
			//
			// The nightly job writes tomorrow's board tonight, so there is normally one
			// document ahead of this window. Excluding it here is what stops a board being
			// playable the evening before it is due, and it costs a range bound.
			const found = await puzzles
				.where('liveOn', '<=', now())
				.orderBy('liveOn', 'desc')
				.limit(limit)
				.get();
			return found.docs.map((d) => puzzleOf(d.id, d.data()));
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

/**
 * Boards, as the pipeline and the seeding tool write them. The id lives in the path.
 *
 * `liveOn` replaced an integer `order`, and does two jobs the integer could not: it says
 * *when* a board is due rather than only what follows what, so the generator can write
 * tomorrow's board tonight without it being playable tonight; and it is a key the
 * generator can pick without reading the collection first to find the largest one.
 *
 * The date is not on `Puzzle` itself. When a board is played is a fact about the
 * schedule, not about the board — keeping it here is what leaves `puzzles.json`, the
 * pipeline's few-shot examples and `engine.spec.ts`'s fixtures free of dates that would
 * be stale the moment they were written.
 */
export type PuzzleDoc = Omit<Puzzle, 'id'> & { liveOn: string; source: string };

export function puzzleDoc(puzzle: Puzzle, liveOn: string, source: string): PuzzleDoc {
	return {
		name: puzzle.name,
		language: puzzle.language,
		groups: puzzle.groups,
		liveOn,
		source
	};
}
