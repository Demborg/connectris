import { describe, expect, it } from 'vitest';
import { daysBefore, fixedClock } from './day';
import { memoryFeedback, memoryPuzzles, memoryRuns, scheduleEndingToday } from './memory';
import { boards, feedbackStoreContract, puzzleStoreContract, runStoreContract } from './contract';

describe('daysBefore', () => {
	it('walks back over a month boundary', () => {
		expect(daysBefore('2026-03-01', 3)).toBe('2026-02-26');
	});

	it('walks back over a year boundary', () => {
		expect(daysBefore('2026-01-01', 1)).toBe('2025-12-31');
	});

	it('stays put at zero', () => {
		expect(daysBefore('2026-09-05', 0)).toBe('2026-09-05');
	});
});

describe('fixedClock', () => {
	it('says whatever day it was told', () => {
		expect(fixedClock('2026-09-05').today()).toBe('2026-09-05');
	});
});

describe('scheduleEndingToday', () => {
	it('lands the last board on today and walks the rest back a day at a time', () => {
		const days = [...scheduleEndingToday(boards, '2026-09-05').keys()].sort();
		expect(days).toEqual(['2026-09-03', '2026-09-04', '2026-09-05']);
	});
});

describe('memory puzzle store', () => {
	puzzleStoreContract(async (b, today) => memoryPuzzles(b, today));
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
