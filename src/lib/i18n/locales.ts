/**
 * Which languages the game speaks, and how a URL says so.
 *
 * English is unprefixed and Swedish lives under `/sv`, the same convention the generator
 * uses for its category pools: the default language keeps the plain name, so every URL
 * that already existed still resolves and nothing has to be redirected.
 *
 * A board's language and the interface's are one setting, not two. They could be split —
 * an English speaker might want Swedish boards — but nobody has asked to, and two
 * settings is two things to get wrong in a switcher that has to fit on a phone.
 */

export const LOCALES = ['en', 'sv'] as const;

/**
 * Remembers a switcher choice, so `/` sends a returning player back to their language.
 *
 * Here rather than beside the layout that writes it, because a route module may only
 * export the handful of names SvelteKit recognises — and because the name of the cookie is
 * a fact about locales rather than about that one page.
 */
export const LOCALE_COOKIE = 'locale';

export type Locale = (typeof LOCALES)[number];

/** Unprefixed, and the fallback for anything that arrives without a language. */
export const DEFAULT_LOCALE = 'en' satisfies Locale;

export function isLocale(value: unknown): value is Locale {
	return typeof value === 'string' && (LOCALES as readonly string[]).includes(value);
}

/**
 * The URL segment for a locale, or `undefined` for the default.
 *
 * `undefined` rather than `''` because that is what SvelteKit's optional route parameter
 * wants: `resolve('/[[lang=locale]]/boards', { lang: undefined })` is `/boards`.
 */
/** The locales that appear in a URL. English is unprefixed, so it is not one of them. */
export type Prefix = Exclude<Locale, typeof DEFAULT_LOCALE>;

export function segment(locale: Locale): Prefix | undefined {
	return locale === DEFAULT_LOCALE ? undefined : locale;
}

/** The locale a route parameter names. Absent means the default. */
export function localeOf(param: string | undefined): Locale {
	return isLocale(param) ? param : DEFAULT_LOCALE;
}
