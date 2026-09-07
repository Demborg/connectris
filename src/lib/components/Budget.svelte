<script lang="ts">
	import { CHECKS } from '$lib/game/engine';

	let { left }: { left: number } = $props();
</script>

<!-- role="status" rather than a bare aria-label: a label on a generic element with no role
     is not reliably exposed, and this div is not in the tab order, so nothing would ever
     have read it. As a status it is also announced when the count changes, which is the
     moment a player would want to hear it. -->
<div class="budget" role="status" aria-label="{left} of {CHECKS} checks left">
	{#each { length: CHECKS }, i}
		<span class="pip" class:spent={i >= left} class:spending={i === left && left < CHECKS}></span>
	{/each}
</div>

<style>
	.budget {
		display: flex;
		justify-content: center;
		gap: 7px;
	}

	.pip {
		width: 10px;
		height: 10px;
		border-radius: 2px;
		background: var(--text);
		transition:
			background 260ms ease,
			box-shadow 260ms ease,
			transform 320ms var(--snap);
	}

	.spent {
		background: none;
		box-shadow: inset 0 0 0 1.5px var(--dim);
		transform: scale(0.7);
	}

	/* The one just spent. Neutral, not red: spending a check is the cost of playing, not
	   a punishment. Getting nothing back for it is what the red crash on the board says. */
	.spending {
		animation: spend 560ms var(--ease);
	}

	@keyframes spend {
		0% {
			background: var(--accent);
			box-shadow: 0 0 0 5px color-mix(in oklab, var(--accent) 22%, transparent);
			transform: scale(1.2);
		}
		45% {
			background: var(--accent);
			box-shadow: 0 0 0 0 transparent;
			transform: scale(1);
		}
	}
</style>
