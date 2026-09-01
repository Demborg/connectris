<script lang="ts">
	import type { Tile } from '$lib/game/types';

	type Props = {
		tile: Tile;
		selected: boolean;
		locking: boolean;
		/** Position in the clearing wave, in ms. */
		delay: number;
		/** Strength of the wave hitting this row, 0 for none. Decays down the board. */
		crash: number;
		crashDelay: number;
		/** The row the wave actually stops on, as opposed to those it only rattles. */
		impact: boolean;
		colour: string;
		disabled: boolean;
		onpick: () => void;
	};

	let {
		tile,
		selected,
		locking,
		delay,
		crash,
		crashDelay,
		impact,
		colour,
		disabled,
		onpick
	}: Props = $props();
</script>

<button
	class="tile"
	class:selected
	class:locking
	class:crashing={crash > 0}
	class:impact={impact && crash > 0}
	style:--len={tile.word.length}
	style:--delay="{delay}ms"
	style:--crash-delay="{crashDelay}ms"
	style:--amp={crash}
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
			box-shadow: 0 0 0 calc(7px * var(--boost)) color-mix(in oklab, var(--colour) 26%, transparent);
			transform: scale(calc(1 + 0.06 * var(--boost)));
		}
		100% {
			background: color-mix(in oklab, var(--colour) 50%, var(--ink));
			outline-color: color-mix(in oklab, var(--colour) 62%, var(--ink));
			box-shadow: 0 0 0 0 transparent;
			transform: none;
		}
	}

	/* The wave has to land somewhere. When it runs out of correct rows it slams into the
	   first row that isn't one — which is exactly the row the player got wrong, so the
	   impact doubles as the answer to "where did I break the run". Rows below only feel
	   the shock travelling on, at a fraction of the amplitude. */
	.crashing {
		animation: crash 460ms var(--ease) var(--crash-delay) both;
	}

	@keyframes crash {
		0%,
		100% {
			transform: none;
		}
		18% {
			transform: translateY(calc(7px * var(--amp))) scaleY(calc(1 - 0.11 * var(--amp)))
				scaleX(calc(1 + 0.04 * var(--amp)));
		}
		46% {
			transform: translateY(calc(-3px * var(--amp))) scaleY(calc(1 + 0.045 * var(--amp)));
		}
		74% {
			transform: translateY(calc(1.5px * var(--amp))) scaleY(calc(1 - 0.015 * var(--amp)));
		}
	}

	.impact {
		animation:
			crash 460ms var(--ease) var(--crash-delay) both,
			jolt 460ms var(--ease) var(--crash-delay) both;
	}

	@keyframes jolt {
		0%,
		100% {
			outline-color: var(--tile-edge);
			box-shadow:
				inset 0 1px 0 rgb(255 255 255 / 5%),
				0 1px 2px rgb(0 0 0 / 45%);
		}
		18% {
			outline-color: color-mix(in oklab, var(--accent) 55%, var(--tile-edge));
			box-shadow:
				inset 0 1px 0 rgb(255 255 255 / 5%),
				0 0 0 5px rgb(238 243 250 / 9%);
		}
	}
</style>
