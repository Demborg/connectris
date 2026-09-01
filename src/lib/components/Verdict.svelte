<script lang="ts">
	import type { Verdict } from '$lib/game/session.svelte';

	let { verdict }: { verdict: Verdict } = $props();
</script>

<p class="verdict">
	<span class="count">{verdict.count}</span>
	<span class="note">{verdict.note}</span>
</p>

<style>
	/* The count is the only thing a check says in words, so it is set like a number that
	   matters rather than a status line. Same tracked caps as the combo callout above it,
	   deliberately quieter — that one shouts, this one informs. */
	.verdict {
		display: flex;
		align-items: baseline;
		justify-content: center;
		gap: 9px;
		margin: 0;
		animation: surface 300ms var(--ease) both;
	}

	.count {
		font-size: var(--fs-lg);
		font-weight: 800;
		font-variant-numeric: tabular-nums;
		line-height: 1;
	}

	.note {
		font-size: var(--fs-xs);
		font-weight: 600;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: var(--muted);
	}

	@keyframes surface {
		from {
			opacity: 0;
			transform: translateY(5px);
		}
	}
</style>
