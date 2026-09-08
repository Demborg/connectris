<script lang="ts">
	import { enhance } from '$app/forms';
	import { ALIAS_MAX, ALIAS_MIN, type AliasProblem } from '$lib/alias';
	import { ui } from '$lib/i18n/ui.svelte';
	import { playedAs } from '$lib/user';
	import type { ActionData } from './$types';

	let { form }: { form: ActionData } = $props();

	const { t } = $derived(ui());

	/**
	 * The rejection, in words.
	 *
	 * The server sends a code and this turns it into a sentence, because the server has no
	 * business holding a copy of the words and the page already knows which language it is
	 * in. The two length messages carry the bound rather than repeating the number.
	 */
	function said(problem: AliasProblem | 'taken'): string {
		if (problem === 'taken') return t.hello.taken;
		if (problem === 'short') return t.alias.short(ALIAS_MIN);
		if (problem === 'long') return t.alias.long(ALIAS_MAX);
		return t.alias[problem];
	}

	/**
	 * The id this browser has been playing under, handed back to the server so the name
	 * being claimed inherits everything already filed against it.
	 *
	 * Empty on the server, where there is no localStorage and no browser to have played,
	 * and filled in when this renders on the client — before anyone has had time to type a
	 * name into the field above it. Empty for anyone new, which is the ordinary case and
	 * costs nothing: the server mints an id instead.
	 */
	let adopt = $derived(playedAs() ?? '');

	// Client-side only as a courtesy. The rule that decides is the server's, because this
	// one can be skipped and that one cannot.
	let alias = $state('');
	let submitting = $state(false);
</script>

<svelte:head>
	<title>{t.title.hello}</title>
</svelte:head>

<div class="app">
	<h1>{t.brand}</h1>

	<div class="panel">
		<h2>{t.hello.heading}</h2>
		<!-- Says what the name is for, because a name box with no stated purpose reads as a
		     sign-up wall. It is neither an account nor an email: the whole cost of entry is
		     one word, and the thing it buys is being on the board. -->
		<p class="why">{t.hello.why}</p>

		<!-- `use:enhance` submits without a navigation when JavaScript is up, and the plain
		     form posts when it is not. This page stands in front of every other one, so it
		     is the one place that must work before hydration. -->
		<form
			method="POST"
			use:enhance={() => {
				submitting = true;
				return async ({ update }) => {
					await update();
					submitting = false;
				};
			}}
		>
			<input type="hidden" name="adopt" value={adopt} />

			<label class="field">
				<span class="label">{t.hello.field}</span>
				<input
					name="alias"
					bind:value={alias}
					maxlength={ALIAS_MAX}
					autocomplete="nickname"
					autocapitalize="words"
					autocorrect="off"
					spellcheck="false"
					placeholder={t.hello.placeholder}
					aria-describedby={form?.problem ? 'problem' : undefined}
					aria-invalid={form?.problem ? 'true' : undefined}
					required
				/>
			</label>

			<!-- Assertive, not polite: the form has just been submitted and rejected, and
			     the reason is the only thing that changed on the page. -->
			<p class="problem" id="problem" role="alert">
				{#if form?.problem}{said(form.problem)}{/if}
			</p>

			<button class="go" type="submit" disabled={submitting || alias.trim().length === 0}>
				{submitting ? t.hello.submitting : t.hello.submit}
			</button>
		</form>
	</div>

	<p class="note">{t.hello.note}</p>
</div>

<style>
	.app {
		display: flex;
		flex-direction: column;
		gap: 14px;
		min-height: 100dvh;
		max-width: 460px;
		margin-inline: auto;
		padding: max(16px, env(safe-area-inset-top)) 12px max(16px, env(safe-area-inset-bottom));
	}

	h1 {
		margin: 0;
		font-size: var(--fs-sm);
		font-weight: 800;
		letter-spacing: 0.22em;
	}

	/* The one raised surface on the page, so the eye has one place to go. Same card
	   treatment the end screen uses — this is the other moment the game asks a question
	   and waits. */
	.panel {
		margin-top: auto;
		padding: 18px 16px;
		border-radius: var(--r-lg);
		background: linear-gradient(var(--surface-card-hi), var(--surface-card));
		outline: 1px solid var(--tile-edge);
		outline-offset: -1px;
	}

	h2 {
		margin: 0 0 6px;
		font-size: var(--fs-lg);
		font-weight: 700;
		letter-spacing: -0.01em;
	}

	/* --muted rather than --dim: this is on a raised surface, where --dim fails contrast.
	   Same rule as the end card's legends. */
	.why {
		margin: 0 0 16px;
		font-size: var(--fs-sm);
		line-height: 1.45;
		color: var(--muted);
	}

	.field {
		display: block;
	}

	.label {
		display: block;
		margin-bottom: 6px;
		font-size: var(--fs-xs);
		font-weight: 600;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--muted);
	}

	input[name='alias'] {
		display: block;
		width: 100%;
		padding: 14px 12px;
		border: 0;
		border-radius: var(--r-sm);
		background: var(--veil-1);
		outline: 1px solid var(--tile-edge);
		outline-offset: -1px;
		color: var(--text);
		font: inherit;
		font-size: var(--fs-md);
	}

	input[name='alias']:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	input[name='alias']::placeholder {
		color: var(--dim);
	}

	input[name='alias'][aria-invalid='true'] {
		outline-color: var(--danger);
	}

	/* Always in the layout, empty until there is something to say — so being told the name
	   is taken does not shove the button out from under a thumb already on its way down. */
	.problem {
		min-height: 1.2em;
		margin: 8px 0 12px;
		font-size: var(--fs-xs);
		color: var(--danger);
	}

	.go {
		display: block;
		width: 100%;
		padding: 15px;
		border-radius: var(--r-sm);
		background: var(--accent);
		color: var(--ink-on-accent);
		font-size: var(--fs-sm);
		font-weight: 700;
		letter-spacing: 0.03em;
		transition: transform 140ms var(--snap);
	}

	.go:active:not(:disabled) {
		transform: scale(0.98);
	}

	.go:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	.go:disabled {
		background: var(--veil-2);
		color: var(--muted);
	}

	.note {
		margin: 0 0 auto;
		font-size: var(--fs-xs);
		line-height: 1.5;
		color: var(--dim);
	}
</style>
