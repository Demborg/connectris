<script lang="ts">
	import { cubicOut } from 'svelte/easing';
	import type { TransitionConfig } from 'svelte/transition';

	let { rows }: { rows: number } = $props();

	// Four is unreachable — with five rows, four correct forces the fifth — but name it
	// anyway rather than fall through to something that reads like a bug.
	const NAMES: Record<number, string> = { 2: 'DOUBLE', 3: 'TRIPLE', 4: 'QUAD', 5: 'CONNECTRIS' };
	let label = $derived(NAMES[rows] ?? `${rows} ROWS`);

	/**
	 * The tally climbs, so the word climbs with it: each new one arrives from below and
	 * shoves the last one out of the top. A crossfade in place would read as a correction
	 * — DOUBLE was wrong, here is TRIPLE — rather than as a count still going up.
	 */
	const roll = (_node: Element, { out = false }: { out?: boolean } = {}): TransitionConfig => ({
		duration: out ? 200 : 240,
		easing: cubicOut,
		css: (t, u) =>
			`opacity: ${t}; transform: translateY(${out ? -u * 30 : u * 30}px) scale(${0.82 + 0.18 * t});`
	});
</script>

<!-- Keyed on the count: each tick is a new word rolling through, not the same one
     re-rendered. Both sit in the same grid cell so they cross over each other. -->
<div class="flash" aria-hidden="true">
	{#key rows}
		<span
			class="word"
			class:t3={rows === 3}
			class:t4={rows === 4}
			class:t5={rows >= 5}
			in:roll
			out:roll={{ out: true }}
		>
			<!-- The escalation lives on this inner span, so its own animation never fights
			     the roll transition for the transform on the outer one. -->
			<span class="ink">{label}</span>
		</span>
	{/key}
</div>

<style>
	.flash {
		position: absolute;
		inset: 0;
		display: grid;
		place-items: center;
		pointer-events: none;
	}

	/* Every tick shares this cell, so an outgoing word and its replacement pass through
	   each other rather than shunting the layout. */
	.word {
		grid-area: 1 / 1;
		white-space: nowrap;
		font-size: clamp(1.5rem, 9vw, 2.2rem);
		font-weight: 800;
		letter-spacing: 0.05em;
		color: var(--text);
		text-shadow:
			0 0 28px rgb(238 243 250 / 30%),
			0 2px 10px rgb(0 0 0 / 60%);
	}

	/* Each rung is louder than the last in the one dimension type has to be loud in:
	   size, weight of tracking, and finally colour. Two rows is a good turn; five is the
	   whole board in one check, and it gets the wordmark treatment. */
	.t3 {
		font-size: clamp(1.75rem, 11vw, 2.6rem);
		letter-spacing: 0.08em;
		text-shadow:
			0 0 34px rgb(238 243 250 / 42%),
			0 2px 10px rgb(0 0 0 / 60%);
	}

	.t4 {
		font-size: clamp(2rem, 13vw, 3rem);
		font-weight: 900;
		letter-spacing: 0.1em;
		text-shadow:
			0 0 44px rgb(238 243 250 / 55%),
			0 2px 12px rgb(0 0 0 / 65%);
	}

	/* The full board in one check. Painted in the tetromino palette the board itself uses,
	   sweeping across the word — the only place on screen where all five category colours
	   appear at once, because it is the only moment all five rows have. */
	.t5 {
		font-size: clamp(1.6rem, 8.2vw, 2.5rem);
		font-weight: 900;
		letter-spacing: 0.1em;
		text-shadow: none;
	}

	.t5 .ink {
		background: linear-gradient(
			100deg,
			var(--g1),
			var(--g2),
			var(--g4),
			var(--g5),
			var(--g3),
			var(--g1)
		);
		background-size: 220% 100%;
		background-clip: text;
		-webkit-background-clip: text;
		color: transparent;
		/* Follows the glyphs rather than their box, which text-shadow can't do once the
		   fill is a clipped gradient. */
		filter: drop-shadow(0 0 18px rgb(238 243 250 / 35%)) drop-shadow(0 2px 8px rgb(0 0 0 / 70%));
		animation: sweep 1.6s linear infinite;
	}

	.ink {
		display: inline-block;
	}

	@keyframes sweep {
		from {
			background-position: 100% 0;
		}
		to {
			background-position: -100% 0;
		}
	}
</style>
