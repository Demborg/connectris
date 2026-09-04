import { CHECKS, check, deal, swapTiles } from './engine';
import { recordBest, saveRun, type Best, type EventInput, type GameEvent } from './log';
import type { Group, Position, Puzzle, Row, SolvedRow } from './types';

export type Status = 'idle' | 'playing' | 'won' | 'lost';

/** The one thing a check says out loud: a count, and what it counts. */
export type Verdict = { count: number; note: string };

/**
 * The clearing wave, and its one direction: down. A row's four tiles light together —
 * nothing travels sideways, because a sideways roll inside each row reads as a second
 * animation crossing the one that matters — and each row starts well after the one above
 * it, so the clear still reads as rolling down the board row by row.
 */
export const LOCK_MS = 240;

/**
 * One row's whole life happens before the next one starts: it lights, it consolidates
 * into its bar, and it names its category, and only then does the row below light. The
 * alternative — every row lifting off first, then a second pass of labels rolling in —
 * is two waves where the player did one thing.
 */
const ROW_STEP = 420;

/** How long the wave's impact takes to play out, and how fast it travels on downward. */
export const CRASH_MS = 460;
export const RIPPLE_STEP = 60;

/**
 * Anticipation. The press runs up the board from the button before anything resolves,
 * so the wave is visibly caused by the thing the player just touched rather than simply
 * appearing at the top. The wave starts slightly before the sweep finishes.
 */
export const SWEEP_MS = 260;
const SWEEP_LEAD = 200;

/** A miss hits harder than a single-row clear and rings further down the stack. */
const MISS_AMP = 1.35;

const reducedMotion = () =>
	typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;

const wait = (ms: number) => new Promise((r) => setTimeout(r, reducedMotion() ? 0 : ms));

export class Session {
	readonly puzzle: Puzzle;

	rows = $state<Row[]>([]);
	solved = $state<SolvedRow[]>([]);
	moves = $state(0);
	checks = $state(0);
	status = $state<Status>('idle');

	/** Tile held by a tap, waiting for a second tap to swap with. */
	tile = $state<Position | null>(null);

	/** What the last check revealed: how many rows are right, never which. Pin 4. */
	verdict = $state<Verdict | null>(null);
	/** True while the top row is lifting off. Drives the tile clear animation. */
	lifting = $state(false);
	/** Rows in the clear currently playing, for how hard it lands. 0 when nothing is. */
	clearing = $state(0);
	/** True while the press is travelling up the board. */
	sweeping = $state(false);
	/** Rows taken by the last multi-row clear, while its flourish is on screen. */
	combo = $state(0);
	/** Strength of the wave's impact on the top remaining row, 0 when nothing is playing. */
	crash = $state(0);
	/** Whether that impact was a failed check rather than a clear landing. */
	crashMiss = $state(false);
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

	/** Checks still in hand. One counter now, not two — spending and counting are the same. */
	get left(): number {
		return CHECKS - this.checks;
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

	/** Whether input is accepted right now. Drag needs to ask before it starts. */
	get live(): boolean {
		return !this.over && !this.busy;
	}

	/** Exchange two tiles. The one verb the game has. */
	swap(a: Position, b: Position): void {
		if (!this.live) return;
		if (a.row === b.row && a.col === b.col) return;

		this.begin();
		this.rows = swapTiles(this.rows, a, b);
		this.moves++;
		this.record({ type: 'swapTiles', a: [a.row, a.col], b: [b.row, b.col] });
		this.tile = null;
	}

	/** Tap a tile: first tap holds it, second tap swaps. The keyboard-reachable path. */
	pickTile(pos: Position): void {
		if (!this.live) return;

		const held = this.tile;
		if (!held) {
			this.tile = pos;
			return;
		}
		if (held.row === pos.row && held.col === pos.col) {
			this.tile = null;
			return;
		}
		this.swap(held, pos);
	}

	clearSelection(): void {
		this.tile = null;
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
		this.verdict = null;

		this.sweeping = true;
		setTimeout(() => (this.sweeping = false), SWEEP_MS);
		await wait(SWEEP_LEAD);

		if (result.locked > 0) {
			await this.roll(result.locked);

			// The wave rolls on into whatever is left. The top remaining row is, by
			// definition, the one that stopped the run — so it takes the hit. A bigger
			// clear carries more momentum into it.
			if (this.rows.length > 0) {
				this.impact(Math.min(1.6, 1 + (result.locked - 1) * 0.2), false);
			}
			if (result.locked >= 2) {
				this.combo = result.locked;
				setTimeout(() => (this.combo = 0), 1200);
			}
		} else {
			// Nothing cleared means row 1 is wrong, so the wave has nowhere to go and slams
			// straight into it. Same motion as a clear landing — a miss is just the
			// degenerate case where the run of correct rows has length zero.
			this.impact(MISS_AMP, true);
		}

		this.record({
			type: 'check',
			locked: result.locked,
			correctCount: result.correctCount,
			left: this.left
		});

		// Only the count is worth saying. That a row cleared, that the board is solved, that
		// the lives ran out — the board and the end card already say all of it, and saying
		// it again in small type undercuts them.
		const remaining = result.correctCount - result.locked;
		// Order matters: a final check that clears the board wins even if it was the last one.
		if (this.rows.length === 0) this.finish('won');
		else if (this.left === 0) this.finish('lost');
		else if (result.locked > 0)
			this.verdict = remaining > 0 ? { count: remaining, note: 'more right · wrong order' } : null;
		else
			this.verdict = {
				count: result.correctCount,
				note: result.correctCount > 0 ? 'rows right · none at the top' : 'rows right'
			};

		this.busy = false;
	}

	/**
	 * Roll the wave down `count` rows, one row at a time. Each row lights, then converts
	 * into its solved bar before the row below it lights — so the board is only ever doing
	 * one thing rather than lifting every row off and then labelling them all again.
	 *
	 * A cleared row leaves `rows` the moment it lands and joins `solved` above it, so the
	 * row currently lifting is always row 0 and the board never changes height.
	 */
	private async roll(count: number): Promise<void> {
		this.clearing = count;

		for (let i = 0; i < count; i++) {
			this.lifting = true;
			await wait(LOCK_MS);

			const [row, ...rest] = this.rows;
			this.rows = rest;
			this.solved = [
				...this.solved,
				{
					group: this.puzzle.groups.find((g) => g.id === row[0].group)!,
					check: this.checks,
					order: i
				}
			];
			this.lifting = false;

			if (i < count - 1) await wait(ROW_STEP - LOCK_MS);
		}

		this.clearing = 0;
	}

	/** Land the wave on the top remaining row. A miss rings further down the stack. */
	private impact(amp: number, miss: boolean): void {
		this.crashMiss = miss;
		this.crash = amp;
		setTimeout(() => (this.crash = 0), CRASH_MS + (miss ? 4 : 2) * RIPPLE_STEP);
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
			checksLeft: this.left,
			moves: this.moves,
			checks: this.checks,
			events: this.events
		};
		saveRun(run);
		if (outcome === 'won') this.best = recordBest(this.puzzle.id, run);
	}
}
