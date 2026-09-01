<script lang="ts">
	let { rows }: { rows: number } = $props();

	// Four is unreachable — with five rows, four correct forces the fifth — but name it
	// anyway rather than fall through to something that reads like a bug.
	const NAMES: Record<number, string> = { 2: 'DOUBLE', 3: 'TRIPLE', 4: 'QUAD', 5: 'CONNECTRIS' };
	let label = $derived(NAMES[rows] ?? `${rows} ROWS`);
</script>

<div class="flash" class:huge={rows >= 5} aria-hidden="true">{label}</div>

<style>
	.flash {
		position: absolute;
		inset: 0;
		display: grid;
		place-items: center;
		pointer-events: none;
		font-size: clamp(1.5rem, 9vw, 2.2rem);
		font-weight: 800;
		color: var(--text);
		text-shadow:
			0 0 28px rgb(238 243 250 / 30%),
			0 2px 10px rgb(0 0 0 / 60%);
		animation: pop 1200ms var(--ease) both;
	}

	.huge {
		font-size: clamp(1.9rem, 12vw, 2.9rem);
	}

	@keyframes pop {
		0% {
			opacity: 0;
			letter-spacing: 0.02em;
			transform: scale(0.72);
		}
		16% {
			opacity: 1;
			transform: scale(1.07);
		}
		28% {
			transform: scale(1);
		}
		70% {
			opacity: 1;
			letter-spacing: 0.16em;
			transform: scale(1);
		}
		100% {
			opacity: 0;
			letter-spacing: 0.24em;
			transform: scale(1.05);
		}
	}
</style>
