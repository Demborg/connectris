<script lang="ts">
	import type { Group } from '$lib/game/types';

	let {
		group,
		colour,
		missed = false
	}: { group: Group; colour: string; missed?: boolean } = $props();
</script>

<div class="banner" class:missed style:--colour={colour}>
	<span class="label">{group.label}</span>
	<span class="words">{group.words.join(' · ')}</span>
</div>

<style>
	.banner {
		padding: 7px 11px;
		border-radius: 10px;
		background: linear-gradient(
			90deg,
			color-mix(in oklab, var(--colour) 22%, var(--well)),
			color-mix(in oklab, var(--colour) 9%, var(--well))
		);
		border-left: 3px solid var(--colour);
		animation: land 420ms var(--snap) both;
	}

	/* Revealed after a loss: same information, visibly not earned. */
	.missed {
		background: none;
		border-left: 3px dashed color-mix(in oklab, var(--colour) 55%, var(--well));
		opacity: 0.62;
	}

	.label {
		display: block;
		font-size: 0.72rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: color-mix(in oklab, var(--colour) 78%, white);
	}

	.words {
		display: block;
		margin-top: 1px;
		font-size: 0.74rem;
		letter-spacing: 0.02em;
		color: var(--muted);
	}

	@keyframes land {
		from {
			opacity: 0;
			transform: translateY(-14px) scale(0.97);
		}
		to {
			opacity: 1;
			transform: none;
		}
	}
</style>
