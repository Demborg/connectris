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
		ondismiss,
		children
	}: {
		dismissLabel: string;
		labelledBy?: string;
		label?: string;
		dim?: boolean;
		ondismiss: () => void;
		children: Snippet;
	} = $props();

	let panel = $state<HTMLElement | null>(null);
	$effect(() => panel?.focus());
</script>

<svelte:window
	onkeydown={(e) => {
		if (e.key === 'Escape') ondismiss();
	}}
/>

<!-- The scrim is a sibling of the panel, never its ancestor: a filtered ancestor drags
     everything inside it into the same blurred layer, which is what was making the end
     card's own text unreadable. -->
<!-- Tapping outside a sheet to dismiss it is the thing everyone tries first, so it had
     better work. A button rather than a div with a handler: it is a real control, and it
     should answer to a keyboard like one. -->
<button class="scrim" class:thin={!dim} tabindex="-1" aria-label={dismissLabel} onclick={ondismiss}
></button>

<div class="sheet">
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

	/* When the panel is out of the way, the board is what the player came back for, so
	   stop dimming it. */
	.scrim.thin {
		opacity: 0.35;
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
