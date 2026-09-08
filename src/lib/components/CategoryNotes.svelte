<script lang="ts">
	import type { Group } from '$lib/game/types';

	/**
	 * A finished category, written out.
	 *
	 * What this panel is for is the thing everybody does anyway: a board ends and you go
	 * and look up the row — what that category actually was, what a BASSET is, why
	 * CARDIGAN counts as a name. Playtesting turned up the same move every time, so the
	 * answer lives here instead of in a search bar.
	 *
	 * It reveals nothing: a row only becomes tappable once it is on the table, so this is
	 * the label the player has already been shown, with the reading behind it.
	 *
	 * Contents only — `Sheet` draws the panel this sits on.
	 */
	let { group, colour }: { group: Group; colour: string } = $props();

	// The word list on the board is the answer key's order. Notes carry their own word,
	// so this pairs them up by name rather than by position — a row displayed in some
	// other order can never end up with a note that belongs to its neighbour.
	let notes = $derived(new Map((group.notes?.words ?? []).map((w) => [w.word, w.note])));
</script>

<div class="notes" style:--colour={colour}>
	<h2 id="category-title">
		<span class="chip" aria-hidden="true"></span>
		{group.label}
	</h2>

	{#if group.notes}
		<p class="summary">{group.notes.summary}</p>

		<!-- A description list, because that is what this is: four terms and their
		     definitions. It also gets the pairing across to a screen reader for free,
		     which a two-column grid of spans does not. -->
		<dl>
			{#each group.words as word (word)}
				<div class="entry">
					<dt>{word}</dt>
					<dd>{notes.get(word) ?? '—'}</dd>
				</div>
			{/each}
		</dl>
	{/if}
</div>

<style>
	/* The row's own colour comes in with it, so the panel is visibly the bar that was
	   tapped rather than a generic dialog about it. */
	.notes {
		display: grid;
		gap: 12px;
	}

	h2 {
		display: flex;
		align-items: center;
		gap: 9px;
		margin: 0;
		font-size: var(--fs-xs);
		font-weight: 700;
		letter-spacing: 0.09em;
		text-transform: uppercase;
		color: color-mix(in oklab, var(--colour) 45%, white);
	}

	/* The same 11px square the solved row carries, so the panel and the bar it came from
	   are the same object. */
	.chip {
		flex: 0 0 auto;
		width: 11px;
		height: 11px;
		border-radius: 3px;
		background: var(--colour);
		box-shadow: 0 0 12px color-mix(in oklab, var(--colour) 60%, transparent);
	}

	.summary {
		margin: 0;
		font-size: var(--fs-md);
		line-height: 1.45;
		color: var(--text);
	}

	dl {
		display: grid;
		gap: 10px;
		margin: 0;
		padding-top: 10px;
		border-top: 1px solid var(--tile-edge);
	}

	/* Word above its line rather than beside it. Two columns is the shape that reads
	   best on a wide screen and the one that leaves a 12-character word 40% of a 375px
	   phone, which is where this game is played. */
	.entry {
		display: grid;
		gap: 2px;
	}

	dt {
		font-size: var(--fs-sm);
		font-weight: 700;
		letter-spacing: 0.04em;
		color: var(--text);
	}

	dd {
		margin: 0;
		font-size: var(--fs-sm);
		line-height: 1.45;
		color: var(--muted);
	}
</style>
