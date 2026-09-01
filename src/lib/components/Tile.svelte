<script lang="ts">
	import type { Tile } from '$lib/game/types';

	type Props = {
		tile: Tile;
		selected: boolean;
		locking: boolean;
		/** Position in the clearing wave, in ms. */
		delay: number;
		colour: string;
		disabled: boolean;
		onpick: () => void;
	};

	let { tile, selected, locking, delay, colour, disabled, onpick }: Props = $props();
</script>

<button
	class="tile"
	class:selected
	class:locking
	style:--len={tile.word.length}
	style:--delay="{delay}ms"
	style:--colour={colour}
	{disabled}
	aria-pressed={selected}
	onclick={onpick}
>
	{tile.word}
</button>

<style>
	.tile {
		display: grid;
		place-items: center;
		min-height: var(--row-h);
		padding: 2px 3px;
		border-radius: var(--radius);
		background: linear-gradient(180deg, var(--tile-hi), var(--tile));
		box-shadow:
			inset 0 1px 0 rgb(255 255 255 / 5%),
			0 1px 2px rgb(0 0 0 / 45%);
		outline: 1px solid var(--tile-edge);
		outline-offset: -1px;
		/* One size for every word that fits, shrinking only when the column demands it.
		   0.62em is about the advance of a bold uppercase glyph plus its letter-spacing. */
		font-size: min(var(--fs-md), calc((100cqw - 12px) / (var(--len) * 0.62)));
		font-weight: 600;
		letter-spacing: 0.02em;
		line-height: 1.05;
		text-align: center;
		white-space: nowrap;
		transition:
			transform 160ms var(--snap),
			outline-color 160ms ease,
			box-shadow 160ms ease,
			background 160ms ease;
	}

	.tile:active:not(:disabled) {
		transform: scale(0.96);
	}

	.selected {
		background: linear-gradient(180deg, #2a3442, #202836);
		outline: 2px solid var(--accent);
		outline-offset: -2px;
		box-shadow:
			0 0 0 4px rgb(238 243 250 / 10%),
			0 6px 14px rgb(0 0 0 / 45%);
		transform: translateY(-3px) scale(1.04);
	}

	.selected:active:not(:disabled) {
		transform: translateY(-3px) scale(1);
	}

	/* Each tile fires on its own delay, so a clear rolls left-to-right, top-to-bottom.
	   It ends on exactly the colour the solved row uses, so the row consolidating into
	   a single bar is a swap the eye doesn't catch. */
	.locking {
		animation: settle 260ms var(--ease) var(--delay) both;
	}

	@keyframes settle {
		0% {
			background: linear-gradient(180deg, var(--tile-hi), var(--tile));
			outline-color: var(--tile-edge);
			box-shadow: 0 1px 2px rgb(0 0 0 / 45%);
			transform: none;
		}
		45% {
			background: color-mix(in oklab, var(--colour) 82%, var(--ink));
			outline-color: color-mix(in oklab, var(--colour) 92%, white);
			box-shadow: 0 0 0 7px color-mix(in oklab, var(--colour) 26%, transparent);
			transform: scale(1.06);
		}
		100% {
			background: color-mix(in oklab, var(--colour) 50%, var(--ink));
			outline-color: color-mix(in oklab, var(--colour) 62%, var(--ink));
			box-shadow: 0 0 0 0 transparent;
			transform: none;
		}
	}
</style>
