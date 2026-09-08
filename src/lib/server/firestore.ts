import { Firestore, type Settings } from '@google-cloud/firestore';
import type { Run } from '$lib/game/log';
import { LOCALES } from '$lib/i18n';
import type { Puzzle } from '$lib/game/types';
import { today } from './day';
import type {
	Feedback,
	FeedbackStore,
	Player,
	PlayerStore,
	Progress,
	ProgressStore,
	PuzzleStore,
	RunRecord,
	RunStore
} from './ports';
import { foldRun, progressKey } from './progress';

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
	feedback: 'feedback',
	players: 'players',
	handles: 'handles',
	progress: 'progress'
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
		async live(limit, language) {
			// Ordered on the one field that is indexed automatically, and narrowed to a
			// language in memory. An equality on `language` beside the range on `liveOn` is
			// exactly the shape that needs a composite index — a thing to declare, deploy
			// and forget — and the same trade was already made for `finishedRuns`.
			//
			// It pages, rather than over-fetching a fixed multiple of `limit` and hoping.
			// The two languages are not interleaved: Swedish starts months after English,
			// so the newest documents can be a run of one language and a single page of
			// them may hold none of the other. In the steady state of a board a night each,
			// the first page answers and the loop runs once.
			const wanted = limit * LOCALES.length;
			const found: Puzzle[] = [];
			let after: FirebaseFirestore.QueryDocumentSnapshot | undefined;

			while (found.length < limit) {
				// The nightly job writes tomorrow's board tonight, so there is normally one
				// document ahead of this window. Excluding it is what stops a board being
				// playable the evening before it is due, and it costs a range bound.
				let query = puzzles.where('liveOn', '<=', now()).orderBy('liveOn', 'desc');
				// The snapshot, not its `liveOn`: both languages publish on the same day, so
				// a cursor on the value alone would step over the second board of a date.
				if (after) query = query.startAfter(after);

				const page = await query.limit(wanted).get();
				if (page.empty) break;

				for (const doc of page.docs) {
					const puzzle = puzzleOf(doc.id, doc.data());
					if (puzzle.language === language) found.push(puzzle);
				}
				after = page.docs[page.docs.length - 1];
				if (page.size < wanted) break;
			}

			return found.slice(0, limit);
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
 * Players, and the index that makes a name unique.
 *
 * Two documents per registration: the player under their id, and a claim on their handle
 * under the handle itself. The claim exists because Firestore has no unique constraint on
 * a field — the only uniqueness it offers is that a document id is unique — so the way to
 * make a name unique is to make it a document id.
 *
 * Both writes go in one transaction, which is the point. This is the single place in the
 * app where two requests racing produce a *wrong* answer rather than a repeated one: a
 * check-then-write would let two people register the same name in the same second and
 * leave the standings with two rows nobody can tell apart. The transaction's read of the
 * handle document is what makes the second one lose.
 *
 * The handle is encoded rather than used verbatim as that id, because a document id is
 * not allowed to be "." or "..", to contain "/", or to be wrapped in double underscores —
 * three ways an otherwise reasonable name would land as an exception instead of a "that
 * one's taken". The name rules have no business knowing any of that, so the encoding
 * absorbs it and the readable spelling lives in the document.
 */
export function firestorePlayers(db: Firestore): PlayerStore {
	const players = db.collection(collections.players);
	const handles = db.collection(collections.handles);
	// Prefixed, so the encoding can never produce the one id Firestore refuses: a value
	// wrapped in double underscores. base64url's alphabet includes "_", so without this it
	// is a remote possibility rather than an impossible one, and the cost of ruling it out
	// is a character.
	const keyOf = (handle: string) => `h${Buffer.from(handle, 'utf8').toString('base64url')}`;

	return {
		async register(player) {
			return db.runTransaction(async (tx) => {
				const claim = handles.doc(keyOf(player.handle));
				if ((await tx.get(claim)).exists) return 'taken' as const;

				tx.set(claim, { id: player.id, alias: player.alias, handle: player.handle });
				tx.set(players.doc(player.id), player);
				return 'ok' as const;
			});
		},
		async byId(id) {
			const found = await players.doc(id).get();
			return found.exists ? (found.data() as Player) : null;
		},
		async all(limit) {
			const found = await players.limit(limit).get();
			return found.docs.map((d) => d.data() as Player);
		}
	};
}

/**
 * One player's history with one board.
 *
 * Read-modify-write in a transaction, because two runs finishing at once would otherwise
 * lose a play between them — and unlike a lost run, a lost play is a board that goes back
 * to looking untouched.
 *
 * `forUser` filters on a single field, which Firestore indexes on its own; there is no
 * composite index to declare and none to forget at deploy time. `all` reads the
 * collection, which is what the standings fold over — see the note in `progress.ts` about
 * why that is affordable and when it stops being.
 */
export function firestoreProgress(db: Firestore, now: () => number = Date.now): ProgressStore {
	const progress = db.collection(collections.progress);

	return {
		async record(userId, run: Run) {
			const doc = progress.doc(progressKey(userId, run.puzzle));
			return db.runTransaction(async (tx) => {
				const found = await tx.get(doc);
				const folded = foldRun(
					found.exists ? (found.data() as Progress) : null,
					userId,
					run,
					now()
				);
				tx.set(doc, folded);
				return folded;
			});
		},
		async forUser(userId) {
			const found = await progress.where('userId', '==', userId).get();
			return found.docs.map((d) => d.data() as Progress);
		},
		async all(limit) {
			const found = await progress.limit(limit).get();
			return found.docs.map((d) => d.data() as Progress);
		}
	};
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
