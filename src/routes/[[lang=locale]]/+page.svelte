<script lang="ts">
	import Game from '$lib/components/Game.svelte';
	import LocaleSwitch from '$lib/components/LocaleSwitch.svelte';
	import { ui } from '$lib/i18n/ui.svelte';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const { t } = $derived(ui());
</script>

{#if data.game}
	<Game board={data.game.board} backlog={data.game.backlog} />
{:else}
	<!-- A language with nothing published yet. Swedish starts here and fills up a board a
	     night, so this is a state the game passes through rather than a fault: it says so,
	     and it puts the switcher right under the sentence, because the other language does
	     have a board today. -->
	<div class="app empty">
		<h1>{t.brand}</h1>
		<p>{t.game.none}</p>
		<LocaleSwitch />
	</div>
{/if}

<style>
	.empty {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 18px;
		min-height: 100svh;
		padding: 12px;
		text-align: center;
	}

	h1 {
		margin: 0;
		font-size: var(--fs-lg);
		font-weight: 800;
		letter-spacing: 0.18em;
	}

	p {
		max-width: 26ch;
		margin: 0;
		color: var(--muted);
	}
</style>
