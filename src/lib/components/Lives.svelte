<script lang="ts">
	import { LIVES } from '$lib/game/engine';

	let { lives }: { lives: number } = $props();
</script>

<div class="lives" aria-label="{lives} of {LIVES} lives left">
	{#each { length: LIVES }, i}
		<span class="pip" class:spent={i >= lives}></span>
	{/each}
</div>

<style>
	.lives {
		display: flex;
		gap: 5px;
	}

	.pip {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--accent);
		transition:
			background 260ms ease,
			transform 320ms var(--snap),
			opacity 260ms ease;
	}

	.spent {
		background: var(--danger);
		opacity: 0.28;
		transform: scale(0.62);
	}
</style>
