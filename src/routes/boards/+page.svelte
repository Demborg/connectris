<script lang="ts">
	import { resolve } from '$app/paths';
	import { formatTime } from '$lib/format';
	import type { ListedBoard } from '$lib/server/board';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	/**
	 * Today's board has a home of its own and this is not a second address for it. Every
	 * other board is reached by id.
	 */
	const href = (id: string, today: boolean) => (today ? resolve('/') : resolve('/p/[id]', { id }));

	/** Said in words as well as drawn, because a mark alone is not readable. */
	function statusOf(board: ListedBoard) {
		if (board.best) return { kind: 'solved' as const, said: 'Solved' };
		if (board.played) return { kind: 'played' as const, said: 'Played' };
		return { kind: 'new' as const, said: 'Not played' };
	}
</script>

<svelte:head>
	<title>Connectris — Boards</title>
</svelte:head>

<div class="app">
	<header>
		<h1>CONNECTRIS</h1>
		<a class="back" href={resolve('/top')}>Standings</a>
		<a class="back" href={resolve('/')}>Today's board</a>
	</header>

	<h2>Boards</h2>
	<!-- Thirty days is the whole window; a board older than that is not reachable from
	     anywhere, so there is no "load more" and nothing is being withheld. -->
	<p class="note">Every board still in play. Yours are marked, on whatever you play them on.</p>

	<ul class="list">
		{#each data.boards as board, i (board.id)}
			{@const s = statusOf(board)}
			<li>
				<a
					class="board"
					href={href(board.id, i === 0)}
					aria-label="{board.name}{i === 0 ? ", today's board" : ''}, {s.said}{board.best
						? `, best ${formatTime(board.best.timeMs)} with ${board.best.checksLeft} checks left`
						: ''}"
				>
					<span class="mark {s.kind}" aria-hidden="true"></span>
					<span class="name">{board.name}</span>
					{#if i === 0}
						<span class="today">Today</span>
					{/if}
					<span class="record">
						{#if board.best}
							{formatTime(board.best.timeMs)} · {board.best.checksLeft} left
						{:else if board.played}
							Played
						{/if}
					</span>
				</a>
			</li>
		{/each}
	</ul>
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

	/* 20px rather than 12. Both links pad their tap target outwards by 8px on each side —
	   the trick that gives them a real 44px target without changing the header's height —
	   so at 12px the two targets overlapped by four pixels and a thumb aimed between them
	   could land on either. */
	header {
		display: flex;
		align-items: center;
		gap: 20px;
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

	.note {
		margin: 0 0 4px;
		font-size: var(--fs-xs);
		color: var(--muted);
	}

	.list {
		display: flex;
		flex-direction: column;
		gap: 6px;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.board {
		display: flex;
		align-items: center;
		gap: 10px;
		min-height: 52px;
		padding: 10px 12px;
		border-radius: var(--r-md);
		background: var(--veil-1);
		outline: 1px solid var(--tile-edge);
		outline-offset: -1px;
		color: var(--text);
		font-size: var(--fs-sm);
		text-decoration: none;
		transition:
			background 160ms ease,
			transform 140ms var(--snap);
	}

	.board:active {
		transform: scale(0.99);
	}

	.board:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	/* Neutral, like every other mark the game draws outside a category. Colour on this
	   board means category and is not spent on progress — which is also why there is no
	   count anywhere on this page. What you did with a board belongs to the board. */
	.mark {
		flex: none;
		width: 10px;
		height: 10px;
		border-radius: 2px;
	}

	/* The budget's vocabulary, reused rather than reinvented: a filled pip is one you
	   hold, a ring is one you do not. So a solved board is filled and the other two are
	   rings, which is the distinction that matters most; played and unplayed then differ
	   by weight. The words in the right-hand column carry all of it anyway — the mark is
	   reinforcement, never the only channel. */
	.mark.solved {
		background: var(--accent);
	}

	.mark.played {
		box-shadow: inset 0 0 0 1.5px var(--muted);
		transform: scale(0.8);
	}

	.mark.new {
		box-shadow: inset 0 0 0 1.5px var(--tile-edge);
		transform: scale(0.8);
	}

	.name {
		font-weight: 600;
	}

	.today {
		padding: 2px 7px;
		border-radius: var(--r-pill);
		background: var(--veil-2);
		font-size: var(--fs-xs);
		font-weight: 600;
		color: var(--muted);
	}

	.record {
		margin-left: auto;
		font-size: var(--fs-xs);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
		color: var(--muted);
	}
</style>
