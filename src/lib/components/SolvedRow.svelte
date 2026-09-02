<script lang="ts">
	import type { Group } from '$lib/game/types';

	let {
		group,
		colour,
		missed = false,
		enterDelay = 0
	}: { group: Group; colour: string; missed?: boolean; enterDelay?: number } = $props();
</script>

<div class="row" class:missed style:--colour={colour} style:--enter="{enterDelay}ms">
	<span class="chip"></span>
	<div class="text">
		<span class="label">{group.label}</span>
		<span class="words">{group.words.join('  ·  ')}</span>
	</div>
</div>

<style>
	/* A solved row keeps a full row's height and spans the rail, so the board never
	   changes size mid-game. Cleared rows are always the topmost ones, so they convert
	   in place and nothing below them moves. */
	.row {
		grid-column: 1 / -1;
		display: grid;
		grid-template-columns: 26px 1fr;
		align-items: center;
		gap: var(--gap);
		/* Matches the height an active row's frame reaches with its bleed, so solved and
		   unsolved rows sit on exactly the same rhythm. */
		min-height: calc(var(--row-h) + 2 * var(--row-bleed));
		padding-right: 12px;
		border-radius: 17px;
		background: linear-gradient(
			180deg,
			color-mix(in oklab, var(--colour) 56%, var(--ink)),
			color-mix(in oklab, var(--colour) 44%, var(--ink))
		);
		outline: 1px solid color-mix(in oklab, var(--colour) 62%, var(--ink));
		outline-offset: -1px;
		/* Delayed per row within a batch, so a multi-row clear settles top to bottom
		   instead of every bar landing on the same frame. */
		animation: consolidate 320ms var(--ease) var(--enter) both;
	}

	.chip {
		justify-self: center;
		width: 11px;
		height: 11px;
		border-radius: 3px;
		background: var(--colour);
		box-shadow: 0 0 12px color-mix(in oklab, var(--colour) 60%, transparent);
	}

	.text {
		display: grid;
		gap: 3px;
		min-width: 0;
		animation: surface 260ms var(--ease) calc(var(--enter) + 90ms) both;
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

	@keyframes consolidate {
		0% {
			filter: brightness(1.5);
		}
		100% {
			filter: none;
		}
	}

	@keyframes surface {
		from {
			opacity: 0;
			transform: translateY(3px);
		}
	}
</style>
