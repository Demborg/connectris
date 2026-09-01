<script lang="ts">
	import Board from '$lib/components/Board.svelte';
	import ComboFlash from '$lib/components/ComboFlash.svelte';
	import EndCard from '$lib/components/EndCard.svelte';
	import Lives from '$lib/components/Lives.svelte';
	import puzzles from '$lib/data/puzzles.json';
	import { formatTime } from '$lib/format';
	import { Session } from '$lib/game/session.svelte';
	import type { Puzzle } from '$lib/game/types';

	const all = puzzles as Puzzle[];

	let index = $state(0);
	let session = $state(new Session(all[0]));
	let rulesOpen = $state(false);

	// `elapsedMs` reads Date.now(), which is not reactive, so the clock is pulled on a
	// timer while a run is live and re-read once when the run ends.
	let elapsed = $state(0);
	$effect(() => {
		elapsed = session.elapsedMs;
		if (session.status !== 'playing') return;
		const id = setInterval(() => (elapsed = session.elapsedMs), 250);
		return () => clearInterval(id);
	});

	function load(i: number) {
		index = ((i % all.length) + all.length) % all.length;
		session = new Session(all[index]);
		rulesOpen = false;
	}
</script>

<svelte:head>
	<title>Connectris — {session.puzzle.name}</title>
</svelte:head>

<div class="app">
	<header>
		<div>
			<h1>CONNECTRIS</h1>
			<p class="puzzle">{session.puzzle.name} · {index + 1}/{all.length}</p>
		</div>
		<Lives lives={session.lives} />
	</header>

	<div class="meters">
		<span class="clock">{formatTime(elapsed)}</span>
		<span class="dot">·</span>
		<span>{session.moves} {session.moves === 1 ? 'move' : 'moves'}</span>
		<span class="dot">·</span>
		<span>{session.checks} {session.checks === 1 ? 'check' : 'checks'}</span>
		<button class="help" onclick={() => (rulesOpen = !rulesOpen)}>
			{rulesOpen ? 'Close' : 'How to play'}
		</button>
	</div>

	{#if rulesOpen}
		<section class="rules">
			<ol>
				<li>Sort all 20 words into 5 rows of four. Order <em>inside</em> a row doesn't matter.</li>
				<li>
					Tap two words to swap them. Tap two rank numbers to swap whole rows — also one move.
				</li>
				<li>
					<strong>Check clears from the top down only.</strong> A correct row sitting below a wrong one
					doesn't clear. Put the row you're surest about first.
				</li>
				<li>A check that clears nothing costs a life. Making progress is free.</li>
				<li>A miss tells you how many rows are right — never which ones.</li>
			</ol>
			<div class="picker">
				{#each all as p, i (p.id)}
					<button class:current={i === index} onclick={() => load(i)}>{p.name}</button>
				{/each}
			</div>
		</section>
	{/if}

	<!-- Well and callout share a stage so the press can sweep up across both, starting
	     level with the button rather than appearing at the top of the board. -->
	<div class="stage">
		<main class="well">
			<Board {session} />
		</main>

		<!-- The slack between the well and the thumb. It grows as rows clear, which is
		     exactly when there is something to shout about. -->
		<div class="callout">
			{#if session.combo}
				<ComboFlash rows={session.combo} />
			{/if}
		</div>

		{#if session.sweeping}
			<div class="sweep" aria-hidden="true"></div>
		{/if}
	</div>

	<footer>
		<p class="feedback" aria-live="polite">{session.feedback || ' '}</p>
		<button
			class="check"
			class:firing={session.sweeping}
			disabled={session.over}
			onclick={() => session.check()}
		>
			Check{session.rows.length > 0 && session.rows.length < 5
				? ` ${session.rows.length} rows`
				: ''}
		</button>
	</footer>

	<!-- Hold the card back while a combo is on screen. The winning move is the one clear
	     worth celebrating, and it is exactly the one the card would otherwise cover. -->
	{#if session.over && !session.combo}
		<EndCard {session} onnext={() => load(index + 1)} />
	{/if}
</div>

<style>
	.app {
		display: flex;
		flex-direction: column;
		gap: 10px;
		min-height: 100dvh;
		max-width: 460px;
		margin-inline: auto;
		padding: max(12px, env(safe-area-inset-top)) 12px max(12px, env(safe-area-inset-bottom));
	}

	header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
	}

	h1 {
		margin: 0;
		font-size: var(--fs-sm);
		font-weight: 800;
		letter-spacing: 0.22em;
	}

	.puzzle {
		margin: 2px 0 0;
		font-size: var(--fs-xs);
		color: var(--muted);
	}

	.meters {
		display: flex;
		align-items: center;
		gap: 6px;
		font-size: var(--fs-xs);
		font-variant-numeric: tabular-nums;
		color: var(--muted);
	}

	.clock {
		color: var(--text);
		font-weight: 600;
	}

	.dot {
		color: var(--dim);
	}

	.help {
		margin-left: auto;
		font-size: var(--fs-xs);
		color: var(--muted);
		text-decoration: underline;
		text-underline-offset: 3px;
		text-decoration-color: var(--dim);
	}

	.rules {
		padding: 12px 14px;
		border-radius: 14px;
		background: rgb(255 255 255 / 3%);
		outline: 1px solid var(--tile-edge);
		outline-offset: -1px;
		animation: reveal 260ms var(--ease) both;
	}

	.rules ol {
		margin: 0;
		padding-left: 18px;
		font-size: var(--fs-sm);
		line-height: 1.5;
		color: var(--muted);
	}

	.rules strong {
		color: var(--text);
	}

	.picker {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		margin-top: 12px;
	}

	.picker button {
		padding: 5px 10px;
		border-radius: 999px;
		font-size: var(--fs-xs);
		color: var(--muted);
		background: rgb(255 255 255 / 5%);
	}

	.picker button.current {
		color: #0d131c;
		background: var(--accent);
		font-weight: 600;
	}

	.stage {
		position: relative;
		display: flex;
		flex-direction: column;
		flex: 1;
		gap: 10px;
	}

	.callout {
		position: relative;
		flex: 1;
		min-height: 44px;
	}

	/* Anticipation: two light rails run up the side of the stage from button height to
	   the top of the well, arriving just as the clearing wave starts down. */
	.sweep {
		position: absolute;
		inset: 0;
		pointer-events: none;
		/* Confined to the stage, so the rails enter at button height and leave at the top
		   of the well rather than streaking past the header. Clipping here rather than on
		   .stage keeps it away from the tiles, whose glow needs to overflow. */
		overflow: hidden;
	}

	.sweep::before,
	.sweep::after {
		content: '';
		position: absolute;
		top: 0;
		width: 3px;
		height: 34%;
		border-radius: 2px;
		background: linear-gradient(180deg, transparent, var(--accent), transparent);
		animation: sweep-up 260ms cubic-bezier(0.3, 0, 0.25, 1) both;
	}

	.sweep::before {
		left: 0;
	}

	.sweep::after {
		right: 0;
	}

	@keyframes sweep-up {
		from {
			opacity: 0;
			transform: translateY(300%);
		}
		30% {
			opacity: 0.85;
		}
		to {
			opacity: 0;
			transform: translateY(-115%);
		}
	}

	/* The well holds five row slots for the whole game — solved rows keep a full row's
	   height — so the board never resizes under the player. */
	.well {
		flex: 0 0 auto;
		padding: 10px;
		border-radius: 18px;
		background:
			linear-gradient(90deg, rgb(255 255 255 / 3.5%), transparent 12px),
			linear-gradient(270deg, rgb(255 255 255 / 3.5%), transparent 12px), var(--well);
		outline: 1px solid var(--well-edge);
		outline-offset: -1px;
	}

	footer {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.feedback {
		margin: 0;
		min-height: 1.1rem;
		font-size: var(--fs-sm);
		text-align: center;
		color: var(--muted);
		animation: reveal 240ms var(--ease);
	}

	.check {
		padding: 15px;
		border-radius: 14px;
		background: linear-gradient(180deg, #232c39, #19212c);
		outline: 1px solid var(--tile-edge);
		outline-offset: -1px;
		font-size: var(--fs-sm);
		font-weight: 700;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		transition: transform 140ms var(--snap);
	}

	.check:active:not(:disabled) {
		transform: scale(0.985);
	}

	/* Roots the sweep in the button, so the light looks like it left from here. */
	.check.firing {
		animation: fire 260ms var(--ease) both;
	}

	@keyframes fire {
		0% {
			background: linear-gradient(180deg, #39465a, #2a3547);
			box-shadow: 0 0 0 6px rgb(238 243 250 / 8%);
		}
		100% {
			background: linear-gradient(180deg, #232c39, #19212c);
			box-shadow: 0 0 0 0 transparent;
		}
	}

	.check:disabled {
		opacity: 0.4;
	}

	@keyframes reveal {
		from {
			opacity: 0;
			transform: translateY(-4px);
		}
	}
</style>
