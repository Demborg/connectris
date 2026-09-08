import { page } from '$app/state';
import { localeOf, segment, strings, type Locale } from './index';

/**
 * The current language, its words, and the URL segment that keeps a link inside it.
 *
 * A function called at the top of a component rather than a store or a context: it reads
 * `page`, which is already reactive and already available everywhere, so there is nothing
 * to provide and nothing that can be forgotten by a component rendered outside a provider.
 *
 * `lang` is the piece that is easy to leave out and expensive to leave out — a `resolve`
 * without it silently drops a Swedish player back into English on the next click.
 */
export function ui(): {
	locale: Locale;
	t: ReturnType<typeof strings>;
	lang: ReturnType<typeof segment>;
} {
	const locale = localeOf(page.data.locale);
	return { locale, t: strings(locale), lang: segment(locale) };
}
