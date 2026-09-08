// See https://svelte.dev/docs/kit/types#app.d.ts
// for information about these interfaces

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
		// interface PageData {}
		// interface PageState {}
		// interface Platform {}
	}
}

export {};
