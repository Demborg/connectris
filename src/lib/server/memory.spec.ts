import { describe } from 'vitest';
import {
	feedbackStoreContract,
	playerStoreContract,
	progressStoreContract,
	puzzleStoreContract,
	runStoreContract
} from './contract';
import { memoryFeedback, memoryPlayers, memoryProgress, memoryPuzzles, memoryRuns } from './memory';

describe('memory puzzle store', () => {
	puzzleStoreContract(async (published, upcoming) =>
		memoryPuzzles([...published, ...upcoming], published.length)
	);
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

describe('memory player store', () => {
	playerStoreContract(async () => memoryPlayers());
});

describe('memory progress store', () => {
	progressStoreContract(async () => memoryProgress());
});
