<script lang="ts">
	import { flip } from 'svelte/animate';
	import SolvedRow from './SolvedRow.svelte';
	import Tile from './Tile.svelte';
	import { RIPPLE_STEP } from '$lib/game/session.svelte';
	import type { Session } from '$lib/game/session.svelte';
	import type { Position } from '$lib/game/types';

	let { session }: { session: Session } = $props();

	const COLOURS = ['var(--g1)', 'var(--g2)', 'var(--g3)', 'var(--g4)', 'var(--g5)'];
	const colourOf = (group: string) =>
		COLOURS[session.puzzle.groups.findIndex((g) => g.id === group)] ?? 'var(--accent)';

	/**
	 * Rows the player is finished with: cleared first, then the ones revealed by a loss.
	 * Once the run is lost the remaining tiles come off the board entirely — their words
	 * are all listed in the revealed rows, and leaving both on screen doubled the board's
	 * height and broke the one-board-height rule.
	 */
	let done = $derived([
		...session.solved.map((s) => ({
			key: s.group.id,
			group: s.group,
			missed: false,
			order: s.order
		})),
		...session.missed.map((g, i) => ({ key: g.id, group: g, missed: true, order: i }))
	]);
	let active = $derived(session.status === 'lost' ? [] : session.rows);

	let tiles = $derived(
		active.flatMap((row, r) =>
			row.map((tile, c) => ({ key: `tile-${tile.id}`, row: r, col: c, tile }) as const)
		)
	);

	/**
	 * Rows are ranked by how sure the player is, and the top one is the one a check
	 * reaches first — so the frames fade as they go down. Linear with a floor, not a
	 * decay: the bottom row still has to read as a container, or the tiering wins the
	 * argument about order at the cost of the one about rows being the unit.
	 *
	 * Neutral, never hued: colour on this board means category and is not spent on
	 * anything else.
	 */
	const tier = (rank: number) => 26 - rank * 5;

	// The impact lands on the top remaining row and loses strength each row further down,
	// so the shock visibly travels rather than shaking the whole board. A clear is absorbed
	// quickly by the rows that took it; a miss was absorbed by nothing, so it rings all the
	// way down the stack.
	let decay = $derived(session.crashMiss ? 0.22 : 0.45);
	const crashAmp = (row: number) => Math.max(0, session.crash * (1 - row * decay));

	// A bigger clear hits harder and glows brighter.
	let boost = $derived(session.clearing > 1 ? Math.min(1.6, 1 + (session.clearing - 1) * 0.2) : 1);

	/* ------------------------------------------------------------------------ */
	/* Dragging                                                                  */
	/* ------------------------------------------------------------------------ */

	/** Movement before a press counts as a drag rather than a tap. */
	const SLOP = 6;

	type Drag = { from: Position; dx: number; dy: number; moved: boolean };
	let drag = $state<Drag | null>(null);
	let over = $state<Position | null>(null);
	let origin = { x: 0, y: 0 };
	// Tap handling stays on `click` so the board keeps working from the keyboard, but a
	// finished drag can also fire one. A timestamp rather than a flag: a drag that ends
	// without a click (dropping outside the tile it started on) must not leave a flag
	// armed to eat the player's next real tap.
	let draggedAt = 0;
	const justDragged = () => performance.now() - draggedAt < 150;

	const samePos = (a: Position | null, b: Position) => a?.row === b.row && a?.col === b.col;

	/**
	 * Which tile is under the pointer. The dragged tile is on top and would always find
	 * itself, so walk the hit stack and take the first one that isn't the one in hand.
	 */
	function tileAt(x: number, y: number, from: Position): Position | null {
		for (const el of document.elementsFromPoint(x, y)) {
			const cell = el.closest<HTMLElement>('[data-row]');
			if (!cell) continue;
			const pos = { row: Number(cell.dataset.row), col: Number(cell.dataset.col) };
			if (!samePos(from, pos)) return pos;
		}
		return null;
	}

	function start(event: PointerEvent, from: Position) {
		if (!session.live) return;
		origin = { x: event.clientX, y: event.clientY };
		drag = { from, dx: 0, dy: 0, moved: false };
		(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
	}

	function move(event: PointerEvent) {
		if (!drag) return;
		const dx = event.clientX - origin.x;
		const dy = event.clientY - origin.y;
		const moved = drag.moved || Math.hypot(dx, dy) > SLOP;
		drag = { ...drag, dx, dy, moved };
		if (!moved) return;

		// A drag is its own gesture; it shouldn't leave a tap selection behind.
		session.clearSelection();
		over = tileAt(event.clientX, event.clientY, drag.from);
	}

	function end(event: PointerEvent) {
		if (!drag) return;
		const { from, moved } = drag;
		const target = moved ? tileAt(event.clientX, event.clientY, from) : null;
		drag = null;
		over = null;

		// A press that never moved is a tap; let the click handler take it.
		if (!moved) return;
		draggedAt = performance.now();
		if (target) session.swap(from, target);
	}

	function cancel() {
		if (drag?.moved) draggedAt = performance.now();
		drag = null;
		over = null;
	}

	function tap(pos: Position) {
		if (justDragged()) return;
		session.pickTile(pos);
	}
</script>

<div
	class="grid"
	style:--boost={boost}
	style:--jolt={session.crashMiss ? 'var(--danger)' : 'var(--accent)'}
>
	{#each done as d, i (d.key)}
		<div class="band" style:grid-row={i + 1}>
			<SolvedRow
				group={d.group}
				colour={colourOf(d.group.id)}
				missed={d.missed}
				enterDelay={d.missed ? d.order * 90 : 0}
			/>
		</div>
	{/each}

	<!-- One frame per row still in play, drawn behind the tiles. Rows are the entity the
	     game is played in, so each one gets a container of its own. -->
	<!-- Unkeyed on purpose: frames are positional, never reorder, and never animate. -->
	{#each active, r}
		<div
			class="frame"
			style:grid-row={done.length + r + 1}
			style:--edge="rgb(255 255 255 / {tier(r).toFixed(1)}%)"
			style:--fill="rgb(255 255 255 / {(tier(r) * 0.25).toFixed(1)}%)"
		></div>
	{/each}

	{#each tiles as cell (cell.key)}
		<div
			class="slot"
			class:lifted={!!drag?.moved && samePos(drag.from, cell)}
			style:grid-row={done.length + cell.row + 1}
			style:grid-column={cell.col + 1}
			animate:flip={{ duration: 300 }}
		>
			<Tile
				tile={cell.tile}
				selected={samePos(session.tile, cell)}
				dragging={!!drag?.moved && samePos(drag.from, cell)}
				target={samePos(over, cell)}
				offset={drag?.moved && samePos(drag.from, cell)
					? { x: drag.dx, y: drag.dy }
					: { x: 0, y: 0 }}
				locking={session.lifting && cell.row === 0}
				crash={crashAmp(cell.row)}
				crashDelay={cell.row * RIPPLE_STEP}
				impact={cell.row === 0}
				colour={colourOf(cell.tile.group)}
				disabled={session.over}
				row={cell.row}
				col={cell.col}
				onpointerdown={(e) => start(e, cell)}
				onpointermove={move}
				onpointerup={end}
				onpointercancel={cancel}
				onpick={() => tap(cell)}
			/>
		</div>
	{/each}
</div>

<style>
	/* Rows are spaced further apart than the tiles within them, so the row reads as the
	   unit and the four words read as its contents. */
	.grid {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		column-gap: var(--gap);
		row-gap: 18px;
		align-items: stretch;
	}

	.band {
		grid-column: 1 / -1;
		display: grid;
		margin: calc(-1 * var(--row-bleed)) -6px;
	}

	/* Empty and behind everything: it never sizes its track, it just draws the row.
	   The negative margin lets it breathe around the tiles it contains. */
	.frame {
		grid-column: 1 / -1;
		margin: calc(-1 * var(--row-bleed)) -6px;
		border-radius: 17px;
		background: var(--fill);
		outline: 1px solid var(--edge);
		outline-offset: -1px;
		pointer-events: none;
	}

	.slot {
		position: relative;
		display: grid;
		/* Lets a tile size its own type against the column it actually got. */
		container-type: inline-size;
	}

	/* Marks where the held tile came from, so the board reads as having a gap rather
	   than a missing piece. */
	.slot.lifted::before {
		content: '';
		position: absolute;
		inset: 0;
		border-radius: var(--radius);
		outline: 1px dashed var(--tile-edge);
		outline-offset: -1px;
	}

	/* container-type makes each slot its own stacking context, so the z-index has to sit
	   on the slot — on the tile it could not rise above the neighbouring slots. */
	.slot.lifted {
		z-index: 5;
	}
</style>
