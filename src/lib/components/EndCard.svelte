<script lang="ts">
	import type { Session } from '$lib/game/session.svelte';
	import { formatTime } from '$lib/format';

	let { session, onnext }: { session: Session; onnext: () => void } = $props();

	let won = $derived(session.status === 'won');
	let best = $derived(session.best);
	// The three axes stay separate on purpose — there is no combined score.
	let stats = $derived([
		{ label: 'Time', value: formatTime(session.elapsedMs), best: best && formatTime(best.timeMs) },
		{ label: 'Lives left', value: `${session.lives}`, best: best && `${best.livesLeft}` },
		{ label: 'Moves', value: `${session.moves}`, best: best && `${best.moves}` },
		{ label: 'Checks', value: `${session.checks}`, best: best && `${best.checks}` }
	]);
</script>

<div class="scrim">
	<div class="card" class:lost={!won}>
		<p class="verdict">{won ? 'Solved' : 'Out of lives'}</p>
		<p class="sub">
			{won
				? 'Every row cleared from the top.'
				: 'The remaining categories are shown above — take a look at what you missed.'}
		</p>

		<dl class="stats">
			{#each stats as s (s.label)}
				<div>
					<dt>{s.label}</dt>
					<dd>{s.value}</dd>
					{#if won && s.best}<dd class="best">best {s.best}</dd>{/if}
				</div>
			{/each}
		</dl>

		<button class="next" onclick={onnext}>Next puzzle</button>
	</div>
</div>

<style>
	.scrim {
		position: fixed;
		inset: 0;
		display: grid;
		place-items: end center;
		padding: 16px;
		padding-bottom: max(16px, env(safe-area-inset-bottom));
		background: rgb(6 8 12 / 45%);
		backdrop-filter: blur(2px);
		animation: fade 260ms ease both;
		z-index: 10;
	}

	.card {
		width: 100%;
		max-width: 440px;
		padding: 20px;
		border-radius: 20px;
		background: linear-gradient(180deg, #161d27, #10151d);
		outline: 1px solid var(--tile-edge);
		outline-offset: -1px;
		box-shadow: 0 18px 48px rgb(0 0 0 / 55%);
		animation: rise 420ms var(--snap) both;
	}

	.verdict {
		margin: 0;
		font-size: 1.4rem;
		font-weight: 700;
		letter-spacing: -0.01em;
		color: var(--g2);
	}

	.lost .verdict {
		color: var(--danger);
	}

	.sub {
		margin: 4px 0 16px;
		font-size: 0.84rem;
		color: var(--muted);
	}

	.stats {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 8px;
		margin: 0 0 18px;
	}

	dt {
		font-size: 0.62rem;
		font-weight: 600;
		letter-spacing: 0.07em;
		text-transform: uppercase;
		color: var(--dim);
	}

	dd {
		margin: 2px 0 0;
		font-size: 1.15rem;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}

	dd.best {
		font-size: 0.66rem;
		font-weight: 500;
		color: var(--muted);
	}

	.next {
		width: 100%;
		padding: 13px;
		border-radius: 12px;
		background: var(--accent);
		color: #08111a;
		font-weight: 700;
		letter-spacing: 0.01em;
		transition: transform 140ms var(--snap);
	}

	.next:active {
		transform: scale(0.98);
	}

	@keyframes fade {
		from {
			opacity: 0;
		}
	}

	@keyframes rise {
		from {
			opacity: 0;
			transform: translateY(22px);
		}
	}
</style>
