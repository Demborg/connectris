import { randomId } from '$lib/user';
import { CHECKS, swapTiles } from './engine';
import { saveRun, type Best, type EventInput, type GameEvent } from './log';
import { noReporter, type Reporter } from './report';
import type {
	Board,
	CheckOutcome,
	Checker,
	Group,
	Position,
	PuzzleMeta,
	Row,
	SolvedRow
} from './types';

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

/** How long the last callout stays up once the wave has finished rolling. */
const COMBO_HOLD = 1100;

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

/**
 * Reduced motion removes motion. It does not remove sequence.
 *
 * Every clock in this file goes through one of the two helpers below, and which one a
 * clock uses is the whole of the accommodation.
 *
 * The distinction: app.css already collapses every CSS animation and transition under the
 * preference, so a *hold* — time reserved for a flourish to play — has nothing left to
 * show and can go to zero. A *gap* is different. "One row's whole life, then the next" is
 * how a player reads which row cleared when, and that reading survives having the
 * transforms taken away; collapsing the gaps too is what made a five-row clear resolve in
 * 86ms with all five categories appearing at once, which is not less motion, it is less
 * information.
 *
 * The cost is nothing: a reduced-motion player used to reach the end card in ~1.18s
 * anyway, because a bare `setTimeout` held it behind the combo callout for 1.1s of
 * finished, motionless board. The same second now goes on five legible row events.
 */

/** How much of a gap survives the preference, and the least that still reads as separate. */
const REDUCED_PACE = 0.6;
const REDUCED_FLOOR = 90;

/** A hold: time for a flourish to play. Nothing to play, nothing to hold. */
const beat = (ms: number) => (reducedMotion() ? 0 : ms);

/** A gap: what makes two events read as two events. Shortened, never removed. */
const pace = (ms: number) =>
	reducedMotion() ? Math.max(REDUCED_FLOOR, Math.round(ms * REDUCED_PACE)) : ms;

const wait = (ms: number) => new Promise<void>((r) => setTimeout(r, beat(ms)));

/** `wait()` for the clocks that carry sequence rather than motion. */
const step = (ms: number) => new Promise<void>((r) => setTimeout(r, pace(ms)));

export class Session {
	readonly puzzle: PuzzleMeta;
	/**
	 * This run's id, minted before it starts because feedback is filed against it — the
	 * answers to "how was that" belong to the run that provoked them.
	 */
	readonly id = randomId();
	/** Whoever holds the answer key. This class never sees it. */
	private readonly grade: Checker;
	private readonly report: Reporter;

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
	/**
	 * The category of the row currently lifting. The board needs it to land those tiles on
	 * the colour their solved bar will use — and it is the only category the player is
	 * allowed to know about before the row has cleared.
	 */
	liftingGroup = $state<Group | null>(null);
	/** Rows in the clear currently playing, for how hard it lands. 0 when nothing is. */
	clearing = $state(0);
	/** True while the press is travelling up the board. */
	sweeping = $state(false);
	/**
	 * Rows the current clear has taken so far, while its flourish is on screen. It counts
	 * up as the wave rolls — DOUBLE, then TRIPLE — rather than being announced once at the
	 * end, so the callout is a running tally of the thing happening rather than a receipt
	 * for it.
	 */
	combo = $state(0);
	/** Strength of the wave's impact on the top remaining row, 0 when nothing is playing. */
	crash = $state(0);
	/** Whether that impact was a failed check rather than a clear landing. */
	crashMiss = $state(false);
	/**
	 * This player's best on this board, and where they stand — both the server's answer,
	 * both arriving after the run has been posted.
	 *
	 * Late rather than immediate, which is the trade for having one number instead of two.
	 * A best kept in localStorage could be shown the instant a run ended, but it was a
	 * second opinion: it disagreed with the standings, with the boards page, and with the
	 * same player's other phone. The card copes by simply not showing a line it does not
	 * have yet.
	 */
	best = $state<Best | undefined>(undefined);
	standing = $state<{ place: number; of: number } | null>(null);
	/** Categories never found, revealed once the run is lost. Only a grader can name them. */
	missed = $state<Group[]>([]);
	/**
	 * Set when a check could not be graded at all. The run is not over and the check was
	 * refunded — but the player pressed a button and nothing happened, so say why.
	 */
	fault = $state<string | null>(null);

	/**
	 * True from the press until the check has finished playing out.
	 *
	 * Reactive because the controls have to say so. `check()` and `swap()` have always
	 * refused input while this is set, but nothing on screen reported it: through a slow
	 * grade or a multi-row roll the Check button and every remaining tile kept their
	 * pointer cursor and their press animation, so they looked live while being inert.
	 */
	busy = $state(false);
	/**
	 * The last swap, phrased for a screen reader. The board is a flat run of buttons whose
	 * only accessible name is their word, so a swap is otherwise silent.
	 */
	announcement = $state('');

	startedAt = 0;
	endedAt = 0;
	private events: GameEvent[] = [];
	private comboTimer: ReturnType<typeof setTimeout> | undefined;

	constructor(board: Board, grade: Checker, report: Reporter = noReporter) {
		this.puzzle = board.puzzle;
		this.rows = board.rows;
		this.grade = grade;
		this.report = report;
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
		const moved = this.rows[a.row][a.col].word;
		const displaced = this.rows[b.row][b.col].word;
		this.rows = swapTiles(this.rows, a, b);
		this.moves++;
		this.record({ type: 'swapTiles', a: [a.row, a.col], b: [b.row, b.col] });
		this.tile = null;
		// Which row each word ended in is the whole game, and it is the one thing a flat
		// list of buttons cannot convey.
		this.announcement = `${moved} to row ${b.row + 1}, ${displaced} to row ${a.row + 1}.`;
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

		this.fault = null;
		// The check is not spent until it has been answered. Charging first and refunding
		// on failure is the same arithmetic, but it renders: the pip dropped and ran its
		// 560ms spend flash before the request had left, so every failed check was a check
		// the player watched themselves be charged and then handed back — for as long as
		// the network took to give up, which is not bounded by anything here. The grader
		// still has to be told which check this is, so it counts from the spend to come.
		const spending = this.checks + 1;
		const grading = this.grade(this.rows, spending);

		// Drop the previous verdict and callout now, so neither is left standing over the
		// clear animation this check is about to play.
		this.verdict = null;
		clearTimeout(this.comboTimer);
		this.combo = 0;

		this.sweeping = true;
		// The sweep has a minimum length of its own, but it ends when the grade lands, not
		// on a fixed timer. A grader slower than the sweep — a scaled-to-zero instance
		// cold-starting, say — used to run the rails up, finish them, and leave the player
		// looking at an inert board and a fully lit Check button.
		const swept = wait(SWEEP_MS);

		// The anticipation sweep is also the latency budget. It has to run before anything
		// resolves anyway, so a grader that answers inside it is one the player never waits
		// for — which is what makes grading somewhere else affordable.
		let result: CheckOutcome | null = null;
		try {
			[result] = await Promise.all([grading, wait(SWEEP_LEAD)]);
		} catch {
			// A check that never came back is not a check, and was never spent. An
			// unreachable grader is not a wrong answer, and charging for one would end runs
			// that the puzzle never beat. Pin 5.
			this.fault = "Couldn't check — no connection. That one's free, try again.";
		}
		void swept.then(() => (this.sweeping = false));
		if (result === null) {
			this.busy = false;
			return;
		}

		this.checks = spending;

		// The impact is held onto rather than fired and forgotten, because on the last
		// check of a lost run the reveal has to wait for it. See the loss branch below.
		let landed = Promise.resolve();
		if (result.locked > 0) {
			await this.roll(result.cleared);

			// The wave rolls on into whatever is left. The top remaining row is, by
			// definition, the one that stopped the run — so it takes the hit. A bigger
			// clear carries more momentum into it.
			if (this.rows.length > 0) {
				landed = this.impact(Math.min(1.6, 1 + (result.locked - 1) * 0.2), false);
			}
		} else {
			// Nothing cleared means row 1 is wrong, so the wave has nowhere to go and slams
			// straight into it. Same motion as a clear landing — a miss is just the
			// degenerate case where the run of correct rows has length zero.
			landed = this.impact(MISS_AMP, true);
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
		if (this.rows.length === 0) this.finish('won', []);
		else if (this.left === 0) {
			// Let the crash finish before the board converts. Both used to land in one
			// synchronous block, so `status` was 'lost' and the tiles were gone before a
			// single frame had been painted with the crash on them — the run ended with no
			// crash, no verdict, and the board simply emptying under a rising card. The
			// crash *is* the feedback: it points at where the run broke, and on the last
			// check it is the only explanation the game offers. Pin 5.
			await landed;
			this.finish('lost', result.missed);
		} else if (result.locked > 0)
			this.verdict = remaining > 0 ? { count: remaining, note: 'more right · wrong order' } : null;
		else {
			// "1 rows right" is reachable, common, and sits in the one sentence the game
			// writes in words.
			const rows = result.correctCount === 1 ? 'row' : 'rows';
			this.verdict = {
				count: result.correctCount,
				note: result.correctCount > 0 ? `${rows} right · none at the top` : `${rows} right`
			};
		}

		this.busy = false;
	}

	/**
	 * Roll the wave down `count` rows, one row at a time. Each row lights, then converts
	 * into its solved bar before the row below it lights — so the board is only ever doing
	 * one thing, and the callout can count up as it goes.
	 *
	 * A cleared row leaves `rows` the moment it lands and joins `solved` above it, so the
	 * row currently lifting is always row 0 and the board never changes height.
	 */
	private async roll(cleared: Group[]): Promise<void> {
		this.clearing = cleared.length;

		for (const [i, group] of cleared.entries()) {
			const [, ...rest] = this.rows;

			this.liftingGroup = group;
			this.lifting = true;
			// Both waits in this loop are gaps, not holds: they are what separates a row
			// lighting from it becoming a bar, and one row from the next.
			await step(LOCK_MS);

			this.rows = rest;
			this.solved = [...this.solved, { group, check: this.checks, order: i }];
			this.lifting = false;
			this.liftingGroup = null;

			// Only from the second row on is there anything to shout about, and from there
			// the shout grows with the tally rather than waiting for the final figure.
			if (i >= 1) this.combo = i + 1;

			if (i < cleared.length - 1) await step(ROW_STEP - LOCK_MS);
		}

		this.clearing = 0;
		if (this.combo > 0) this.comboTimer = setTimeout(() => (this.combo = 0), beat(COMBO_HOLD));
	}

	/**
	 * Land the wave on the top remaining row. A miss rings further down the stack.
	 *
	 * Resolves when the impact has finished playing, so a caller that needs the crash to
	 * be seen before it changes the board can wait for it.
	 */
	private impact(amp: number, miss: boolean): Promise<void> {
		this.crashMiss = miss;
		this.crash = amp;
		return wait(CRASH_MS + (miss ? 4 : 2) * RIPPLE_STEP).then(() => {
			this.crash = 0;
		});
	}

	private finish(outcome: 'won' | 'lost', missed: Group[]): void {
		this.status = outcome;
		this.missed = missed;
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

		// Not awaited: the card is already on screen and the run is already local. What
		// comes back only ever adds a line to it.
		void this.report(this.id, run).then((recorded) => {
			if (!recorded) return;
			this.best = recorded.best ?? undefined;
			this.standing =
				recorded.place && recorded.of ? { place: recorded.place, of: recorded.of } : null;
		});
	}
}
