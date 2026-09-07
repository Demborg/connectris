import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

/**
 * The focus ring keeps disappearing, and it is invisible when it does.
 *
 * The global reset in app.css strips every button to bare text, so every control in this
 * app has to redraw its own edge — and the way to draw an edge that follows a border
 * radius is `outline`. A scoped component rule compiles to a higher specificity than the
 * global `:focus-visible`, so the decorative outline wins and the ring never paints. It
 * fails silently: the control still *matches* :focus-visible, keyboard navigation still
 * works, and nothing looks broken unless you are the one navigating by keyboard.
 *
 * So: every class that sits on a focusable element and draws its own `outline` has to
 * carry a `:focus-visible` rule of its own.
 */

/** Every `.svelte` under `src`, so a control on a route is held to this too. */
function svelteFiles(dir: string): string[] {
	return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
		const path = join(dir, entry.name);
		if (entry.isDirectory()) return svelteFiles(path);
		return entry.name.endsWith('.svelte') ? [path] : [];
	});
}

const src = join(new URL('.', import.meta.url).pathname, '..', '..');
const components = svelteFiles(src);

/** Elements a player can put keyboard focus on, or that wrap something they can. */
const FOCUSABLE = /<(?:button|textarea|select|label|a)\s[^>]*?class="([^"{}]+)"/g;

/** Classes on focusable elements in the markup, ignoring Svelte's `class:` directives. */
function controlClasses(markup: string): string[] {
	const found = new Set<string>();
	for (const [, list] of markup.matchAll(FOCUSABLE)) {
		for (const cls of list.trim().split(/\s+/)) found.add(cls);
	}
	return [...found];
}

/** Whether `.cls` sets an outline for decoration, i.e. outranks the global ring. */
const drawsOutline = (style: string, cls: string) =>
	new RegExp(`\\.${cls}\\b[^{}]*\\{[^{}]*?\\n\\s*outline:\\s*(?!none)`, 's').test(style);

/** Whether anything scoped to `.cls` styles the focused state. */
const drawsRing = (style: string, cls: string) =>
	new RegExp(`\\.${cls}\\b[^{}]*:focus-visible`).test(style);

describe('focus rings', () => {
	it('finds components with controls to check', () => {
		const checked = components.filter((f) => {
			const source = readFileSync(f, 'utf8');
			return controlClasses(source).length > 0;
		});
		expect(checked.length).toBeGreaterThan(2);
	});

	for (const file of components) {
		const source = readFileSync(file, 'utf8');
		const style = source.slice(source.indexOf('<style>'));

		for (const cls of controlClasses(source)) {
			if (!drawsOutline(style, cls)) continue;

			it(`${file.split('/src/')[1]}: .${cls} draws its own focus ring`, () => {
				expect(
					drawsRing(style, cls),
					`.${cls} is a focusable control that sets a decorative \`outline\`. That rule ` +
						'outranks the global :focus-visible in app.css, so the control has no visible ' +
						`focus ring. Add a \`.${cls}:focus-visible\` rule.`
				).toBe(true);
			});
		}
	}
});
