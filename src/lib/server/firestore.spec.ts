import { PassThroughClient } from 'google-auth-library';
import { describe } from 'vitest';
import { feedbackStoreContract, puzzleStoreContract, runStoreContract } from './contract';
import {
	collections,
	connect,
	firestoreFeedback,
	firestorePuzzles,
	firestoreRuns,
	puzzleDoc
} from './firestore';
import type { Feedback, RunRecord } from './ports';

/**
 * The Firestore adapters, against the emulator, held to the same contract as the in-memory
 * and file ones.
 *
 * Skipped unless `FIRESTORE_EMULATOR_HOST` is set, which is CI's job — the emulator wants
 * a Java runtime that a laptop has no reason to carry. Never pointed at a real database:
 * these tests wipe the collections they use.
 *
 * The emulator needs no credentials, but `preferRest` still asks for them: the REST path
 * goes through google-gax's fallback stub, which calls `GoogleAuth.getClient()` before it
 * will send anything, and that reaches for Application Default Credentials whatever
 * `FIRESTORE_EMULATOR_HOST` says. The gRPC path skips this — it swaps in insecure channel
 * credentials when it sees the emulator — which is why this only bites the transport
 * production actually uses. On a CI runner with no ADC the lookup hangs on the metadata
 * server until every test times out. `PassThroughClient` sends the request unsigned, which
 * is what the emulator wants anyway, and keeps these tests on REST rather than quietly
 * exercising a transport we do not deploy.
 */
const emulating = Boolean(process.env.FIRESTORE_EMULATOR_HOST);

describe.skipIf(!emulating)('firestore stores', () => {
	const db = connect({ projectId: 'connectris-contract', authClient: new PassThroughClient() });

	async function wipe(name: string): Promise<void> {
		const docs = await db.collection(name).listDocuments();
		await Promise.all(docs.map((d) => d.delete()));
	}

	describe('puzzles', () => {
		puzzleStoreContract(async (given) => {
			await wipe(collections.puzzles);
			await Promise.all(
				given.map((p, i) =>
					db
						.collection(collections.puzzles)
						.doc(p.id)
						.set(puzzleDoc(p, i, 'contract'))
				)
			);
			return firestorePuzzles(db);
		});
	});

	describe('runs', () => {
		runStoreContract(async () => {
			await wipe(collections.runs);
			return {
				store: firestoreRuns(db),
				recorded: async () =>
					(await db.collection(collections.runs).get()).docs.map((d) => d.data() as RunRecord)
			};
		});
	});

	describe('feedback', () => {
		feedbackStoreContract(async () => {
			await wipe(collections.feedback);
			return {
				store: firestoreFeedback(db),
				recorded: async () =>
					(await db.collection(collections.feedback).get()).docs.map((d) => d.data() as Feedback)
			};
		});
	});
});
