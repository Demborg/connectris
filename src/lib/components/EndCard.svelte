<script lang="ts">
	import { formatTime } from '$lib/format';
	import type { AnswerReporter } from '$lib/game/report';
	import type { Session } from '$lib/game/session.svelte';
	import type { Difficulty } from '$lib/game/types';

	let {
		session,
		onnext,
		onanswer
	}: { session: Session; onnext: () => void; onanswer: AnswerReporter } = $props();

	let won = $derived(session.status === 'won');
	let best = $derived(session.best);
	// Time is a score once the run is over; it was only corrosive as a clock ticking while
	// you think. Moves and checks stay in the log and off the card — showing them is what
	// made the game read as a move-optimisation puzzle. A previous best is only worth
	// showing when it differs from this run, otherwise it just reads as noise.
	let stats = $derived(
		[
			{ label: 'Time', value: formatTime(session.elapsedMs), was: best && formatTime(best.timeMs) },
			{ label: 'Checks left', value: `${session.left}`, was: best && `${best.checksLeft}` }
		].map((s) => ({ ...s, was: won && s.was !== s.value ? s.was : undefined }))
	);

	/**
	 * The two things a run cannot tell us about itself.
	 *
	 * Everything else worth knowing — how long, how many checks, which rows went first,
	 * where the player hesitated — is already in the log. Difficulty is the one answer the
	 * generation pipeline needs and cannot infer, because cheap-model difficulty is not
	 * human difficulty and nothing maps between them yet. Fairness is the one a losing
	 * player is uniquely qualified to give, and the red team's whole job is finding boards
	 * that are unfair in a way solving cannot reveal.
	 *
	 * Both post the moment they are tapped rather than on a submit, so leaving without
	 * finishing still tells us something. Neither blocks the way out.
	 */
	const LEVELS: { value: Difficulty; label: string }[] = [
		{ value: 'easy', label: 'Too easy' },
		{ value: 'right', label: 'Just right' },
		{ value: 'hard', label: 'Too hard' }
	];

	let difficulty = $state<Difficulty | null>(null);
	let fair = $state<boolean | null>(null);
	let comment = $state('');

	const answer = () => onanswer({ difficulty, fair, comment: comment.trim() });

	function rate(value: Difficulty) {
		difficulty = value;
		answer();
	}

	function judge(value: boolean) {
		fair = value;
		answer();
	}
</script>

<!-- The scrim is a sibling of the card, never its ancestor: a filtered ancestor drags
     everything inside it into the same blurred layer, which is what was making the
     card's own text unreadable. -->
<div class="scrim" aria-hidden="true"></div>

<div class="sheet">
	<div class="card" class:lost={!won}>
		<p class="outcome">{won ? 'Solved' : 'Out of checks'}</p>
		{#if !won}
			<p class="sub">The categories you missed are shown above.</p>
		{/if}

		<dl class="stats">
			{#each stats as s (s.label)}
				<div>
					<dt>{s.label}</dt>
					<dd>{s.value}</dd>
					{#if s.was}<dd class="best">best {s.was}</dd>{/if}
				</div>
			{/each}
		</dl>

		<fieldset>
			<legend>How was that?</legend>
			<div class="choices">
				{#each LEVELS as level (level.value)}
					<button
						class="choice"
						class:picked={difficulty === level.value}
						aria-pressed={difficulty === level.value}
						onclick={() => rate(level.value)}
					>
						{level.label}
					</button>
				{/each}
			</div>
		</fieldset>

		<fieldset>
			<legend>Was it fair?</legend>
			<div class="choices">
				<button
					class="choice"
					class:picked={fair === true}
					aria-pressed={fair === true}
					aria-label="Yes, it was fair"
					onclick={() => judge(true)}>Yes</button
				>
				<button
					class="choice"
					class:picked={fair === false}
					aria-pressed={fair === false}
					aria-label="No, it was not fair"
					onclick={() => judge(false)}>No</button
				>
			</div>
		</fieldset>

		<!-- Posted on blur rather than on every keystroke: one record per thought, not per
		     letter. -->
		<textarea
			class="comment"
			rows="2"
			placeholder="Anything else? (optional)"
			bind:value={comment}
			onblur={answer}></textarea>

		<button class="next" onclick={onnext}>Next puzzle</button>
	</div>
</div>

<style>
	fieldset {
		margin: 0 0 12px;
		padding: 0;
		border: 0;
	}

	legend {
		padding: 0;
		margin-bottom: 6px;
		font-size: var(--fs-xs);
		font-weight: 600;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--dim);
	}

	.choices {
		display: flex;
		gap: 6px;
	}

	/* Unhued. Colour on this board means category, and an answer about the board is not
	   one — see the palette note in Board.svelte. */
	.choice {
		flex: 1;
		padding: 11px 6px;
		border-radius: 10px;
		background: rgb(255 255 255 / 6%);
		outline: 1px solid var(--tile-edge);
		outline-offset: -1px;
		color: var(--text);
		font-size: var(--fs-sm);
		font-weight: 600;
		transition:
			background 160ms ease,
			transform 140ms var(--snap);
	}

	.choice:active {
		transform: scale(0.97);
	}

	.choice.picked {
		background: rgb(255 255 255 / 18%);
		outline-color: rgb(255 255 255 / 42%);
	}

	.comment {
		display: block;
		width: 100%;
		margin-bottom: 14px;
		padding: 10px;
		border: 0;
		border-radius: 10px;
		background: rgb(255 255 255 / 6%);
		outline: 1px solid var(--tile-edge);
		outline-offset: -1px;
		color: var(--text);
		font: inherit;
		font-size: var(--fs-sm);
		resize: none;
	}

	.comment::placeholder {
		color: var(--dim);
	}

	/* Graded rather than uniform: the solved rows are the answer, so they stay readable
	   at the top while the card gets real contrast behind it at the bottom. */
	.scrim {
		position: fixed;
		inset: 0;
		background: linear-gradient(180deg, rgb(6 8 12 / 15%) 0%, rgb(6 8 12 / 82%) 62%);
		animation: fade 260ms ease both;
		z-index: 10;
	}

	.sheet {
		position: fixed;
		inset: 0;
		display: grid;
		place-items: end center;
		padding: 16px;
		padding-bottom: max(16px, env(safe-area-inset-bottom));
		pointer-events: none;
		z-index: 11;
	}

	.card {
		pointer-events: auto;
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

	.outcome {
		margin: 0;
		font-size: var(--fs-lg);
		font-weight: 700;
		letter-spacing: -0.01em;
		color: var(--g4);
	}

	.lost .outcome {
		color: var(--danger);
	}

	.sub {
		margin: 4px 0 18px;
		font-size: var(--fs-sm);
		color: var(--muted);
	}

	.stats {
		display: grid;
		grid-template-columns: repeat(2, 1fr);
		gap: 8px;
		margin: 0 0 18px;
	}

	dt {
		font-size: var(--fs-xs);
		font-weight: 600;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--dim);
	}

	dd {
		margin: 3px 0 0;
		font-size: var(--fs-lg);
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}

	dd.best {
		font-size: var(--fs-xs);
		font-weight: 500;
		color: var(--muted);
	}

	.next {
		width: 100%;
		padding: 14px;
		border-radius: 12px;
		background: var(--accent);
		color: #0d131c;
		font-size: var(--fs-sm);
		font-weight: 700;
		letter-spacing: 0.03em;
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
