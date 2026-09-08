<script lang="ts">
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { LOCALES, segment, strings, type Locale } from '$lib/i18n';
	import { ui } from '$lib/i18n/ui.svelte';

	const { locale, t } = $derived(ui());

	/**
	 * The same page in the other language.
	 *
	 * Resolved from the route the player is already on with only `lang` swapped, so a board
	 * keeps its id and switching language never sends anyone home. Rewriting the pathname
	 * by hand would have been shorter and wrong twice: it would ignore `base`, and it would
	 * need its own copy of the rule about which locale is prefixed.
	 *
	 * The cast is the price of that. `resolve` is typed over the literal union of route ids
	 * and `page.route.id` is a `string | null`; there is no way to tell the compiler that
	 * the id of the route currently rendering is one of the routes that exist.
	 */
	function href(to: Locale): string {
		// `resolve` is typed over the literal union of route ids, and there is no way to
		// tell the compiler that the id of the route currently rendering is one of them.
		const anyRoute = resolve as (id: string, params: Record<string, string | undefined>) => string;
		return anyRoute(page.route.id ?? '/', { ...page.params, lang: segment(to) }) + page.url.search;
	}
</script>

<!-- A form, so the choice survives to the next visit: `/` consults this cookie before it
     consults the browser's own language header. The links are real links and work with
     JavaScript off; the cookie is the only thing that needs the round trip. -->
<nav class="switch" aria-label={t.switcher.label}>
	{#each LOCALES as code (code)}
		{#if code !== locale}
			<!-- `href()` above *is* `resolve`, called with the current route and its own
			     parameters. The rule matches on the call appearing in the attribute and
			     cannot follow it through a helper, and the helper is what makes this one
			     link work from every page. -->
			<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -->
			<a href={href(code)} hreflang={code} data-sveltekit-reload rel="alternate">
				{strings(code).switcher.to[code]}
			</a>
		{:else}
			<span aria-current="true">{strings(code).switcher.to[code]}</span>
		{/if}
	{/each}
</nav>

<style>
	.switch {
		display: flex;
		gap: 10px;
		align-items: baseline;
		margin: 0 0 10px;
		font-size: var(--fs-xs);
		font-weight: 600;
		letter-spacing: 0.1em;
		text-transform: uppercase;
	}

	.switch a {
		color: var(--muted);
		text-decoration: none;
		border-bottom: 1px solid transparent;
	}

	.switch a:hover,
	.switch a:focus-visible {
		color: var(--fg);
		border-bottom-color: currentColor;
	}

	/* The current language is stated rather than linked: a link to the page you are on is
	   a control that does nothing, and this is the one place a player checks which of the
	   two they are in. */
	.switch [aria-current] {
		color: var(--fg);
	}
</style>
