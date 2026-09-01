<script lang="ts">
	import { flip } from 'svelte/animate';
	import Tile from './Tile.svelte';
	import type { Session } from '$lib/game/session.svelte';
	import type { Tile as TileData } from '$lib/game/types';

	let { session }: { session: Session } = $props();

	const COLOURS = ['var(--g1)', 'var(--g2)', 'var(--g3)', 'var(--g4)', 'var(--g5)'];
	const colourOf = (group: string) =>
		COLOURS[session.puzzle.groups.findIndex((g) => g.id === group)] ?? 'var(--accent)';

	type Cell =
		| { key: string; kind: 'rail'; row: number }
		| { key: string; kind: 'tile'; row: number; col: number; tile: TileData };

	// One flat grid rather than a container per row: tiles move *between* rows, and
	// `animate:flip` only animates within a single keyed block.
	let cells = $derived(
		session.rows.flatMap((row, r): Cell[] => [
			{ key: `rail-${r}`, kind: 'rail', row: r },
			...row.map((tile, c): Cell => ({
				key: `tile-${tile.id}`,
				kind: 'tile',
				row: r,
				col: c,
				tile
			}))
		])
	);

	let shaking = $state(false);
	$effect(() => {
		if (session.shake === 0) return;
		shaking = true;
		const id = setTimeout(() => (shaking = false), 420);
		return () => clearTimeout(id);
	});
</script>

<div class="grid" class:shaking>
	{#each cells as cell (cell.key)}
		<div class="slot" animate:flip={{ duration: 320 }}>
			{#if cell.kind === 'rail'}
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

	.shaking {
		animation: shake 400ms ease;
	}

	.slot {
		display: grid;
		/* Lets a tile size its own type against the column it actually got. */
		container-type: inline-size;
	}

	/* The rank rail doubles as the row handle. Showing the ranking is the point: the
	   player is ordering rows by confidence, so the order has to be legible. */
	.rail {
		display: grid;
		place-items: center;
		border-radius: 9px;
		font-size: 0.72rem;
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
		color: var(--bg);
		background: var(--accent);
		box-shadow: 0 0 0 4px rgb(125 211 252 / 14%);
	}

	.rail.locking {
		color: var(--tile-text);
		background: rgb(255 255 255 / 8%);
	}

	@keyframes shake {
		0%,
		100% {
			transform: translateX(0);
		}
		15% {
			transform: translateX(-7px);
		}
		35% {
			transform: translateX(6px);
		}
		55% {
			transform: translateX(-4px);
		}
		78% {
			transform: translateX(2px);
		}
	}
</style>
