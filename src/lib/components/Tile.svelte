<script lang="ts">
	import type { Tile } from '$lib/game/types';

	type Props = {
		tile: Tile;
		selected: boolean;
		locking: boolean;
		colour: string;
		disabled: boolean;
		onpick: () => void;
	};

	let { tile, selected, locking, colour, disabled, onpick }: Props = $props();

	// Four columns on a phone leaves roughly 70px a tile, so long words have to shrink.
	// The rem value is an upper bound for short words; the real fit is done in CSS off
	// the container width, which is the only thing that actually knows how wide a tile is.
	const cap = [1.05, 1.05, 1.05, 1.05, 1.05, 1.05, 1, 0.94, 0.86, 0.8, 0.74, 0.68, 0.64];
	let size = $derived(cap[Math.min(tile.word.length, cap.length - 1)]);
</script>

<button
	class="tile"
	class:selected
	class:locking
	style:--fs="{size}rem"
	style:--len={tile.word.length}
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
		min-height: clamp(58px, 12vh, 84px);
		padding: 2px 3px;
		border-radius: var(--radius);
		background: linear-gradient(180deg, var(--tile-hi), var(--tile));
		box-shadow:
			inset 0 1px 0 rgb(255 255 255 / 5%),
			0 1px 2px rgb(0 0 0 / 45%);
		outline: 1px solid var(--tile-edge);
		outline-offset: -1px;
		/* Whichever is smaller: the per-length cap, or what actually fits the column.
		   0.64em is about the advance of a bold uppercase glyph plus its letter-spacing. */
		font-size: min(var(--fs), calc((100cqw - 12px) / (var(--len) * 0.64)));
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
		background: linear-gradient(180deg, #24303e, #1b2431);
		outline: 2px solid var(--accent);
		outline-offset: -2px;
		box-shadow:
			0 0 0 4px rgb(125 211 252 / 12%),
			0 6px 14px rgb(0 0 0 / 45%);
		transform: translateY(-3px) scale(1.04);
	}

	.selected:active:not(:disabled) {
		transform: translateY(-3px) scale(1);
	}

	.locking {
		animation: lift 620ms linear forwards;
	}

	/* Every stop sets every animated property: with implicit keyframes the browser
	   interpolates the missing ones across the *whole* animation, which made the fade
	   start immediately instead of at the end. */
	@keyframes lift {
		0% {
			background: linear-gradient(180deg, var(--tile-hi), var(--tile));
			outline-color: var(--tile-edge);
			transform: none;
			opacity: 1;
			animation-timing-function: var(--snap);
		}
		18% {
			background: color-mix(in oklab, var(--colour) 36%, var(--tile));
			outline-color: var(--colour);
			box-shadow: 0 0 0 5px color-mix(in oklab, var(--colour) 20%, transparent);
			transform: scale(1.035);
			opacity: 1;
			animation-timing-function: ease-out;
		}
		58% {
			background: color-mix(in oklab, var(--colour) 36%, var(--tile));
			outline-color: var(--colour);
			box-shadow: 0 0 0 5px color-mix(in oklab, var(--colour) 20%, transparent);
			transform: translateY(-3px) scale(1.035);
			opacity: 1;
			animation-timing-function: cubic-bezier(0.55, 0, 0.9, 0.35);
		}
		100% {
			background: color-mix(in oklab, var(--colour) 36%, var(--tile));
			outline-color: transparent;
			box-shadow: none;
			transform: translateY(-34px) scale(0.9);
			opacity: 0;
		}
	}
</style>
