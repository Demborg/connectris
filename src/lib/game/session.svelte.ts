import { COLS, LIVES, check, deal, swapRows, swapTiles } from './engine';
import { recordBest, saveRun, type Best, type EventInput, type GameEvent } from './log';
import type { Group, Position, Puzzle, Row, SolvedRow } from './types';

export type Status = 'idle' | 'playing' | 'won' | 'lost';

/**
 * The clearing wave. Tiles within a row light up in quick succession, and each row
 * starts well after the one above it — so the clear reads as rolling down the board
 * row by row rather than as one undifferentiated flash.
 */
export const ROW_STAGGER = 170;
export const TILE_STAGGER = 45;
const POP = 260;
const SETTLE = 120;

/** How long the wave's impact takes to play out, and how fast it travels on downward. */
export const CRASH_MS = 460;
export const RIPPLE_STEP = 60;

/** How long the wave takes to cross `rows` rows before they consolidate. */
export const lockDuration = (rows: number) =>
	(rows - 1) * ROW_STAGGER + (COLS - 1) * TILE_STAGGER + POP + SETTLE;

const reducedMotion = () =>
	typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;

const wait = (ms: number) => new Promise((r) => setTimeout(r, reducedMotion() ? 0 : ms));

export class Session {
	readonly puzzle: Puzzle;

	rows = $state<Row[]>([]);
	solved = $state<SolvedRow[]>([]);
	lives = $state(LIVES);
	moves = $state(0);
	checks = $state(0);
	status = $state<Status>('idle');

	/** Selected tile, or selected row rank — never both. */
	tile = $state<Position | null>(null);
	row = $state<number | null>(null);

	feedback = $state('');
	/** Rows currently lifting off. Drives the clear animation. */
	locking = $state(0);
	/** Bumped on a failed check so the board can shake. */
	shake = $state(0);
	/** Rows taken by the last multi-row clear, while its flourish is on screen. */
	combo = $state(0);
	/** Strength of the wave's impact on the top remaining row, 0 when nothing is playing. */
	crash = $state(0);
	best = $state<Best | undefined>(undefined);

	startedAt = 0;
	endedAt = 0;
	private events: GameEvent[] = [];
	private busy = false;

	constructor(puzzle: Puzzle) {
		this.puzzle = puzzle;
		this.rows = deal(puzzle);
	}

	get elapsedMs(): number {
		if (this.status === 'idle') return 0;
		return (this.endedAt || Date.now()) - this.startedAt;
	}

	get over(): boolean {
		return this.status === 'won' || this.status === 'lost';
	}

	/** Categories never found, revealed once the run is lost. */
	get missed(): Group[] {
		if (this.status !== 'lost') return [];
		return this.puzzle.groups.filter((g) => !this.solved.some((s) => s.group.id === g.id));
	}

	private begin(): void {
		if (this.status !== 'idle') return;
		this.status = 'playing';
		this.startedAt = Date.now();
		this.events.push({ t: 0, type: 'start', puzzle: this.puzzle.id });
	}

	private record(event: EventInput): void {
		this.events.push({ ...event, t: Date.now() - this.startedAt } as GameEvent);
	}

	/* ---------------------------------------------------------------------- */
	/* Input                                                                   */
	/* ---------------------------------------------------------------------- */

	/** Tap a tile: first tap selects, second tap swaps. */
	pickTile(pos: Position): void {
		if (this.over || this.busy) return;
		this.row = null;

		const held = this.tile;
		if (!held) {
			this.tile = pos;
			return;
		}
		if (held.row === pos.row && held.col === pos.col) {
			this.tile = null;
			return;
		}

		this.begin();
		this.rows = swapTiles(this.rows, held, pos);
		this.moves++;
		this.record({ type: 'swapTiles', a: [held.row, held.col], b: [pos.row, pos.col] });
		this.tile = null;
	}

	/** Tap a rank: first tap selects the row, second tap swaps the two rows. One move. */
	pickRow(index: number): void {
		if (this.over || this.busy) return;
		this.tile = null;

		const held = this.row;
		if (held === null) {
			this.row = index;
			return;
		}
		if (held === index) {
			this.row = null;
			return;
		}

		this.begin();
		this.rows = swapRows(this.rows, held, index);
		this.moves++;
		this.record({ type: 'swapRows', a: held, b: index });
		this.row = null;
	}

	clearSelection(): void {
		this.tile = null;
		this.row = null;
	}

	/* ---------------------------------------------------------------------- */
	/* Checking                                                                */
	/* ---------------------------------------------------------------------- */

	async check(): Promise<void> {
		if (this.over || this.busy) return;
		this.busy = true;
		this.begin();
		this.clearSelection();

		const result = check(this.rows);
		this.checks++;
		// Drop the previous verdict now, so it isn't left standing over the clear animation.
		this.feedback = '';

		if (result.locked > 0) {
			this.locking = result.locked;
			await wait(lockDuration(result.locked));
			const cleared = this.rows.slice(0, result.locked);
			this.rows = this.rows.slice(result.locked);
			this.solved = [
				...this.solved,
				...cleared.map((r, order) => ({
					group: this.puzzle.groups.find((g) => g.id === r[0].group)!,
					check: this.checks,
					order
				}))
			];
			this.locking = 0;

			// The wave rolls on into whatever is left. The top remaining row is, by
			// definition, the one that stopped the run — so it takes the hit. A bigger
			// clear carries more momentum into it.
			if (this.rows.length > 0) {
				this.crash = Math.min(1.6, 1 + (result.locked - 1) * 0.2);
				setTimeout(() => (this.crash = 0), CRASH_MS + 2 * RIPPLE_STEP);
			}
			if (result.locked >= 2) {
				this.combo = result.locked;
				setTimeout(() => (this.combo = 0), 1200);
			}
		} else {
			this.lives--;
			this.shake++;
		}

		this.record({
			type: 'check',
			locked: result.locked,
			correctCount: result.correctCount,
			livesLeft: this.lives
		});

		const remaining = result.correctCount - result.locked;
		if (this.rows.length === 0) {
			this.feedback = 'Solved.';
			this.finish('won');
		} else if (this.lives === 0) {
			this.feedback = 'Out of lives.';
			this.finish('lost');
		} else if (result.locked > 0) {
			this.feedback =
				remaining > 0
					? `Cleared ${result.locked}. ${remaining} of the rows below ${remaining === 1 ? 'is' : 'are'} already right — wrong order.`
					: `Cleared ${result.locked}.`;
		} else if (result.correctCount > 0) {
			this.feedback = `${result.correctCount} rows are right — none of them at the top.`;
		} else {
			this.feedback = 'No rows correct.';
		}

		this.busy = false;
	}

	private finish(outcome: 'won' | 'lost'): void {
		this.status = outcome;
		this.endedAt = Date.now();
		this.record({ type: 'end', outcome });

		const run = {
			puzzle: this.puzzle.id,
			startedAt: this.startedAt,
			outcome,
			timeMs: this.elapsedMs,
			livesLeft: this.lives,
			moves: this.moves,
			checks: this.checks,
			events: this.events
		};
		saveRun(run);
		if (outcome === 'won') this.best = recordBest(this.puzzle.id, run);
	}
}
