<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import Board from '$lib/components/Board.svelte';
	import Budget from '$lib/components/Budget.svelte';
	import ComboFlash from '$lib/components/ComboFlash.svelte';
	import EndCard from '$lib/components/EndCard.svelte';
	import Verdict from '$lib/components/Verdict.svelte';
	import { httpChecker } from '$lib/game/checker';
	import { httpAnswers, httpReporter } from '$lib/game/report';
	import { Session } from '$lib/game/session.svelte';
	import type { Board as Dealt } from '$lib/game/types';

	type Listed = { id: string; name: string };

	let { board, backlog }: { board: Dealt; backlog: Listed[] } = $props();

	// A new board means a new run. `board` is a fresh object on every navigation, so
	// picking a puzzle rebuilds the session and nothing has to reset it by hand.
	let session = $derived.by(() => new Session(board, httpChecker(board.puzzle.id), httpReporter()));
	let rulesOpen = $state(false);

	// Nothing counts up on screen while you play. Time, moves and checks are all still
	// recorded — see the run log — they just aren't shown, because a visible counter turns
	// the game into an optimisation problem instead of a grouping one.

	let index = $derived(backlog.findIndex((p) => p.id === board.puzzle.id));

	function open(id: string) {
		rulesOpen = false;
		goto(resolve('/p/[id]', { id }));
	}

	// The backlog runs newest first, so the next board to play is the one after this in
	// the list: today's, then yesterday's, then back around.
	const next = () => backlog[(index + 1) % backlog.length];
</script>

<svelte:head>
	<title>Connectris — {session.puzzle.name}</title>
</svelte:head>

<div class="app">
	<header>
		<h1>CONNECTRIS</h1>
		<!-- The label stays put and `aria-expanded` carries the state, matching the end
		     card's toggle. Swapping the label to "Close" made one of the app's two
		     disclosure buttons behave unlike the other, and read as "close the page". -->
		<button
			class="help"
			aria-expanded={rulesOpen}
			aria-controls="rules"
			onclick={() => (rulesOpen = !rulesOpen)}
		>
			How to play
		</button>
	</header>

	<!-- Connections keeps its goal on screen permanently, and it earns the space: it is
	     the one line that says what you are trying to do. The second half carries what
	     the rank numbers used to. -->
	<p class="goal">Make five rows of four — surest at the top</p>

	{#if rulesOpen}
		<section class="rules" id="rules">
			<ol>
				<li>Sort all 20 words into 5 rows of four. Order <em>inside</em> a row doesn't matter.</li>
				<li>Drag a word onto another to swap them, or tap the two of them in turn.</li>
				<li>
					<strong>Check clears from the top down only.</strong> A correct row sitting below a wrong one
					doesn't clear. Put the row you're surest about first.
				</li>
				<li>
					<strong>Every check costs one.</strong> Clearing several rows in one go is how you keep them
					— which is what getting the order right buys you.
				</li>
				<li>A check tells you how many rows are right — never which ones.</li>
			</ol>
			<div class="picker">
				{#each backlog as p (p.id)}
					<button class:current={p.id === board.puzzle.id} onclick={() => open(p.id)}>
						{p.name}
					</button>
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
		     exactly when there is something to shout about. The combo shouts from the
		     middle of it; the verdict sits at the bottom, nearest the button that asked. -->
		<div class="callout" aria-live="polite">
			{#if session.combo}
				<ComboFlash rows={session.combo} />
			{/if}
			{#if session.verdict}
				<Verdict verdict={session.verdict} />
			{/if}
		</div>

		{#if session.sweeping}
			<div class="sweep" aria-hidden="true"></div>
		{/if}
	</div>

	<!-- The budget sits on the button that spends it. -->
	<footer>
		<!-- A transport failure is a "your press did not land" message, which is a state of
		     the button — not something the check said. In the callout it appeared in the
		     slot, at the size and in the colour a missed check uses. -->
		{#if session.fault}
			<p class="fault">{session.fault}</p>
		{/if}
		<Budget left={session.left} />
		<button
			class="check"
			class:firing={session.sweeping}
			class:waiting={session.busy}
			disabled={session.over}
			aria-disabled={session.busy || undefined}
			onclick={() => session.check()}
		>
			Check
		</button>
	</footer>

	<!-- Swaps are otherwise silent: the board is a flat run of buttons, and which row a
	     word ended up in is the entire game. -->
	<p class="sr-only" aria-live="polite">{session.announcement}</p>

	<!-- Hold the card back while a combo is on screen. The winning move is the one clear
	     worth celebrating, and it is exactly the one the card would otherwise cover. -->
	{#if session.over && !session.combo}
		<EndCard
			{session}
			onnext={() => open(next().id)}
			onanswer={httpAnswers(session.id, session.puzzle.id)}
		/>
	{/if}
</div>

<style>
	/* Not --danger: red on this board means the board bit back, and a network that never
	   answered is not the puzzle beating you. */
	.fault {
		margin: 0;
		font-size: var(--fs-sm);
		color: var(--muted);
		text-align: center;
	}

	.sr-only {
		position: absolute;
		width: 1px;
		height: 1px;
		margin: -1px;
		padding: 0;
		overflow: hidden;
		clip-path: inset(50%);
		white-space: nowrap;
	}

	.app {
		display: flex;
		flex-direction: column;
		gap: 10px;
		min-height: 100dvh;
		max-width: 460px;
		margin-inline: auto;
		padding: max(12px, env(safe-area-inset-top)) 12px max(12px, env(safe-area-inset-bottom));
	}

	/* Wordmark and a way to the rules. Nothing else earns a place up here — anything that
	   counts upward while you play changes what the game feels like it is. */
	header {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.goal {
		margin: -2px 0 0;
		font-size: var(--fs-xs);
		font-weight: 600;
		letter-spacing: 0.05em;
		text-align: center;
		color: var(--muted);
	}

	h1 {
		margin: 0 auto 0 0;
		font-size: var(--fs-sm);
		font-weight: 800;
		letter-spacing: 0.22em;
	}

	/* The sole route to the rules and to every other board, and it was a 62×15 hit target
	   on a phone-first game. Padding grows the target to ~41px; the matching negative
	   margin keeps the header exactly the height it was, which matters because the app
	   already does not fit a 640px-tall screen. */
	.help {
		padding: 13px 8px;
		margin: -13px -8px;
		font-size: var(--fs-xs);
		color: var(--muted);
		text-decoration: underline;
		text-underline-offset: 3px;
		text-decoration-color: var(--dim);
	}

	.rules {
		padding: 12px 14px;
		border-radius: var(--r-md);
		background: var(--veil-1);
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

	/* Same trick as .help: a bigger target, the same layout. */
	.picker button {
		padding: 10px;
		margin-block: -5px;
		border-radius: var(--r-pill);
		font-size: var(--fs-xs);
		color: var(--muted);
		background: var(--veil-1);
	}

	.picker button.current {
		color: var(--ink-on-accent);
		background: var(--accent);
		font-weight: 600;
	}

	.picker button:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
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
		display: grid;
		align-items: end;
		flex: 1;
		min-height: 44px;
		padding-bottom: 4px;
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
	   height — so the board never resizes under the player. It carries no border of its
	   own: the rows are the structure now, and an outer frame around framed rows just
	   nests boxes inside boxes. */
	.well {
		flex: 0 0 auto;
		padding: 10px;
		border-radius: var(--r-lg);
		background: var(--well);
	}

	footer {
		display: flex;
		flex-direction: column;
		gap: 12px;
	}

	.check {
		padding: 15px;
		border-radius: var(--r-md);
		background: linear-gradient(180deg, var(--surface-hi), var(--surface));
		outline: 1px solid var(--tile-edge);
		outline-offset: -1px;
		font-size: var(--fs-sm);
		font-weight: 700;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		transition:
			transform 140ms var(--snap),
			opacity 160ms ease;
	}

	/* The decorative outline above outranks the global :focus-visible, so the ring has to
	   be redrawn here or it never appears. */
	.check:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	.check:active:not(:disabled):not([aria-disabled='true']) {
		transform: scale(0.985);
	}

	/* Mid-check the button is not dead, it is waiting — so it stays legible but stops
	   inviting a press it will ignore. */
	.check.waiting {
		opacity: 0.6;
		cursor: default;
	}

	/* Roots the sweep in the button, so the light looks like it left from here. */
	.check.firing {
		animation: fire 260ms var(--ease) both;
	}

	@keyframes fire {
		0% {
			background: linear-gradient(180deg, var(--surface-fire-hi), var(--surface-fire));
			box-shadow: 0 0 0 6px color-mix(in oklab, var(--accent) 8%, transparent);
		}
		100% {
			background: linear-gradient(180deg, var(--surface-hi), var(--surface));
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
