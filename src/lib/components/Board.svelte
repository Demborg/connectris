<script lang="ts">
	import { flip } from 'svelte/animate';
	import SolvedRow from './SolvedRow.svelte';
	import Tile from './Tile.svelte';
	import { RIPPLE_STEP, ROW_STAGGER, TILE_STAGGER } from '$lib/game/session.svelte';
	import type { Session } from '$lib/game/session.svelte';
	import type { Group, Tile as TileData } from '$lib/game/types';

	let { session }: { session: Session } = $props();

	const COLOURS = ['var(--g1)', 'var(--g2)', 'var(--g3)', 'var(--g4)', 'var(--g5)'];
	const colourOf = (group: string) =>
		COLOURS[session.puzzle.groups.findIndex((g) => g.id === group)] ?? 'var(--accent)';

	type Cell =
		| { key: string; kind: 'solved'; group: Group; missed: boolean; order: number }
		| { key: string; kind: 'rail'; row: number }
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
		...session.rows.flatMap((row, r): Cell[] => [
			{ key: `rail-${r}`, kind: 'rail', row: r },
			...row.map((tile, c): Cell => ({
				key: `tile-${tile.id}`,
				kind: 'tile',
				row: r,
				col: c,
				tile
			}))
		])
	]);

	// The impact lands on the top remaining row and loses strength each row further down,
	// so the shock visibly travels rather than shaking the whole board. A clear is absorbed
	// quickly by the rows that took it; a miss was absorbed by nothing, so it rings all the
	// way down the stack.
	let decay = $derived(session.crashMiss ? 0.22 : 0.45);
	const crashAmp = (row: number) => Math.max(0, session.crash * (1 - row * decay));

	// A bigger clear hits harder and glows brighter.
	let boost = $derived(session.locking > 1 ? Math.min(1.6, 1 + (session.locking - 1) * 0.2) : 1);
</script>

<div
	class="grid"
	style:--boost={boost}
	style:--jolt={session.crashMiss ? 'var(--danger)' : 'var(--accent)'}
>
	{#each cells as cell (cell.key)}
		<!-- Only tiles ever need to travel. The rank rail stays put on a row swap and simply
		     re-labels once rows clear, so animating it would just drag numbers across the board. -->
		<div
			class="slot"
			class:full={cell.kind === 'solved'}
			animate:flip={{ duration: cell.kind === 'tile' ? 300 : 0 }}
		>
			{#if cell.kind === 'solved'}
				<SolvedRow
					group={cell.group}
					colour={colourOf(cell.group.id)}
					missed={cell.missed}
					enterDelay={cell.order * 90}
				/>
			{:else if cell.kind === 'rail'}
				<button
					class="rail"
					class:held={session.row === cell.row}
					class:locking={cell.row < session.locking}
					disabled={session.over}
					aria-label="Row {cell.row + 1}. Select to reorder."
					onclick={() => session.pickRow(cell.row)}
				>
					{cell.row + 1}
				</button>
			{:else}
				<Tile
					tile={cell.tile}
					selected={session.tile?.row === cell.row && session.tile?.col === cell.col}
					locking={cell.row < session.locking}
					delay={cell.row * ROW_STAGGER + cell.col * TILE_STAGGER}
					crash={crashAmp(cell.row)}
					crashDelay={cell.row * RIPPLE_STEP}
					impact={cell.row === 0}
					colour={colourOf(cell.tile.group)}
					disabled={session.over}
					onpick={() => session.pickTile({ row: cell.row, col: cell.col })}
				/>
			{/if}
		</div>
	{/each}
</div>

<style>
	.grid {
		display: grid;
		grid-template-columns: var(--rail) repeat(4, minmax(0, 1fr));
		gap: var(--gap);
		align-items: stretch;
	}

	.slot {
		display: grid;
		/* Lets a tile size its own type against the column it actually got. */
		container-type: inline-size;
	}

	.slot.full {
		grid-column: 1 / -1;
		container-type: normal;
	}

	/* The rank rail doubles as the row handle. Showing the ranking is the point: the
	   player is ordering rows by confidence, so the order has to be legible. */
	.rail {
		display: grid;
		place-items: center;
		border-radius: 9px;
		font-size: var(--fs-xs);
		font-weight: 700;
		font-variant-numeric: tabular-nums;
		color: var(--dim);
		background: rgb(255 255 255 / 2%);
		transition:
			color 160ms ease,
			background 160ms ease,
			box-shadow 160ms ease;
	}

	.rail.held {
		color: #0d131c;
		background: var(--accent);
		box-shadow: 0 0 0 4px rgb(238 243 250 / 12%);
	}

	.rail.locking {
		color: var(--text);
		background: rgb(255 255 255 / 8%);
	}
</style>
