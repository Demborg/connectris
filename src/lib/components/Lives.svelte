<script lang="ts">
	import { LIVES } from '$lib/game/engine';

	let { lives }: { lives: number } = $props();
</script>

<div class="lives" aria-label="{lives} of {LIVES} lives left">
	{#each { length: LIVES }, i}
		<span class="pip" class:spent={i >= lives} class:draining={i === lives && lives < LIVES}></span>
	{/each}
</div>

<style>
	.lives {
		display: flex;
		gap: 6px;
	}

	.pip {
		width: 9px;
		height: 9px;
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

	/* The one that just went. Losing a life should register. */
	.draining {
		animation: drain 620ms var(--ease);
	}

	@keyframes drain {
		0% {
			background: var(--danger);
			box-shadow: 0 0 0 5px color-mix(in oklab, var(--danger) 30%, transparent);
			transform: scale(1.25);
		}
		45% {
			background: var(--danger);
			box-shadow: 0 0 0 0 transparent;
			transform: scale(1);
		}
	}
</style>
