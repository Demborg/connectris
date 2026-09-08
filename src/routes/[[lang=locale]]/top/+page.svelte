<script lang="ts">
	import { resolve } from '$app/paths';
	import { ui } from '$lib/i18n/ui.svelte';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const { t, lang } = $derived(ui());

	/**
	 * What a row says under the name.
	 *
	 * Solves first because that is the axis people feel, then the two tiebreaks in the
	 * order they are applied — checks in hand, then time. Written out rather than shown as
	 * three columns: at this width a table of numbers reads as a spreadsheet, and only one
	 * of the three is the score.
	 */
	const detail = (row: { checksLeft: number; timeMs: number }) =>
		t.top.detail(row.checksLeft, row.timeMs);

	const boards = (n: number) => t.top.boards(n);
</script>

<svelte:head>
	<title>{t.title.standings}</title>
</svelte:head>

<div class="app">
	<header>
		<h1>{t.brand}</h1>
		<a class="back" href={resolve('/[[lang=locale]]', { lang })}>{t.nav.today}</a>
	</header>

	<h2>{t.top.heading}</h2>
	<!-- Says the rule, because a ranking whose rule is not stated is one people argue
	     about. Same rule a personal best uses, which is the point of there being one. -->
	<p class="note">
		{t.top.rule}
		{t.top.players(data.of)}
	</p>

	{#if data.listed.length === 0}
		<p class="empty">{t.top.empty}</p>
	{:else}
		<ol class="list">
			{#each data.listed as row (row.place)}
				<li class="row" class:you={row.you}>
					<span class="place">{row.place}</span>
					<span class="who">
						<span class="alias">{row.alias}{row.you ? t.top.you : ''}</span>
						<span class="detail">{row.solved > 0 ? detail(row) : t.top.notYet}</span>
					</span>
					<span class="solved">{boards(row.solved)}</span>
				</li>
			{/each}
		</ol>

		{#if data.mine}
			<!-- Below the cut. Shown apart rather than by lengthening the list, so the top
			     list stays a top list and you can still find yourself on the page. -->
			<ol class="list mine" start={data.mine.place}>
				<li class="row you">
					<span class="place">{data.mine.place}</span>
					<span class="who">
						<span class="alias">{data.mine.alias}{t.top.you}</span>
						<span class="detail">{data.mine.solved > 0 ? detail(data.mine) : t.top.notYet}</span>
					</span>
					<span class="solved">{boards(data.mine.solved)}</span>
				</li>
			</ol>
		{/if}
	{/if}

	<a class="boards" href={resolve('/[[lang=locale]]/boards', { lang })}>{t.nav.boards}</a>
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
		gap: 12px;
	}

	h1 {
		margin: 0 auto 0 0;
		font-size: var(--fs-sm);
		font-weight: 800;
		letter-spacing: 0.22em;
	}

	/* Same trick as the game's help link: a real tap target, no change in height. */
	.back {
		padding: 13px 8px;
		margin: -13px -8px;
		font-size: var(--fs-xs);
		color: var(--muted);
		text-decoration: underline;
		text-underline-offset: 3px;
		text-decoration-color: var(--dim);
	}

	h2 {
		margin: 6px 0 0;
		font-size: var(--fs-lg);
		font-weight: 700;
		letter-spacing: -0.01em;
	}

	.note,
	.empty {
		margin: 0 0 4px;
		font-size: var(--fs-xs);
		color: var(--muted);
	}

	.empty {
		padding: 16px 0;
	}

	.list {
		display: flex;
		flex-direction: column;
		gap: 6px;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.mine {
		margin-top: 6px;
		padding-top: 10px;
		border-top: 1px dashed var(--tile-edge);
	}

	.row {
		display: flex;
		align-items: center;
		gap: 12px;
		min-height: 52px;
		padding: 8px 12px;
		border-radius: var(--r-md);
		background: var(--veil-1);
		outline: 1px solid var(--tile-edge);
		outline-offset: -1px;
		font-size: var(--fs-sm);
	}

	/* Your own row, marked the way the boards page marks a solve — a brighter edge, no
	   colour. Colour on this board means category and is not spent on chrome. The "(you)"
	   in the name carries it for anyone who cannot see the edge. */
	.row.you {
		background: var(--veil-2);
		outline-color: var(--veil-edge);
	}

	.place {
		flex: none;
		min-width: 1.6em;
		font-size: var(--fs-sm);
		font-weight: 700;
		font-variant-numeric: tabular-nums;
		color: var(--muted);
	}

	.row.you .place {
		color: var(--text);
	}

	.who {
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-width: 0;
	}

	.alias {
		font-weight: 600;
		overflow-wrap: anywhere;
	}

	.detail {
		font-size: var(--fs-xs);
		font-variant-numeric: tabular-nums;
		color: var(--muted);
	}

	.solved {
		margin-left: auto;
		flex: none;
		font-size: var(--fs-xs);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
		color: var(--muted);
	}

	.boards {
		display: grid;
		place-items: center;
		margin-top: auto;
		padding: 14px;
		border-radius: var(--r-sm);
		background: var(--veil-1);
		outline: 1px solid var(--tile-edge);
		outline-offset: -1px;
		color: var(--text);
		font-size: var(--fs-sm);
		font-weight: 600;
		text-decoration: none;
	}

	.boards:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
</style>
