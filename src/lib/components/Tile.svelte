<script lang="ts">
	import type { Tile } from '$lib/game/types';

	type Props = {
		tile: Tile;
		row: number;
		col: number;
		/** Held by a tap, waiting for a second tap. */
		selected: boolean;
		/** Currently under the finger. */
		dragging: boolean;
		/** The tile a drag is hovering over, and would swap with. */
		target: boolean;
		offset: { x: number; y: number };
		/** The row the wave is on right now — the whole row lights at once. */
		locking: boolean;
		/** Strength of the wave hitting this row, 0 for none. Decays down the board. */
		crash: number;
		crashDelay: number;
		/** The row the wave actually stops on, as opposed to those it only rattles. */
		impact: boolean;
		colour: string;
		disabled: boolean;
		/** True while a check is playing out: input is refused, so say so. */
		waiting: boolean;
		/** How many rows are still in play, for "row 2 of 5". */
		rows: number;
		onpointerdown: (event: PointerEvent) => void;
		onpointermove: (event: PointerEvent) => void;
		onpointerup: (event: PointerEvent) => void;
		onpointercancel: () => void;
		onpick: () => void;
	};

	let {
		tile,
		row,
		col,
		selected,
		dragging,
		target,
		offset,
		locking,
		crash,
		crashDelay,
		impact,
		colour,
		disabled,
		waiting,
		rows,
		onpointerdown,
		onpointermove,
		onpointerup,
		onpointercancel,
		onpick
	}: Props = $props();
</script>

<button
	class="tile"
	class:selected
	class:dragging
	class:target
	class:locking
	class:crashing={crash > 0}
	class:impact={impact && crash > 0}
	data-row={row}
	data-col={col}
	style:--len={tile.word.length}
	style:--dx="{offset.x}px"
	style:--dy="{offset.y}px"
	style:--crash-delay="{crashDelay}ms"
	style:--amp={crash}
	style:--colour={colour}
	{disabled}
	aria-disabled={waiting || undefined}
	aria-pressed={selected}
	aria-label="{tile.word}, row {row + 1} of {rows}"
	{onpointerdown}
	{onpointermove}
	{onpointerup}
	{onpointercancel}
	onclick={onpick}
>
	{tile.word}
</button>

<style>
	.tile {
		position: relative;
		display: grid;
		place-items: center;
		min-height: var(--row-h);
		padding: 2px 3px;
		border-radius: var(--r-md);
		background: linear-gradient(180deg, var(--surface-hi), var(--surface));
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
		/* The board owns vertical gestures — dragging a tile must not scroll the page. */
		touch-action: none;
		transition:
			transform 160ms var(--snap),
			outline-color 160ms ease,
			box-shadow 160ms ease,
			background 160ms ease;
	}

	/* The board is reachable from a keyboard — that is the whole reason tap-to-swap exists
	   — but the ring was invisible, because every focusable control here redraws itself
	   with `outline` for decoration and a scoped component rule outranks the global
	   `:focus-visible`. A tile literally matched :focus-visible and computed the decorative
	   edge instead. Higher specificity, and offset outwards so it cannot be mistaken for
	   the 1px edge. */
	.tile:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	.tile:active:not(:disabled):not([aria-disabled='true']) {
		transform: scale(0.96);
	}

	/* Nothing can be swapped mid-check. `aria-disabled` rather than `disabled`: a real
	   disabled attribute on a focused control drops focus to <body>, and the Check button
	   is focused on exactly the press that starts a check. */
	.tile[aria-disabled='true'] {
		cursor: default;
	}

	.selected {
		background: linear-gradient(180deg, var(--surface-lift-hi), var(--surface-lift));
		outline: 2px solid var(--accent);
		outline-offset: -2px;
		box-shadow:
			0 0 0 4px color-mix(in oklab, var(--accent) 10%, transparent),
			0 6px 14px rgb(0 0 0 / 45%);
		transform: translateY(-3px) scale(1.04);
	}

	.selected:active:not(:disabled):not([aria-disabled='true']) {
		transform: translateY(-3px) scale(1);
	}

	/* Where a drop would land. The held tile is lifted clear of it, so the ring and the
	   brighter fill stay visible underneath rather than being covered exactly. */
	.target {
		background: linear-gradient(180deg, var(--surface-drop-hi), var(--surface-drop));
		outline: 2px solid color-mix(in oklab, var(--accent) 60%, transparent);
		outline-offset: -2px;
		box-shadow: 0 0 0 3px color-mix(in oklab, var(--accent) 12%, transparent);
	}

	/* Tracks the finger exactly: no transition, or it lags behind. Held above the pointer
	   so a thumb doesn't sit on top of the thing being aimed at. */
	.dragging,
	.dragging:active:not(:disabled):not([aria-disabled='true']) {
		transform: translate(var(--dx), calc(var(--dy) - 16px)) scale(1.04);
		outline: 2px solid var(--accent);
		outline-offset: -2px;
		box-shadow: 0 16px 30px rgb(0 0 0 / 60%);
		transition: none;
	}

	/* The whole row lights on one frame: the wave's only direction is down the board, and
	   a left-to-right roll inside the row is a second direction crossing it. What is left
	   over to read is vertical — the row is pressed down as the wave passes through it.
	   Each tile ends on exactly the colour the solved row uses, so the row consolidating
	   into a single bar is a swap the eye doesn't catch. */
	.locking {
		animation: settle 240ms var(--ease) both;
	}

	@keyframes settle {
		0% {
			background: linear-gradient(180deg, var(--surface-hi), var(--surface));
			outline-color: var(--tile-edge);
			box-shadow: 0 1px 2px rgb(0 0 0 / 45%);
			transform: none;
		}
		45% {
			background: color-mix(in oklab, var(--colour) 82%, var(--ink));
			outline-color: color-mix(in oklab, var(--colour) 92%, white);
			box-shadow: 0 0 0 calc(7px * var(--boost)) color-mix(in oklab, var(--colour) 26%, transparent);
			transform: translateY(calc(3px * var(--boost))) scale(calc(1 + 0.06 * var(--boost)));
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
			outline-color: color-mix(in oklab, var(--jolt) 62%, var(--tile-edge));
			box-shadow:
				inset 0 1px 0 rgb(255 255 255 / 5%),
				0 0 0 5px color-mix(in oklab, var(--jolt) 14%, transparent);
		}
	}
</style>
