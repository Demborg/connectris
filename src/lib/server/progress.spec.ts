import { describe, expect, it } from 'vitest';
import type { Run } from '$lib/game/log';
import { playOf, playerOf } from './contract';
import type { Player, Progress } from './ports';
import { foldRun, placeOf, rank, type Standing } from './progress';

const at = 1_700_000_000_000;

const fold = (prev: Progress | null, over: Partial<Run> = {}) =>
	foldRun(prev, 'ada', playOf(over), at);

describe('foldRun', () => {
	it('starts a record from a first run', () => {
		expect(fold(null, { puzzle: 'p1', outcome: 'lost' })).toEqual({
			userId: 'ada',
			puzzleId: 'p1',
			plays: 1,
			best: null,
			updatedAt: at
		});
	});

	it('counts plays across every attempt', () => {
		const once = fold(null, { outcome: 'lost' });
		expect(fold(once, { outcome: 'lost' }).plays).toBe(2);
	});

	it('lets only a win set a best', () => {
		expect(fold(null, { outcome: 'won', checksLeft: 2 }).best).toMatchObject({ checksLeft: 2 });
		expect(fold(null, { outcome: 'lost' }).best).toBeNull();
	});

	it('never takes a best away', () => {
		// Replaying a solved board is the ordinary case — the picker walks the archive —
		// and it must not be possible to lose a solve by playing again.
		const solved = fold(null, { outcome: 'won', checksLeft: 3, timeMs: 40_000 });
		const after = fold(solved, { outcome: 'lost', checksLeft: 0, timeMs: 10_000 });

		expect(after.best).toMatchObject({ checksLeft: 3, timeMs: 40_000 });
	});
});

/** A player with a board or two behind them, for the fold to reduce. */
const solve = (userId: string, puzzleId: string, checksLeft: number, timeMs: number): Progress => ({
	userId,
	puzzleId,
	plays: 1,
	best: { checksLeft, timeMs, moves: 0, checks: 4 - checksLeft },
	updatedAt: at
});

const attempt = (userId: string, puzzleId: string): Progress => ({
	userId,
	puzzleId,
	plays: 1,
	best: null,
	updatedAt: at
});

const roster: Player[] = [
	playerOf({ id: 'ada', alias: 'Ada' }),
	playerOf({ id: 'bo', alias: 'Bo' }),
	playerOf({ id: 'cy', alias: 'Cy' })
];

const order = (standings: Standing[]) => standings.map((s) => s.alias);

describe('rank', () => {
	it('puts whoever solved most first', () => {
		const listed = rank(roster, [
			solve('ada', 'p1', 1, 300_000),
			solve('bo', 'p1', 3, 10_000),
			solve('bo', 'p2', 3, 10_000)
		]);

		expect(order(listed).slice(0, 2)).toEqual(['Bo', 'Ada']);
	});

	it('breaks a tie on checks left before time', () => {
		// The same rule a personal best uses, applied to a whole player. Spending checks
		// well is the game; being quick is the tiebreak.
		const listed = rank(roster, [solve('ada', 'p1', 3, 300_000), solve('bo', 'p1', 1, 10_000)]);

		expect(order(listed).slice(0, 2)).toEqual(['Ada', 'Bo']);
	});

	it('breaks a full tie on time', () => {
		const listed = rank(roster, [solve('ada', 'p1', 2, 90_000), solve('bo', 'p1', 2, 40_000)]);

		expect(order(listed).slice(0, 2)).toEqual(['Bo', 'Ada']);
	});

	it('totals only the boards that were solved', () => {
		const listed = rank(roster, [solve('ada', 'p1', 2, 90_000), attempt('ada', 'p2')]);
		const ada = listed.find((s) => s.alias === 'Ada')!;

		expect(ada).toMatchObject({ solved: 1, played: 2, checksLeft: 2, timeMs: 90_000 });
	});

	it('lists a registered player who has never played, at the bottom', () => {
		// A standings page you registered for and cannot find yourself on reads as broken.
		const listed = rank(roster, [solve('ada', 'p1', 2, 90_000)]);

		expect(listed).toHaveLength(3);
		expect(listed[0].alias).toBe('Ada');
		expect(listed.slice(1).every((s) => s.solved === 0)).toBe(true);
	});

	it('ignores progress belonging to nobody registered', () => {
		// A browser that played before registration existed. Its boards are not lost —
		// registering adopts the id and they arrive with it — but until then there is no
		// name to put on a row.
		const listed = rank(roster, [solve('ghost', 'p1', 3, 10_000)]);

		expect(listed.map((s) => s.userId)).not.toContain('ghost');
		expect(listed.every((s) => s.solved === 0)).toBe(true);
	});

	it('orders the same way twice, whoever played last', () => {
		const one = rank(roster, [solve('ada', 'p1', 2, 90_000), solve('bo', 'p1', 2, 90_000)]);
		const two = rank([...roster].reverse(), [
			solve('bo', 'p1', 2, 90_000),
			solve('ada', 'p1', 2, 90_000)
		]);

		expect(order(one)).toEqual(order(two));
	});
});

describe('placeOf', () => {
	it('counts from one', () => {
		const listed = rank(roster, [solve('bo', 'p1', 3, 10_000)]);
		expect(placeOf(listed, 'bo')).toBe(1);
	});

	it('answers zero for somebody who is not on the list', () => {
		expect(placeOf(rank(roster, []), 'ghost')).toBe(0);
	});
});
