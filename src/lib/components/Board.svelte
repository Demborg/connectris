<script lang="ts">
	import { flip } from 'svelte/animate';
	import SolvedRow from './SolvedRow.svelte';
	import Tile from './Tile.svelte';
	import { RIPPLE_STEP, ROW_STAGGER, TILE_STAGGER } from '$lib/game/session.svelte';
	import type { Session } from '$lib/game/session.svelte';
	import type { Group, Position, Tile as TileData } from '$lib/game/types';

	let { session }: { session: Session } = $props();

	const COLOURS = ['var(--g1)', 'var(--g2)', 'var(--g3)', 'var(--g4)', 'var(--g5)'];
	const colourOf = (group: string) =>
		COLOURS[session.puzzle.groups.findIndex((g) => g.id === group)] ?? 'var(--accent)';

	type Cell =
		| { key: string; kind: 'solved'; group: Group; missed: boolean; order: number }
		| { key: string; kind: 'tile'; row: number; col: number; tile: TileData };

	// One flat grid for the whole board: solved rows, then revealed misses, then the rows
	// still in play. Cleared rows are always the topmost ones, so they turn into solved
	// rows exactly where they already sit — nothing below them has to move.
	let cells = $derived([
		...session.solved.map((s): Cell => ({
			key: `done-${s.group.id}`,
			kind: 'solved',
			group: s.group,
			missed: false,
			order: s.order
		})),
		...session.missed.map((g, i): Cell => ({
			key: `done-${g.id}`,
			kind: 'solved',
			group: g,
			missed: true,
			order: i
		})),
		...session.rows.flatMap((row, r): Cell[] =>
			row.map((tile, c): Cell => ({ key: `tile-${tile.id}`, kind: 'tile', row: r, col: c, tile }))
		)
	]);

	// The impact lands on the top remaining row and loses strength each row further down,
	// so the shock visibly travels rather than shaking the whole board. A clear is absorbed
	// quickly by the rows that took it; a miss was absorbed by nothing, so it rings all the
	// way down the stack.
	let decay = $derived(session.crashMiss ? 0.22 : 0.45);
	const crashAmp = (row: number) => Math.max(0, session.crash * (1 - row * decay));

	// A bigger clear hits harder and glows brighter.
	let boost = $derived(session.locking > 1 ? Math.min(1.6, 1 + (session.locking - 1) * 0.2) : 1);

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
	{#each cells as cell (cell.key)}
		<div
			class="slot"
			class:full={cell.kind === 'solved'}
			class:lifted={cell.kind === 'tile' && !!drag?.moved && samePos(drag.from, cell)}
			animate:flip={{ duration: cell.kind === 'tile' ? 300 : 0 }}
		>
			{#if cell.kind === 'solved'}
				<SolvedRow
					group={cell.group}
					colour={colourOf(cell.group.id)}
					missed={cell.missed}
					enterDelay={cell.order * 90}
				/>
			{:else}
				<Tile
					tile={cell.tile}
					selected={samePos(session.tile, cell)}
					dragging={!!drag?.moved && samePos(drag.from, cell)}
					target={samePos(over, cell)}
					offset={drag?.moved && samePos(drag.from, cell)
						? { x: drag.dx, y: drag.dy }
						: { x: 0, y: 0 }}
					locking={cell.row < session.locking}
					delay={cell.row * ROW_STAGGER + cell.col * TILE_STAGGER}
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
			{/if}
		</div>
	{/each}
</div>

<style>
	.grid {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: var(--gap);
		align-items: stretch;
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

	.slot.full {
		grid-column: 1 / -1;
		container-type: normal;
	}

	/* container-type makes each slot its own stacking context, so the z-index has to sit
	   on the slot — on the tile it could not rise above the neighbouring slots. */
	.slot.lifted {
		z-index: 5;
	}
</style>
