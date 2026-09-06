import { describe } from 'vitest';
import { feedbackStoreContract, puzzleStoreContract, runStoreContract } from './contract';
import { memoryFeedback, memoryPuzzles, memoryRuns } from './memory';

describe('memory puzzle store', () => {
	puzzleStoreContract(async (given) => memoryPuzzles(given));
});

describe('memory run store', () => {
	runStoreContract(async () => {
		const store = memoryRuns();
		return { store, recorded: async () => store.all() };
	});
});

describe('memory feedback store', () => {
	feedbackStoreContract(async () => {
		const store = memoryFeedback();
		return { store, recorded: async () => store.all() };
	});
});
