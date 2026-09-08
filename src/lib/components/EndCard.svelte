<script lang="ts">
	import Sheet from './Sheet.svelte';
	import { resolve } from '$app/paths';
	import { ui } from '$lib/i18n/ui.svelte';
	import type { AnswerReporter } from '$lib/game/report';
	import type { Session } from '$lib/game/session.svelte';
	import type { Difficulty } from '$lib/game/types';

	let {
		session,
		onnext,
		onanswer
	}: { session: Session; onnext: () => void; onanswer: AnswerReporter } = $props();

	const { t, lang } = $derived(ui());

	let won = $derived(session.status === 'won');

	// Time is a score once the run is over; it was only corrosive as a clock ticking while
	// you think. Moves and checks stay in the log and off the card — showing them is what
	// made the game read as a move-optimisation puzzle. One line rather than a grid: the
	// board behind this card is the thing worth the space.
	let score = $derived(t.end.score(session.elapsedMs, session.left));
	// Separator included, rather than sitting as a leading space inside a span the
	// compiler is free to trim — which it was, rendering "3 left· best 0:03".
	let best = $derived(
		won && session.best && session.best.timeMs !== session.elapsedMs
			? t.end.best(session.best.timeMs)
			: ''
	);

	/**
	 * Where that put you, once the server has counted it.
	 *
	 * Arrives a moment after the card does and appears without moving anything: it is a
	 * link in the row that already holds the ways out, not a new row. The end of a run is
	 * the one moment a standing is interesting, and making someone go and look for it is
	 * how a scoreboard becomes a page nobody opens.
	 */
	let standing = $derived(session.standing);

	/**
	 * Whether the questions are showing.
	 *
	 * The board is exactly as tall as the screen — solved rows keep a full row's height so
	 * nothing resizes mid-game — so anything at the bottom covers categories. That is
	 * merely annoying for the stats and actively self-defeating for the questions: asking
	 * whether a board was fair while hiding the board is asking someone to guess.
	 *
	 * On a **win** the questions go up, because an unseen question is an unanswered one and
	 * everything underneath was revealed row by row and watched as it landed.
	 *
	 * On a **loss** the board goes first. A loss is the only ending that shows the player
	 * something new, and the card lands in the same frame the missed rows begin staggering
	 * in — so on a 360px-tall-ish phone it was covering three of the five categories at the
	 * exact moment they appeared. Asking "was it fair?" over the top of the answer is the
	 * same self-defeating shape the questions-up default was meant to avoid.
	 */
	// The initial value on purpose: this is the card's opening position, and the player
	// owns it from the first tap onwards. The outcome cannot change under a mounted card.
	// svelte-ignore state_referenced_locally
	let asking = $state(won);

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
	const LEVELS: { value: Difficulty; label: string }[] = $derived([
		{ value: 'easy', label: t.end.levels.easy },
		{ value: 'right', label: t.end.levels.right },
		{ value: 'hard', label: t.end.levels.hard }
	]);

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

<!-- Dismissing the card means putting the questions away, not leaving the run: the board
     underneath is the last thing the player has to look at. -->
<Sheet
	dismissLabel={t.end.seeBoard}
	labelledBy="outcome"
	dim={asking}
	ondismiss={() => (asking = false)}
>
	<div class="card" class:lost={!won}>
		<!-- The whole header is the toggle. No swipe: a grabber promised a gesture that
		     took real work to honour on the web and was not worth it for a control that
		     only has two states. A chevron and a word do the same job and cannot be got
		     half right. -->
		<button class="head" onclick={() => (asking = !asking)} aria-expanded={asking}>
			<span class="outcome" id="outcome">{won ? t.end.won : t.end.lost}</span>
			<span class="score">{score}{best}</span>
			<span class="toggle">
				<span class="chev" class:up={!asking} aria-hidden="true">▾</span>
				{asking ? t.end.seeBoard : t.end.questions}
			</span>
		</button>

		{#if asking}
			<div class="asks">
				<!-- Real radios, styled as the pills. These were buttons carrying
				     `aria-pressed`, which is the wrong shape twice over: the options are
				     mutually exclusive, and `fieldset`/`legend` only names *form controls*,
				     so the question had no programmatic relation to the answers — a screen
				     reader announced "Too easy, toggle button, not pressed" with nothing
				     saying what was being asked. As inputs the legend names them for free,
				     and so do arrow keys. -->
				<fieldset>
					<legend>{t.end.howWasThat}</legend>
					<div class="choices">
						{#each LEVELS as level (level.value)}
							<label class="choice" class:picked={difficulty === level.value}>
								<input
									type="radio"
									name="difficulty"
									value={level.value}
									checked={difficulty === level.value}
									onchange={() => rate(level.value)}
								/>
								{level.label}
							</label>
						{/each}
					</div>
				</fieldset>

				<fieldset>
					<legend>{t.end.wasItFair}</legend>
					<div class="choices">
						<label class="choice" class:picked={fair === true}>
							<input
								type="radio"
								name="fair"
								checked={fair === true}
								onchange={() => judge(true)}
							/>
							{t.end.yes}
						</label>
						<label class="choice" class:picked={fair === false}>
							<input
								type="radio"
								name="fair"
								checked={fair === false}
								onchange={() => judge(false)}
							/>
							{t.end.no}
						</label>
					</div>
				</fieldset>

				<!-- Posted on blur rather than on every keystroke: one record per thought,
				     not per letter. -->
				<textarea
					class="comment"
					rows="2"
					aria-label={t.end.commentLabel}
					placeholder={t.end.commentPlaceholder}
					bind:value={comment}
					onblur={answer}></textarea>
			</div>
		{/if}

		<!-- Only ever on a win, which is what makes it affordable: a loss does not move
		     anyone's place, so the server does not compute one and this line does not
		     render. The loss card therefore keeps the exact height it was fixed to have,
		     and the extra line lands only on the card that is already tall because the
		     questions are open under it. -->
		{#if standing}
			<a class="standing" href={resolve('/[[lang=locale]]/top', { lang })}>
				{standing.place === 1 ? t.end.top(standing.of) : t.end.place(standing.place, standing.of)}
			</a>
		{/if}

		<!-- Beside the primary rather than under it. "Next puzzle" is a guess — it walks the
		     backlog and wraps from the end back to today's board, the one you have most
		     likely just played — so the way out of that guess belongs next to it. Stacked,
		     it made the card tall enough to cover the bottom revealed row again, which is
		     the whole thing the loss card was fixed not to do. -->
		<div class="ways-out">
			<a class="boards" href={resolve('/[[lang=locale]]/boards', { lang })}>{t.nav.boards}</a>
			<button class="next" onclick={onnext}>{t.end.next}</button>
		</div>
	</div>
</Sheet>

<style>
	fieldset {
		margin: 0 0 12px;
		padding: 0;
		border: 0;
	}

	/* --muted, not --dim. This phase exists to collect these two answers, and at --dim on
	   the card they were the least legible text on screen — 2.26:1, failing AA by a factor
	   of two, in the smallest size in the scale, in caps, above buttons at 12.85:1. --dim
	   is a hairline colour for the near-black body ground and stops working the moment it
	   is put on the one raised surface in the app. */
	legend {
		padding: 0;
		margin-bottom: 6px;
		font-size: var(--fs-xs);
		font-weight: 600;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--muted);
	}

	.choices {
		display: flex;
		gap: 6px;
	}

	/* Unhued. Colour on this board means category, and an answer about the board is not
	   one — see the palette note in Board.svelte. */
	.choice {
		display: grid;
		place-items: center;
		flex: 1;
		padding: 13px 6px;
		border-radius: var(--r-sm);
		background: var(--veil-1);
		outline: 1px solid var(--tile-edge);
		outline-offset: -1px;
		color: var(--text);
		font-size: var(--fs-sm);
		font-weight: 600;
		cursor: pointer;
		transition:
			background 160ms ease,
			transform 140ms var(--snap);
	}

	/* Hidden but still focusable, so the label is the target and the input keeps the
	   keyboard behaviour. */
	.choice input {
		position: absolute;
		opacity: 0;
		pointer-events: none;
	}

	.choice:active {
		transform: scale(0.97);
	}

	.choice:has(input:focus-visible) {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	.choice.picked {
		background: var(--veil-3);
		outline-color: var(--veil-edge);
	}

	.comment {
		display: block;
		width: 100%;
		margin-bottom: 14px;
		padding: 10px;
		border: 0;
		border-radius: var(--r-sm);
		background: var(--veil-1);
		outline: 1px solid var(--tile-edge);
		outline-offset: -1px;
		color: var(--text);
		font: inherit;
		font-size: var(--fs-sm);
		resize: none;
	}

	.comment:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	.comment::placeholder {
		color: var(--muted);
	}

	/* Sheet owns the panel: its position, its scrim, its chrome. What is left here is what
	   goes on it. */

	/* One tap target across the whole width: outcome, score, and the affordance that
	   gets the card out of the way.

	   It wraps, because it has to. On a loss the outcome is "Out of checks" rather than
	   "Solved", and the three items only fit on one line at 414px and up — below that the
	   score was the sole flex item able to shrink (`flex: 1 1 0; min-width: 0`) and took
	   the whole squeeze, stacking `0:06 · 0 left` into four lines in a 12px column. Now
	   the toggle drops to its own line instead and the score stays intact. */
	.head {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 10px;
		width: 100%;
		padding: 0 0 12px;
		color: inherit;
		text-align: left;
	}

	.head:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	/* A chevron and a word. The chevron alone read as decoration — every button here is
	   stripped to bare text by the global reset — so it is drawn as the control it is,
	   and the word says which way it goes. */
	.toggle {
		display: flex;
		align-items: center;
		gap: 5px;
		flex: none;
		/* Sits at the end of the header, and on its own line once the row wraps. */
		margin-left: auto;
		padding: 5px 10px;
		border-radius: var(--r-pill);
		background: var(--veil-2);
		outline: 1px solid var(--tile-edge);
		outline-offset: -1px;
		font-size: var(--fs-xs);
		font-weight: 600;
		color: var(--text);
		white-space: nowrap;
	}

	.head:active .toggle {
		background: var(--veil-3);
	}

	.chev {
		display: block;
		line-height: 1;
		transition: transform 200ms var(--snap);
	}

	.chev.up {
		transform: rotate(180deg);
	}

	/* Neutral. This was --g4 for a win and --danger (which was byte-identical to --g5) for
	   a loss, i.e. two category tokens used as card chrome — twenty lines above .choice's
	   note that colour on this board means category and an answer about the board is not
	   one. The word carries the outcome; a win gets weight and full-strength text, a loss
	   is quiet. */
	.outcome {
		font-size: var(--fs-lg);
		font-weight: 700;
		letter-spacing: -0.01em;
		color: var(--text);
	}

	.lost .outcome {
		color: var(--muted);
	}

	.score {
		flex: 0 1 auto;
		font-size: var(--fs-sm);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
		color: var(--muted);
	}

	/* Never more than a bit over half the screen, and scrolls inside itself if a small
	   phone in landscape makes even that too much. */
	.asks {
		max-height: 52dvh;
		overflow-y: auto;
	}

	/* A line of text that happens to be a link, not a third button. The row below it holds
	   the two things a player is being asked to choose between, and a third filled control
	   beside them would make the choice look like it had three answers. */
	.standing {
		display: block;
		padding: 0 0 12px;
		font-size: var(--fs-xs);
		font-weight: 600;
		color: var(--muted);
		text-decoration: underline;
		text-underline-offset: 3px;
		text-decoration-color: var(--tile-edge);
	}

	.standing:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	.ways-out {
		display: flex;
		align-items: stretch;
		gap: 8px;
	}

	/* Quieter than the primary: a choice available, not a second thing being urged. */
	.boards {
		display: grid;
		place-items: center;
		flex: none;
		padding: 14px 14px;
		border-radius: var(--r-sm);
		background: var(--veil-1);
		outline: 1px solid var(--tile-edge);
		outline-offset: -1px;
		color: var(--text);
		font-size: var(--fs-sm);
		font-weight: 600;
		white-space: nowrap;
		text-decoration: none;
	}

	.boards:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	.next {
		flex: 1;
		padding: 14px;
		border-radius: var(--r-sm);
		background: var(--accent);
		color: var(--ink-on-accent);
		font-size: var(--fs-sm);
		font-weight: 700;
		letter-spacing: 0.03em;
		transition: transform 140ms var(--snap);
	}

	.next:active {
		transform: scale(0.98);
	}

	/* Offset outwards, so the ring lands on the card rather than inside an accent fill it
	   would be invisible against. */
	.next:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
</style>
