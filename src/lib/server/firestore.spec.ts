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
import { scheduleEndingToday } from './memory';

/**
 * The Firestore adapters, against the emulator, held to the same contract as the in-memory
 * and file ones.
 *
 * Skipped unless `FIRESTORE_EMULATOR_HOST` is set, which is CI's job — the emulator wants
 * a Java runtime that a laptop has no reason to carry. Never pointed at a real database:
 * these tests wipe the collections they use.
 */
const emulating = Boolean(process.env.FIRESTORE_EMULATOR_HOST);

describe.skipIf(!emulating)('firestore stores', () => {
	const db = connect({ projectId: 'connectris-contract' });

	async function wipe(name: string): Promise<void> {
		const docs = await db.collection(name).listDocuments();
		await Promise.all(docs.map((d) => d.delete()));
	}

	describe('puzzles', () => {
		puzzleStoreContract(async (given, today) => {
			await wipe(collections.puzzles);
			await Promise.all(
				[...scheduleEndingToday(given, today)].map(([day, p]) =>
					db
						.collection(collections.puzzles)
						.doc(p.id)
						.set(puzzleDoc(p, day, 'contract'))
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
