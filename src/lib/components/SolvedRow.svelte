<script lang="ts">
	import type { Group } from '$lib/game/types';

	let {
		group,
		colour,
		missed = false,
		enterDelay = 0,
		/** Whether this row's notes are the ones currently on screen. */
		open = false,
		onopen
	}: {
		group: Group;
		colour: string;
		missed?: boolean;
		enterDelay?: number;
		open?: boolean;
		onopen: () => void;
	} = $props();

	/**
	 * A row with notes is a control; a row without them is a label.
	 *
	 * Boards written before the notes stage existed carry none, and a button that opens
	 * an empty panel is worse than no button — so the element itself changes rather than
	 * the row staying a button that sometimes does nothing.
	 */
	let openable = $derived(!!group.notes);
</script>

<svelte:element
	this={openable ? 'button' : 'div'}
	class="row"
	class:missed
	class:openable
	style:--colour={colour}
	style:--enter="{enterDelay}ms"
	role={openable ? 'button' : undefined}
	aria-haspopup={openable ? 'dialog' : undefined}
	aria-expanded={openable ? open : undefined}
	onclick={openable ? onopen : undefined}
>
	<span class="chip"></span>
	<div class="text">
		<span class="label">{group.label}</span>
		<span class="words">{group.words.join('  ·  ')}</span>
	</div>
	{#if openable}
		<!-- The one hint that there is more here. Quiet on purpose: the row landing is the
		     moment, and an inviting button on top of it competes with the clear. -->
		<span class="more" aria-hidden="true">&#9656;</span>
	{/if}
</svelte:element>

<style>
	/* A solved row keeps a full row's height and spans the rail, so the board never
	   changes size mid-game. Cleared rows are always the topmost ones, so they convert
	   in place and nothing below them moves. */
	.row {
		grid-column: 1 / -1;
		display: grid;
		grid-template-columns: 26px 1fr auto;
		align-items: center;
		gap: var(--gap);
		text-align: left;
		/* Matches the height an active row's frame reaches with its bleed, so solved and
		   unsolved rows sit on exactly the same rhythm. */
		min-height: calc(var(--row-h) + 2 * var(--row-bleed));
		padding-right: 12px;
		border-radius: var(--r-row);
		background: linear-gradient(
			180deg,
			color-mix(in oklab, var(--colour) 56%, var(--ink)),
			color-mix(in oklab, var(--colour) 44%, var(--ink))
		);
		outline: 1px solid color-mix(in oklab, var(--colour) 62%, var(--ink));
		outline-offset: -1px;
		/* A cleared row converts the instant the wave leaves it, so this needs no delay of
		   its own — the sequencing is the wave's. The delay is only for the rows a loss
		   reveals, which have no wave to inherit their order from. */
		animation: consolidate 300ms var(--ease) var(--enter) both;
	}

	/* Reads as "there is more of this", not as a second action: the whole row is the
	   target, so nothing here should look like a button of its own. */
	.more {
		font-size: var(--fs-xs);
		color: color-mix(in oklab, var(--colour) 30%, var(--text));
		opacity: 0.5;
		transition: opacity 160ms ease;
	}

	.openable:hover .more,
	.openable:focus-visible .more {
		opacity: 1;
	}

	/* The row draws its own outline for decoration, which outranks the global ring — so
	   it has to redraw the ring itself or a keyboard player never sees where they are.
	   See focus.spec.ts. */
	.row:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	.chip {
		justify-self: center;
		width: 11px;
		height: 11px;
		border-radius: 3px;
		background: var(--colour);
		box-shadow: 0 0 12px color-mix(in oklab, var(--colour) 60%, transparent);
	}

	/* Close on the bar's heels rather than a beat behind it: naming the category is part
	   of the row landing, not a second pass over rows that already landed. */
	.text {
		display: grid;
		gap: 3px;
		min-width: 0;
		animation: surface 240ms var(--ease) calc(var(--enter) + 50ms) both;
	}

	.label {
		font-size: var(--fs-xs);
		font-weight: 700;
		letter-spacing: 0.09em;
		text-transform: uppercase;
		color: color-mix(in oklab, var(--colour) 45%, white);
	}

	.words {
		font-size: var(--fs-sm);
		font-weight: 500;
		letter-spacing: 0.02em;
		color: var(--text);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	/* Revealed after a loss: same information, visibly not earned. */
	.missed {
		background: none;
		outline: 1px dashed color-mix(in oklab, var(--colour) 40%, var(--well-edge));
		opacity: 0.65;
	}

	.missed .chip {
		box-shadow: none;
		opacity: 0.7;
	}

	/* Squashed under the wave that just passed through it, then settling — the same
	   vertical vocabulary the tiles lock with and the impact lands with. */
	@keyframes consolidate {
		0% {
			filter: brightness(1.5);
			transform: scaleY(1.07);
		}
		100% {
			filter: none;
			transform: scaleY(1);
		}
	}

	/* Dropping in from above, with the wave, rather than rising against it. */
	@keyframes surface {
		from {
			opacity: 0;
			transform: translateY(-4px);
		}
	}
</style>
