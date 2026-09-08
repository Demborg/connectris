// See https://svelte.dev/docs/kit/types#app.d.ts
// for information about these interfaces

import type { Locale } from '$lib/i18n';
import type { Player } from '$lib/server/ports';

declare global {
	namespace App {
		// interface Error {}
		interface Locals {
			/**
			 * Whoever this browser registered as, resolved from the cookie once per request
			 * in `hooks.server.ts`. Null until they register, which every page but the
			 * registration one refuses to render.
			 */
			player: Player | null;
		}
		interface PageData {
			/**
			 * Which language this page is in, from the URL prefix and settled once by the
			 * layout. Declared here rather than read per page so a component deep in the
			 * tree can ask `page.data.locale` and get a `Locale` rather than `any`.
			 */
			locale: Locale;
		}
		// interface PageState {}
		// interface Platform {}
	}
}

export {};
