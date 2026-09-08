<script lang="ts" module>
	/** Every sheet currently open, oldest first. See the Escape handler below. */
	const stack: symbol[] = [];
</script>

<script lang="ts">
	import type { Snippet } from 'svelte';

	/**
	 * A panel over the board that goes away in a tap.
	 *
	 * There were three disclosure idioms in the app for three panels: this one, a transient
	 * callout in reserved slack, and — for the rules — an inline `<section>` in normal flow.
	 * The callout does a genuinely different job. The rules did not: they were the same
	 * shape as the end card and behaved differently only by accident, and being in flow they
	 * were the one panel that moved the board, pushing the Check button 307px below the fold
	 * on a 375×667 screen.
	 *
	 * So the shape lives here once. What goes on the panel is the caller's business; that it
	 * arrives over the board, dims what is behind it, takes focus, and leaves on a tap, a
	 * scrim press or Escape is this component's.
	 */
	let {
		/** Names the dismiss control — what tapping outside the panel does. */
		dismissLabel,
		/** Element id that names the dialog, for `aria-labelledby`. */
		labelledBy,
		/** Fallback name when there is no visible heading to point at. */
		label,
		/** False once the panel is showing something the player wants the board behind. */
		dim = true,
		/** True for a sheet opened from under another one, which has to sit over it. */
		above = false,
		ondismiss,
		children
	}: {
		dismissLabel: string;
		labelledBy?: string;
		label?: string;
		dim?: boolean;
		above?: boolean;
		ondismiss: () => void;
		children: Snippet;
	} = $props();

	let panel = $state<HTMLElement | null>(null);

	/**
	 * The panel takes focus on open and gives it back on close.
	 *
	 * Handing it back is what makes the keyboard path work now that a sheet can be opened
	 * from a control on the board: tab to a solved row, open its notes, close them, and
	 * without this focus is on nothing — the next tab starts again from the wordmark, and
	 * the player has lost their place on a board of five rows.
	 *
	 * Read inside the effect rather than at init: effects do not run on the server, and by
	 * the time this one does the panel has not taken focus yet, so `activeElement` is
	 * still whatever opened it. `??=` so a re-run cannot overwrite it with the panel.
	 */
	let opener: HTMLElement | null = null;
	$effect(() => {
		if (!panel) return;
		opener ??= document.activeElement as HTMLElement | null;
		panel.focus();
		return () => opener?.focus();
	});

	// Escape belongs to the sheet on top, and sheets do stack: a category's notes open
	// over the end card. Every open sheet takes a ticket, the newest one is the topmost,
	// and the ones underneath ignore the key — otherwise one press dismissed the whole
	// pile, closing the card the player was not looking at.
	const me = Symbol();
	$effect(() => {
		stack.push(me);
		return () => stack.splice(stack.indexOf(me), 1);
	});
</script>

<svelte:window
	onkeydown={(e) => {
		if (e.key === 'Escape' && stack[stack.length - 1] === me) ondismiss();
	}}
/>

<!-- The scrim is a sibling of the panel, never its ancestor: a filtered ancestor drags
     everything inside it into the same blurred layer, which is what was making the end
     card's own text unreadable. -->
<!-- Tapping outside a sheet to dismiss it is the thing everyone tries first, so it had
     better work. A button rather than a div with a handler: it is a real control, and it
     should answer to a keyboard like one. -->
<button
	class="scrim"
	class:thin={!dim}
	class:above
	tabindex="-1"
	aria-label={dismissLabel}
	onclick={ondismiss}
></button>

<div class="sheet" class:above>
	<div
		class="panel"
		bind:this={panel}
		role="dialog"
		aria-modal="true"
		aria-labelledby={labelledBy}
		aria-label={labelledBy ? undefined : label}
		tabindex="-1"
	>
		{@render children()}
	</div>
</div>

<style>
	/* Graded rather than uniform: whatever is behind this stays readable at the top while
	   the panel gets real contrast behind it at the bottom. */
	.scrim {
		position: fixed;
		inset: 0;
		display: block;
		width: 100%;
		cursor: default;
		background: linear-gradient(180deg, rgb(6 8 12 / 15%) 0%, rgb(6 8 12 / 82%) 62%);
		animation: fade 260ms ease both;
		transition: opacity 240ms ease;
		z-index: 10;
	}

	/* When the panel is out of the way, the board is what the player came back for — so
	   stop dimming it, and stop standing in front of it.

	   `pointer-events` is the load-bearing half. A scrim is `inset: 0`, so the end card's
	   covered the whole board even once it had been put away: every tap on a solved row
	   landed on the scrim and was read as "dismiss", which made a category's notes
	   unreachable at the one moment a player wants them — the run has just ended and they
	   are looking at the five answers. A thin scrim has nothing left to dismiss, so it
	   gets out of the way entirely. */
	.scrim.thin {
		opacity: 0.35;
		pointer-events: none;
	}

	/* Over whatever sheet was already up, scrim included, so the pair reads as one
	   panel on top of another rather than two panels arguing. */
	.scrim.above {
		z-index: 20;
	}

	.sheet.above {
		z-index: 21;
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

	.panel {
		pointer-events: auto;
		width: 100%;
		max-width: 440px;
		/* Never taller than the screen it is sitting on; content scrolls inside instead. */
		max-height: calc(100dvh - 32px);
		overflow-y: auto;
		padding: 16px;
		border-radius: var(--r-xl);
		background: linear-gradient(180deg, var(--surface-card-hi), var(--surface-card));
		outline: 1px solid var(--tile-edge);
		outline-offset: -1px;
		box-shadow: 0 18px 48px rgb(0 0 0 / 55%);
		animation: rise 420ms var(--snap) both;
	}

	/* It takes focus on open; it should not draw a ring for having done so. */
	.panel:focus {
		outline: 1px solid var(--tile-edge);
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
