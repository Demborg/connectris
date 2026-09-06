import { expect, it } from 'vitest';
import { shift, today } from './day';

it('names the day a moment falls on, in UTC', () => {
	expect(today(new Date('2026-09-06T23:59:59Z'))).toBe('2026-09-06');
	expect(today(new Date('2026-09-07T00:00:00Z'))).toBe('2026-09-07');
});

it('steps across the ends of months and years', () => {
	// Written out because the arithmetic is the whole function, and off-by-one here is a
	// day with two boards or none.
	expect(shift('2026-12-31', 1)).toBe('2027-01-01');
	expect(shift('2027-01-01', -1)).toBe('2026-12-31');
	expect(shift('2028-02-28', 1)).toBe('2028-02-29');
	expect(shift('2026-02-28', 1)).toBe('2026-03-01');
});

it('steps across a daylight-saving boundary without losing a day', () => {
	// The generator runs in europe-north1, where the clocks move on the last Sunday in
	// March. A date built from a local time would repeat or skip a day here; these are
	// instants at UTC midnight, so they cannot.
	expect(shift('2026-03-28', 1)).toBe('2026-03-29');
	expect(shift('2026-03-29', 1)).toBe('2026-03-30');
});

it('is its own inverse', () => {
	expect(shift(shift('2026-09-06', 7), -7)).toBe('2026-09-06');
});
