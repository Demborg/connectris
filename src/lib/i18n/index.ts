import { en } from './en';
import { DEFAULT_LOCALE, type Locale } from './locales';
import { sv } from './sv';

export type { Marked, Strings } from './en';
export {
	DEFAULT_LOCALE,
	LOCALES,
	LOCALE_COOKIE,
	isLocale,
	localeOf,
	segment,
	type Locale,
	type Prefix
} from './locales';

const CATALOGUE = { en, sv } satisfies Record<Locale, typeof en>;

/**
 * The words for one locale.
 *
 * Both catalogues are imported rather than loaded per request. They are a few kilobytes
 * and this is a two-language game, so splitting them would buy a round trip's worth of
 * complexity to save less than one image. It also means a component can ask for its
 * strings synchronously, during SSR, without the layout having to serialise them into the
 * page payload on every navigation.
 */
export function strings(locale: Locale = DEFAULT_LOCALE) {
	return CATALOGUE[locale] ?? CATALOGUE[DEFAULT_LOCALE];
}
